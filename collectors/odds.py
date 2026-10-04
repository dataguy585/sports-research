from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from database.db import log_collection_run


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
    retrieved_at = utc_now()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    raw_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(raw_json.encode()).hexdigest()

    record = {
        "retrieved_at": retrieved_at,
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

    return path, payload_hash, retrieved_at


def record_run(
    status,
    path,
    payload_hash,
    retrieved_at,
    metadata=None,
    error_message=None,
):
    metadata = metadata or {}

    log_collection_run(
        retrieved_at=retrieved_at,
        source="the_odds_api",
        sport=SPORT,
        market=MARKETS,
        status=status,
        http_status=metadata.get("http_status"),
        event_count=metadata.get("event_count"),
        bookmaker_count=metadata.get("bookmaker_count"),
        requests_remaining=metadata.get("requests_remaining"),
        requests_used=metadata.get("requests_used"),
        requests_last=metadata.get("requests_last"),
        snapshot_path=str(path),
        payload_sha256=payload_hash,
        error_message=error_message,
    )


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

    metadata = {}

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        metadata = {
            "http_status": response.status_code,
            "requests_remaining": response.headers.get("x-requests-remaining"),
            "requests_used": response.headers.get("x-requests-used"),
            "requests_last": response.headers.get("x-requests-last"),
        }

        response.raise_for_status()
        data = response.json()

    except requests.RequestException as exc:
        error_message = str(exc)

        if API_KEY:
            error_message = error_message.replace(API_KEY, "[REDACTED]")

        path, payload_hash, retrieved_at = save_snapshot(
            payload={"error": error_message},
            status="DATA_SOURCE_FAILURE",
            metadata=metadata,
        )

        record_run(
            status="DATA_SOURCE_FAILURE",
            path=path,
            payload_hash=payload_hash,
            retrieved_at=retrieved_at,
            metadata=metadata,
            error_message=error_message,
        )

        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return
        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return

    except ValueError as exc:
        error_message = f"Invalid JSON: {exc}"

        path, payload_hash, retrieved_at = save_snapshot(
            payload={"error": error_message},
            status="DATA_SOURCE_FAILURE",
            metadata=metadata,
        )

        record_run(
            status="DATA_SOURCE_FAILURE",
            path=path,
            payload_hash=payload_hash,
            retrieved_at=retrieved_at,
            metadata=metadata,
            error_message=error_message,
        )

        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return

    if not isinstance(data, list):
        path, payload_hash, retrieved_at = save_snapshot(
            payload=data,
            status="INVALID_RESPONSE",
            metadata=metadata,
        )

        record_run(
            status="INVALID_RESPONSE",
            path=path,
            payload_hash=payload_hash,
            retrieved_at=retrieved_at,
            metadata=metadata,
        )

        print("STATUS: INVALID_RESPONSE")
        print(f"Saved snapshot: {path}")
        return

    if len(data) == 0:
        metadata["event_count"] = 0
        metadata["bookmaker_count"] = 0

        path, payload_hash, retrieved_at = save_snapshot(
            payload=data,
            status="EMPTY_MARKET",
            metadata=metadata,
        )

        record_run(
            status="EMPTY_MARKET",
            path=path,
            payload_hash=payload_hash,
            retrieved_at=retrieved_at,
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

    metadata["event_count"] = len(data)
    metadata["bookmaker_count"] = bookmaker_count

    if bookmaker_count == 0:
        status = "PARTIAL_DATA"
    else:
        status = "VALID"

    path, payload_hash, retrieved_at = save_snapshot(
        payload=data,
        status=status,
        metadata=metadata,
    )

    record_run(
        status=status,
        path=path,
        payload_hash=payload_hash,
        retrieved_at=retrieved_at,
        metadata=metadata,
    )

    print(f"STATUS: {status}")
    print(f"MLB events received: {len(data)}")
    print(f"Bookmaker blocks received: {bookmaker_count}")

    if metadata.get("requests_remaining") is not None:
        print(
            f"API requests remaining: "
            f"{metadata['requests_remaining']}"
        )

    print(f"Saved snapshot: {path}")
    print("Collection run recorded in SQLite.")


if __name__ == "__main__":
    collect()
