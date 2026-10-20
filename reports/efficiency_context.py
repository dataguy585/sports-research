from __future__ import annotations

import sqlite3

from database.db import DB_PATH


def get_latest_efficiency_snapshot(
    conn,
    season,
    through_week,
):
    return conn.execute(
        """
        SELECT
            id,
            retrieved_at,
            season,
            through_week,
            source_latest_week,
            status,
            play_count,
            team_count,
            source,
            snapshot_path,
            payload_sha256,
            error_message
        FROM efficiency_snapshots
        WHERE season = ?
          AND through_week = ?
          AND status = 'VALID'
        ORDER BY retrieved_at DESC
        LIMIT 1
        """,
        (
            season,
            through_week,
        ),
    ).fetchone()


def get_team_efficiency(
    conn,
    snapshot_id,
    team,
):
    return conn.execute(
        """
        SELECT
            team,
            off_epa_per_play,
            def_epa_per_play,
            off_success_rate,
            def_success_rate,
            dropback_epa_per_play,
            rush_epa_per_play,
            off_plays,
            def_plays,
            recent_games,
            recent_off_epa_per_play,
            recent_def_epa_per_play,
            recent_off_success_rate,
            recent_def_success_rate,
            recent_dropback_epa_per_play,
            recent_rush_epa_per_play
        FROM team_efficiency
        WHERE efficiency_snapshot_id = ?
          AND team = ?
        LIMIT 1
        """,
        (
            snapshot_id,
            team,
        ),
    ).fetchone()


def matchup_efficiency_context(
    away_team,
    home_team,
    season,
    nfl_week,
):
    through_week = nfl_week - 1

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        snapshot = get_latest_efficiency_snapshot(
            conn,
            season,
            through_week,
        )

        if snapshot is None:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    f"No valid efficiency snapshot "
                    f"through Week {through_week}."
                ),
                "snapshot": None,
                "away": None,
                "home": None,
            }

        away = get_team_efficiency(
            conn,
            snapshot["id"],
            away_team,
        )

        home = get_team_efficiency(
            conn,
            snapshot["id"],
            home_team,
        )

        if away is None or home is None:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "Efficiency data missing for "
                    "one or both teams."
                ),
                "snapshot": dict(snapshot),
                "away": None,
                "home": None,
            }

        return {
            "status": "VALID",
            "reason": None,
            "snapshot": dict(snapshot),
            "away": dict(away),
            "home": dict(home),
        }
