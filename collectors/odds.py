from datetime import datetime, timezone
import json
from pathlib import Path
import requests

DATA_DIR = Path("data/raw/odds")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def save_snapshot(payload, status, source="test_source"):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    record = {
        "retrieved_at": utc_now(),
        "source": source,
        "status": status,
        "payload": payload,
    }

    path = DATA_DIR / f"odds_{timestamp}.json"

    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return path

def collect():
    print("Starting odds collection...")

    try:
        response = requests.get(
            "https://httpbin.org/json",
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

    except Exception as exc:
        path = save_snapshot(
            payload={"error": str(exc)},
            status="DATA_SOURCE_FAILURE"
        )

        print("STATUS: DATA_SOURCE_FAILURE")
        print(f"Saved failure snapshot: {path}")
        return

    if not data:
        path = save_snapshot(
            payload=data,
            status="EMPTY_RESPONSE"
        )

        print("STATUS: EMPTY_RESPONSE")
        print(f"Saved snapshot: {path}")
        return

    path = save_snapshot(
        payload=data,
        status="VALID"
    )

    print("STATUS: VALID")
    print(f"Saved snapshot: {path}")

if __name__ == "__main__":
    collect()
