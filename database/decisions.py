from datetime import datetime, timezone
import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")


VALID_DECISIONS = {
    "BET",
    "WATCH",
    "NO_BET",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def record_decision(
    *,
    sport,
    collection_run_id,
    event_id,
    commence_time,
    home_team,
    away_team,
    market_key,
    outcome_name,
    sportsbook_key,
    offered_price,
    market_probability,
    model_probability,
    decision,
    stake_units,
    model_version,
    rule_version,
    reason=None,
):
    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"Invalid decision: {decision}"
        )

    model_edge = None

    if (
        model_probability is not None
        and market_probability is not None
    ):
        model_edge = (
            model_probability
            - market_probability
        )

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO decisions (
                created_at,
                sport,
                collection_run_id,
                event_id,
                commence_time,
                home_team,
                away_team,
                market_key,
                outcome_name,
                sportsbook_key,
                offered_price,
                market_probability,
                model_probability,
                model_edge,
                decision,
                stake_units,
                model_version,
                rule_version,
                reason
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                utc_now(),
                sport,
                collection_run_id,
                event_id,
                commence_time,
                home_team,
                away_team,
                market_key,
                outcome_name,
                sportsbook_key,
                offered_price,
                market_probability,
                model_probability,
                model_edge,
                decision,
                stake_units,
                model_version,
                rule_version,
                reason,
            ),
        )

        conn.commit()

        if cursor.rowcount == 1:
            return cursor.lastrowid

        existing = conn.execute(
            """
            SELECT id
            FROM decisions
            WHERE collection_run_id = ?
              AND event_id = ?
              AND market_key = ?
              AND outcome_name = ?
              AND model_version = ?
              AND rule_version = ?
            """,
            (
                collection_run_id,
                event_id,
                market_key,
                outcome_name,
                model_version,
                rule_version,
            ),
        ).fetchone()

        return existing[0] if existing else None
