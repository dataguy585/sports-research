import sqlite3
from pathlib import Path

DB_PATH = Path("database/sports.db")


def log_collection_run(
    retrieved_at,
    source,
    sport,
    market,
    status,
    http_status=None,
    event_count=None,
    bookmaker_count=None,
    requests_remaining=None,
    requests_used=None,
    requests_last=None,
    snapshot_path=None,
    payload_sha256=None,
    error_message=None,
):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO collection_runs (
                retrieved_at,
                source,
                sport,
                market,
                status,
                http_status,
                event_count,
                bookmaker_count,
                requests_remaining,
                requests_used,
                requests_last,
                snapshot_path,
                payload_sha256,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retrieved_at,
                source,
                sport,
                market,
                status,
                http_status,
                event_count,
                bookmaker_count,
                requests_remaining,
                requests_used,
                requests_last,
                snapshot_path,
                payload_sha256,
                error_message,
            ),
        )
        conn.commit()
