from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def payload_sha256(payload):
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def upsert_game_result(
    *,
    sport,
    event_id,
    commence_time,
    home_team,
    away_team,
    home_score,
    away_score,
    status,
    completed_at=None,
    source="manual",
    source_payload=None,
):
    winner = None

    if status == "COMPLETED":
        if home_score > away_score:
            winner = home_team
        elif away_score > home_score:
            winner = away_team
        else:
            winner = "TIE"

    retrieved_at = utc_now()

    payload_hash = None

    if source_payload is not None:
        payload_hash = payload_sha256(source_payload)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO game_results (
                sport,
                event_id,
                commence_time,
                home_team,
                away_team,
                home_score,
                away_score,
                status,
                winner,
                completed_at,
                retrieved_at,
                source,
                source_payload_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sport, event_id)
            DO UPDATE SET
                commence_time = excluded.commence_time,
                home_team = excluded.home_team,
                away_team = excluded.away_team,
                home_score = excluded.home_score,
                away_score = excluded.away_score,
                status = excluded.status,
                winner = excluded.winner,
                completed_at = excluded.completed_at,
                retrieved_at = excluded.retrieved_at,
                source = excluded.source,
                source_payload_sha256 = excluded.source_payload_sha256
            """,
            (
                sport,
                event_id,
                commence_time,
                home_team,
                away_team,
                home_score,
                away_score,
                status,
                winner,
                completed_at,
                retrieved_at,
                source,
                payload_hash,
            ),
        )

        conn.commit()
