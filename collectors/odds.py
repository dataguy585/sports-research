from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from config.load_config import load_sport_config

import requests
from dotenv import load_dotenv

from database.db import log_collection_run


load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY")

BASE_URL = "https://api.the-odds-api.com/v4"

DEFAULT_CONFIG = load_sport_config("mlb")

DATA_DIR = Path("data/raw/odds")



def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_snapshot(payload, status, sport, markets, metadata=None):
    sport_name = sport.rsplit("_", 1)[-1]
    sport_dir = DATA_DIR / sport_name
    sport_dir.mkdir(parents=True, exist_ok=True)

    retrieved_at = utc_now()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    raw_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(raw_json.encode()).hexdigest()

    record = {
        "retrieved_at": retrieved_at,
        "source": "the_odds_api",
        "sport": sport,
        "markets": markets,
        "status": status,
        "payload_sha256": payload_hash,
        "metadata": metadata or {},
        "payload": payload,
    }

    path = sport_dir / f"odds_{timestamp}.json"

    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return path, payload_hash, retrieved_at


def record_run(
    status,
    path,
    payload_hash,
    retrieved_at,
    sport,
    markets,
    metadata=None,
    error_message=None,
):

    metadata = metadata or {}

    run_id = log_collection_run(
        retrieved_at=retrieved_at,
        source="the_odds_api",
        sport=sport,
        market=markets,
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

    return run_id


def collect(config=None):
    if config is None:
        config = DEFAULT_CONFIG

    sport = config["sport"]
    regions = config["regions"]
    markets = config["markets"]
    odds_format = config["odds_format"]

    if not API_KEY:
        print("STATUS: CONFIGURATION_ERROR")
        print("ODDS_API_KEY is missing from .env")
        return "CONFIGURATION_ERROR"

    url = f"{BASE_URL}/sports/{sport}/odds/"

    params = {
        "apiKey": API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }

    metadata = {}

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
            sport=sport,
	    markets=markets,
            metadata=metadata,
        )

        record_run(
            status="DATA_SOURCE_FAILURE",
            path=path,
            payload_hash=payload_hash,
            retrieved_at=retrieved_at,
	    sport=sport,
	    markets=markets,
            metadata=metadata,
            error_message=error_message,
        )

        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return "DATA_SOURCE_FAILURE"

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
	    sport=sport,
	    markets=markets,
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
	    sport=sport,
	    markets=markets,
	    metadata=metadata
        )

        print("STATUS: INVALID_RESPONSE")
        print(f"Saved snapshot: {path}")
        return "INVALID_RESPONSE"

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
	    sport=sport,
	    markets=markets,
            metadata=metadata,
        )

        print("STATUS: EMPTY_MARKET")
        print(f"The API returned zero {config['name'].upper()} events.")
        print(f"Saved snapshot: {path}")
        return "EMPTY_MARKET"

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
	sport=sport,
	markets=markets,
        metadata=metadata,
    )

    run_id = record_run(
        status=status,
        path=path,
        payload_hash=payload_hash,
        retrieved_at=retrieved_at,
        sport=sport,
        markets=markets,
        metadata=metadata,
    )

    print(f"STATUS: {status}")
    print(f"{config['name'].upper()} events received: {len(data)}")
    print(f"Bookmaker blocks received: {bookmaker_count}")

    if metadata.get("requests_remaining") is not None:
        print(
            f"API requests remaining: "
            f"{metadata['requests_remaining']}"
        )

    print(f"Saved snapshot: {path}")
    print("Collection run recorded in SQLite.")
    

    return status, run_id

if __name__ == "__main__":
    collect()
