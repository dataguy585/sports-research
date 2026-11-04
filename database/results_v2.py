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
    db_path=None,
):
    if db_path is None:
        db_path = DB_PATH

    if status == "COMPLETED":
        if home_score is None or away_score is None:
            raise ValueError(
                "Completed games must contain both scores"
            )

        if home_score > away_score:
            winner = home_team
        elif away_score > home_score:
            winner = away_team
        else:
            winner = "TIE"
    else:
        winner = None

    retrieved_at = utc_now()

    payload_hash = (
        payload_sha256(source_payload)
        if source_payload is not None
        else None
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
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
                source_payload_sha256,
                first_retrieved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(sport, event_id)
            DO UPDATE SET

                commence_time = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.commence_time
                    ELSE excluded.commence_time
                END,

                home_team = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.home_team
                    ELSE excluded.home_team
                END,

                away_team = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.away_team
                    ELSE excluded.away_team
                END,

                home_score = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.home_score
                    ELSE excluded.home_score
                END,

                away_score = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.away_score
                    ELSE excluded.away_score
                END,

                status = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.status
                    ELSE excluded.status
                END,

                winner = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.winner
                    ELSE excluded.winner
                END,

                completed_at = CASE
                    WHEN game_results.status = 'COMPLETED'
                    THEN game_results.completed_at
                    ELSE excluded.completed_at
                END,

                retrieved_at = excluded.retrieved_at,

                source = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.source
                    ELSE excluded.source
                END,

                source_payload_sha256 = CASE
                    WHEN game_results.status = 'COMPLETED'
                     AND excluded.status != 'COMPLETED'
                    THEN game_results.source_payload_sha256
                    ELSE excluded.source_payload_sha256
                END

            WHERE
                game_results.status != 'COMPLETED'
                OR excluded.status = 'COMPLETED'
                OR game_results.retrieved_at != excluded.retrieved_at
        """, (
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
            retrieved_at,
        ))

        conn.commit()
