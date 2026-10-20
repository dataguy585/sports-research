from __future__ import annotations

import sqlite3
from datetime import datetime

from database.db import DB_PATH
from reports.nfl_week import normalize_team


def get_latest_weather_snapshot(
    conn,
    season,
    week,
):
    return conn.execute(
        """
        SELECT
            id,
            retrieved_at,
            season,
            week,
            status,
            game_count,
            weather_game_count,
            indoor_game_count,
            source,
            error_message
        FROM weather_snapshots
        WHERE season = ?
          AND week = ?
        ORDER BY retrieved_at DESC
        LIMIT 1
        """,
        (
            season,
            week,
        ),
    ).fetchone()

def weather_freshness(
    retrieved_at,
    kickoff_et,
):
    retrieved = datetime.fromisoformat(
        retrieved_at
    )

    kickoff = datetime.fromisoformat(
        kickoff_et
    )

    hours_to_kickoff = (
        kickoff - retrieved
    ).total_seconds() / 3600

    if hours_to_kickoff > 72:
        label = "PRELIMINARY"
    elif hours_to_kickoff > 24:
        label = "DEVELOPING"
    elif hours_to_kickoff > 6:
        label = "HIGH"
    else:
        label = "GAMEDAY"

    return {
        "label": label,
        "hours_to_kickoff": hours_to_kickoff,
    }

def matchup_weather_context(
    away_team,
    home_team,
    season,
    week,
):
    away_team = normalize_team(
        away_team
    )
    home_team = normalize_team(
        home_team
    )

    with sqlite3.connect(
        DB_PATH
    ) as conn:
        conn.row_factory = sqlite3.Row

        snapshot = (
            get_latest_weather_snapshot(
                conn,
                season,
                week,
            )
        )

        if snapshot is None:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "No weather snapshot "
                    "available."
                ),
                "snapshot": None,
                "weather": None,
            }

        row = conn.execute(
            """
            SELECT
                away_team,
                home_team,
                stadium_id,
                stadium,
                city,
                roof_type,
                weather_relevant,
                kickoff_et,
                local_kickoff,
                forecast_time,
                temperature_f,
                precipitation_in,
                weather_code,
                wind_mph,
                wind_gust_mph,
                snapshot_path
            FROM nfl_weather
            WHERE weather_snapshot_id = ?
              AND away_team = ?
              AND home_team = ?
            LIMIT 1
            """,
            (
                snapshot["id"],
                away_team,
                home_team,
            ),
        ).fetchone()

        if row is None:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "Matchup missing from "
                    "weather snapshot."
                ),
                "snapshot": dict(snapshot),
                "weather": None,
            }
        freshness = None

        if (
            row["weather_relevant"]
            and row["kickoff_et"]
        ):
            freshness = weather_freshness(
                snapshot["retrieved_at"],
                row["kickoff_et"],
            )
        return {
            "status": snapshot["status"],
            "reason": None,
            "snapshot": dict(snapshot),
            "weather": dict(row),
            "freshness": freshness,
        }
