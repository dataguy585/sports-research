from __future__ import annotations

import sqlite3

from database.db import DB_PATH
from reports.nfl_week import normalize_team

def get_latest_injury_snapshot(conn, season, expected_week):
    return conn.execute(
        """
        SELECT
            id,
            retrieved_at,
            season,
            expected_week,
            latest_week,
            status,
            row_count,
            source,
            snapshot_path,
            payload_sha256,
            error_message
        FROM injury_snapshots
        WHERE season = ?
          AND expected_week = ?
        ORDER BY
            CASE
                WHEN status = 'VALID'
                 AND latest_week = expected_week THEN 0
                WHEN status = 'VALID' THEN 1
                ELSE 2
            END,
            retrieved_at DESC
        LIMIT 1
        """,
        (
            season,
            expected_week,
        ),
    ).fetchone()


def get_team_injuries(
    conn,
    injury_snapshot_id,
    team,
    week,
):
    return conn.execute(
        """
        SELECT
            team,
            week,
            gsis_id,
            position,
            full_name,
            report_primary_injury,
            report_secondary_injury,
            report_status,
            practice_primary_injury,
            practice_secondary_injury,
            practice_status
        FROM nfl_injuries
        WHERE injury_snapshot_id = ?
          AND team = ?
          AND week = ?
        ORDER BY
            CASE report_status
                WHEN 'Out' THEN 1
                WHEN 'Doubtful' THEN 2
                WHEN 'Questionable' THEN 3
                ELSE 4
            END,
            position,
            full_name
        """,
        (
            injury_snapshot_id,
            team,
            week,
        ),
    ).fetchall()


def matchup_injury_context(
    away_team,
    home_team,
    season,
    expected_week,
):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        snapshot = get_latest_injury_snapshot(
            conn,
            season,
            expected_week,
        )

        if snapshot is None:
            return {
                "status": "UNAVAILABLE",
                "reason": "No injury snapshot found.",
                "snapshot": None,
                "away": [],
                "home": [],
            }

        if snapshot["status"] != "VALID":
            return {
                "status": "STALE",
                "reason": (
                    f"Source latest week "
                    f"{snapshot['latest_week']} "
                    f"is behind expected week "
                    f"{snapshot['expected_week']}."
                ),
                "snapshot": dict(snapshot),
                "away": [],
                "home": [],
            }

        away_team = normalize_team(away_team)
        home_team = normalize_team(home_team)

        away = get_team_injuries(
            conn,
            snapshot["id"],
            away_team,
            expected_week,
        )

        home = get_team_injuries(
            conn,
            snapshot["id"],
            home_team,
            expected_week,
        )

        return {
            "status": "VALID",
            "reason": None,
            "snapshot": dict(snapshot),
            "away": [
                dict(row)
                for row in away
            ],
            "home": [
                dict(row)
                for row in home
            ],
        }
