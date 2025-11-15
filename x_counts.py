import os
import requests
from datetime import datetime, timedelta, timezone

# Bearer token must be provided via env var
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

# Config
MIN_LIKES = 50
# We conceptually talk about a 7-day window, but we let the API default
# to its recent-search range and only bound the end_time.
DAYS_BACK = 7

# X/Twitter v2 recent search endpoint
BASE_URL = "https://api.twitter.com/2/tweets/search/recent"
HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}"
}


def iso_time(dt: datetime) -> str:
    """Return an RFC3339/ISO8601 string with Z timezone."""
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def count_popular_tweets(query: str, min_likes: int) -> int:
    """Count tweets matching `query` with at least `min_likes`.

    We no longer send `start_time` because the `recent` endpoint already
    restricts results to roughly the last 7 days for standard tiers, and
    the boundary rules for `start_time` are quite strict. Instead, we only
    bound `end_time` slightly before `now` to satisfy the API constraint.
    """
    if not BEARER_TOKEN:
        raise RuntimeError("Set X_BEARER_TOKEN environment variable with your bearer token.")

    now = datetime.now(timezone.utc)
    # X requires end_time to be at least a bit before the request time
    end_time = now - timedelta(seconds=20)

    params = {
        "query": query,
        "end_time": iso_time(end_time),
        "max_results": 100,
        "tweet.fields": "public_metrics,created_at",
    }

    total_count = 0
    next_token = None

    while True:
        if next_token:
            params["next_token"] = next_token
        else:
            params.pop("next_token", None)

        resp = requests.get(BASE_URL, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print("Error:", resp.status_code, resp.text)
            break

        data = resp.json()

        for tweet in data.get("data", []):
            likes = tweet["public_metrics"]["like_count"]
            if likes >= min_likes:
                total_count += 1

        meta = data.get("meta", {})
        next_token = meta.get("next_token")

        if not next_token:
            break

    return total_count


def main():
    # Queries: Spanish, no retweets, mentions by name or handle
    q_jeannette = '("Jeannette Jara" OR "Jeannet Jara" OR jeannette_jara) lang:es -is:retweet'
    q_evelyn = '("Evelyn Matthei" OR evelynmatthei) lang:es -is:retweet'

    print(f"Counting tweets in the recent window (≈{DAYS_BACK} days) with >= {MIN_LIKES} likes...\n")

    n_jeannette = count_popular_tweets(q_jeannette, MIN_LIKES)
    n_evelyn = count_popular_tweets(q_evelyn, MIN_LIKES)

    print("Results:")
    print(f"  Jeannette Jara : {n_jeannette} tweets with >= {MIN_LIKES} likes")
    print(f"  Evelyn Matthei : {n_evelyn} tweets with >= {MIN_LIKES} likes")


if __name__ == "__main__":
    main()
