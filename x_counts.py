import os
import requests
from datetime import datetime, timedelta, timezone

BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
MIN_LIKES = 50
DAYS_BACK = 15
BASE_URL = "https://api.x.com/2/tweets/search/recent"
HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}"
}


def iso_time(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def count_popular_tweets(query: str, min_likes: int, days_back: int = 15) -> int:
    if not BEARER_TOKEN:
        raise RuntimeError("Set X_BEARER_TOKEN environment variable with your bearer token.")

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days_back)

    params = {
        "query": query,
        "start_time": iso_time(start_time),
        "end_time": iso_time(now),
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
    q_jeannette = '("Jeannette Jara" OR "Jeannet Jara" OR jeannette_jara) lang:es -is:retweet'
    q_evelyn = '("Evelyn Matthei" OR evelynmatthei) lang:es -is:retweet'

    print(f"Counting tweets in last {DAYS_BACK} days with >= {MIN_LIKES} likes...\n")

    n_jeannette = count_popular_tweets(q_jeannette, MIN_LIKES, DAYS_BACK)
    n_evelyn = count_popular_tweets(q_evelyn, MIN_LIKES, DAYS_BACK)

    print("Results:")
    print(f"  Jeannette Jara : {n_jeannette} tweets with >= {MIN_LIKES} likes")
    print(f"  Evelyn Matthei : {n_evelyn} tweets with >= {MIN_LIKES} likes")


if __name__ == "__main__":
    main()
