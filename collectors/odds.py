from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY")

BASE_URL = "https://api.the-odds-api.com/v4"

SPORT = "baseball_mlb"
REGIONS = "us"
MARKETS = "h2h"
ODDS_FORMAT = "american"

DATA_DIR = Path("data/raw/odds")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_snapshot(payload, status, metadata=None):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(raw_json.encode()).hexdigest()

    record = {
        "retrieved_at": utc_now(),
        "source": "the_odds_api",
        "sport": SPORT,
        "markets": MARKETS,
        "status": status,
        "payload_sha256": payload_hash,
        "metadata": metadata or {},
        "payload": payload,
    }

    path = DATA_DIR / f"odds_{timestamp}.json"

    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return path


def collect():
    print("Starting The Odds API collection...")

    if not API_KEY:
        print("STATUS: CONFIGURATION_ERROR")
        print("ODDS_API_KEY is missing from .env")
        return

    url = f"{BASE_URL}/sports/{SPORT}/odds/"

    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        remaining = response.headers.get("x-requests-remaining")
        used = response.headers.get("x-requests-used")
        last = response.headers.get("x-requests-last")

        metadata = {
            "http_status": response.status_code,
            "requests_remaining": remaining,
            "requests_used": used,
            "requests_last": last,
        }

        response.raise_for_status()
        data = response.json()

    except requests.RequestException as exc:
        path = save_snapshot(
            payload={"error": str(exc)},
            status="DATA_SOURCE_FAILURE",
        )

        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return

    except ValueError as exc:
        path = save_snapshot(
            payload={"error": f"Invalid JSON: {exc}"},
            status="DATA_SOURCE_FAILURE",
        )

        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return

    if not isinstance(data, list):
        path = save_snapshot(
            payload=data,
            status="INVALID_RESPONSE",
            metadata=metadata,
        )

        print("STATUS: INVALID_RESPONSE")
        print(f"Saved snapshot: {path}")
        return

    if len(data) == 0:
        path = save_snapshot(
            payload=data,
            status="EMPTY_MARKET",
            metadata=metadata,
        )

        print("STATUS: EMPTY_MARKET")
        print("The API returned zero MLB events.")
        print(f"Saved snapshot: {path}")
        return

    bookmaker_count = sum(
        len(event.get("bookmakers", []))
        for event in data
    )

    if bookmaker_count == 0:
        status = "PARTIAL_DATA"
    else:
        status = "VALID"

    metadata["event_count"] = len(data)
    metadata["bookmaker_count"] = bookmaker_count

    path = save_snapshot(
        payload=data,
        status=status,
        metadata=metadata,
    )

    print(f"STATUS: {status}")
    print(f"MLB events received: {len(data)}")
    print(f"Bookmaker blocks received: {bookmaker_count}")

    if remaining is not None:
        print(f"API requests remaining: {remaining}")

    print(f"Saved snapshot: {path}")


if __name__ == "__main__":
    collect()
