import argparse
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

# Bearer token from your X/Twitter app
# export X_BEARER_TOKEN="YOUR_TOKEN"
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

BASE_URL = "https://api.twitter.com/2/tweets/counts/recent"

# Two candidates for this project
CANDIDATES = {
    "Jara": '("Jeannette Jara" OR "Jeannet Jara" OR jeannette_jara) lang:es -is:retweet',
    "Matthei": '("Evelyn Matthei" OR evelynmatthei) lang:es -is:retweet',
}

def bearer_oauth(r: requests.Request) -> requests.Request:
    """Attach bearer token to the request."""
    if not BEARER_TOKEN:
        raise RuntimeError("Set X_BEARER_TOKEN environment variable with your bearer token.")
    r.headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    r.headers["User-Agent"] = "proyectFemCountsPython"
    return r


def fetch_counts(query: str) -> list[dict]:
    """Call /2/tweets/counts/recent for a given query.

    Returns a list of {start, end, tweet_count}.
    """
    params = {
        "query": query,
        "granularity": "day",
    }
    resp = requests.get(BASE_URL, auth=bearer_oauth, params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Error {resp.status_code}: {resp.text}")
    data = resp.json()
    return data.get("data", [])


def extract_conversation_ids(csv_path: str) -> list[str]:
    """Read a CSV and return a de-duplicated list of conversation IDs.

    The CSV must include a ``conversation_id`` column.
    """

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if "conversation_id" not in df.columns:
        raise KeyError("CSV must contain a 'conversation_id' column")

    # Drop missing values, convert to string, and preserve order while de-duplicating.
    seen: set[str] = set()
    unique_ids: list[str] = []
    for conv_id in df["conversation_id"].dropna().astype(str):
        if conv_id not in seen:
            seen.add(conv_id)
            unique_ids.append(conv_id)

    return unique_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch X counts or extract conversation IDs from a CSV.")
    parser.add_argument(
        "--conversation-csv",
        help="Path to a CSV file that includes a 'conversation_id' column.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.conversation_csv:
        ids = extract_conversation_ids(args.conversation_csv)
        print("\nUnique conversation_id values:\n")
        for conv_id in ids:
            print(conv_id)
        return

    if not BEARER_TOKEN:
        raise RuntimeError("X_BEARER_TOKEN is not set in the environment.")

    out_dict: dict[str, list[int]] = {}
    index_dates: list[str] | None = None

    for short_name, query in CANDIDATES.items():
        print(f"Querying counts for: {short_name} ...")
        data = fetch_counts(query)

        # On the first candidate, build the index (one row per day)
        if index_dates is None:
            index_dates = [row["start"][:10] for row in data]  # 'YYYY-MM-DD'

        # Store tweet_count for each day
        counts = [row["tweet_count"] for row in data]
        out_dict[short_name] = counts

        # Small pause, just to be gentle with the API
        time.sleep(1)

    # Build DataFrame: rows = days, columns = candidates
    df = pd.DataFrame(out_dict, index=index_dates)
    df.index.name = "date"

    print("\nDaily tweet counts (recent window):")
    print(df)

    # Save to CSV in the current directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_name = f"x_counts_recent_{timestamp}.csv"
    df.to_csv(out_name)
    print(f"\nSaved CSV to {out_name}")


if __name__ == "__main__":
    main()
