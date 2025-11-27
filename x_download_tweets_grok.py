"""Download replies for X/Twitter conversations using Tweepy.

This script reads conversation IDs from a CSV file (column: ``conversation_id``),
queries the recent search endpoint for replies, and stores the results as JSON.

Environment:
    - X_BEARER_TOKEN: Bearer token for the X API v2
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import tweepy

BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

DEFAULT_CSV = Path("data/account_search-allmetrics_honduras.csv")
DEFAULT_OUTPUT = Path("replies_by_conversation.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch replies for a list of conversation IDs using the X API",
    )
    parser.add_argument(
        "--conversation-csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Path to a CSV with a 'conversation_id' column.",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Number of days back to search (uses the recent search endpoint).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the replies JSON file.",
    )
    parser.add_argument(
        "--sleep-between",
        type=float,
        default=0.8,
        help="Seconds to sleep between paginator pages to respect rate limits.",
    )
    return parser.parse_args()


def load_conversation_ids(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    if "conversation_id" not in df.columns:
        raise KeyError("CSV must include a 'conversation_id' column")

    seen: set[str] = set()
    unique_ids: list[str] = []
    for value in df["conversation_id"].dropna().astype(str):
        if value not in seen:
            seen.add(value)
            unique_ids.append(value)

    return unique_ids


def tweet_to_dict(tweet: tweepy.Tweet) -> dict[str, Any]:
    return tweet.data if hasattr(tweet, "data") else tweet._json  # type: ignore[attr-defined]


def fetch_conversation_replies(
    client: tweepy.Client, conv_id: str, start_time: datetime, sleep_between: float
) -> list[tweepy.Tweet]:
    replies: list[tweepy.Tweet] = []
    try:
        for response in tweepy.Paginator(
            client.search_recent_tweets,
            query=f"conversation_id:{conv_id}",
            start_time=start_time,
            tweet_fields=[
                "author_id",
                "created_at",
                "public_metrics",
                "lang",
                "in_reply_to_user_id",
            ],
            expansions=["author_id"],
            user_fields=["username", "name", "verified"],
            max_results=100,
        ):
            if response.data:
                replies.extend(response.data)
            time.sleep(sleep_between)
    except tweepy.TooManyRequests:
        print("Rate limit hit – waiting 15 minutes...")
        time.sleep(15 * 60 + 5)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"Error fetching {conv_id}: {exc}")
    return replies


def main() -> None:
    args = parse_args()

    if not BEARER_TOKEN:
        raise RuntimeError("Set the X_BEARER_TOKEN environment variable with your bearer token.")

    conversation_ids = load_conversation_ids(args.conversation_csv)
    if not conversation_ids:
        print("No conversation IDs found.")
        return

    client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=True)

    start_time = datetime.now(timezone.utc) - timedelta(days=args.days_back)
    all_replies: dict[str, list[tweepy.Tweet]] = {}

    for conv_id in conversation_ids:
        print(f"Fetching replies for conversation {conv_id}...")
        replies = fetch_conversation_replies(client, conv_id, start_time, args.sleep_between)
        all_replies[conv_id] = replies
        print(f"→ Got {len(replies)} replies")

    print(f"\nDone! Total conversations processed: {len(conversation_ids)}")
    print(f"Total replies collected: {sum(len(v) for v in all_replies.values())}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(
            {key: [tweet_to_dict(tweet) for tweet in tweets] for key, tweets in all_replies.items()},
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    print(f"Saved replies to {args.output}")


if __name__ == "__main__":
    main()
