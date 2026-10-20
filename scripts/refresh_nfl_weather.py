from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from collectors import nfl_weather
from database.db import DB_PATH


def parse_dt(value):
    if not value:
        return None

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def refresh_interval_hours(
    hours_to_kickoff,
):
    if hours_to_kickoff > 72:
        return 24

    if hours_to_kickoff > 24:
        return 12

    if hours_to_kickoff > 6:
        return 4

    return 1


def main():
    now = datetime.now(timezone.utc)

    print("=== NFL WEATHER REFRESH CHECK ===")
    print(
        f"Season / Week: "
        f"{nfl_weather.SEASON} / "
        f"{nfl_weather.WEEK}"
    )
    print(
        f"Checked at: {now.isoformat()}"
    )
    print()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        snapshot = conn.execute(
            """
            SELECT
                id,
                retrieved_at,
                status
            FROM weather_snapshots
            WHERE season = ?
              AND week = ?
            ORDER BY retrieved_at DESC
            LIMIT 1
            """,
            (
                nfl_weather.SEASON,
                nfl_weather.WEEK,
            ),
        ).fetchone()

        if snapshot is None:
            print(
                "No weather snapshot exists."
            )
            print(
                "Action: REFRESH NOW"
            )
            nfl_weather.main()
            return

        retrieved_at = parse_dt(
            snapshot["retrieved_at"]
        )

        rows = conn.execute(
            """
            SELECT
                away_team,
                home_team,
                kickoff_et
            FROM nfl_weather
            WHERE weather_snapshot_id = ?
              AND weather_relevant = 1
              AND kickoff_et IS NOT NULL
            """,
            (
                snapshot["id"],
            ),
        ).fetchall()

    upcoming = []

    for row in rows:
        kickoff = parse_dt(
            row["kickoff_et"]
        )

        if kickoff is None:
            continue

        hours_to_kickoff = (
            kickoff - now
        ).total_seconds() / 3600

        if hours_to_kickoff > 0:
            upcoming.append(
                (
                    hours_to_kickoff,
                    row["away_team"],
                    row["home_team"],
                    kickoff,
                )
            )

    if not upcoming:
        print(
            "No future weather-relevant "
            "games remain."
        )
        print(
            "Action: NO REFRESH"
        )
        return

    upcoming.sort(
        key=lambda item: item[0]
    )

    (
        nearest_hours,
        away_team,
        home_team,
        nearest_kickoff,
    ) = upcoming[0]

    interval_hours = (
        refresh_interval_hours(
            nearest_hours
        )
    )

    snapshot_age_hours = (
        now - retrieved_at
    ).total_seconds() / 3600

    print(
        f"Latest snapshot: "
        f"{snapshot['id']}"
    )
    print(
        f"Snapshot status: "
        f"{snapshot['status']}"
    )
    print(
        f"Snapshot age: "
        f"{snapshot_age_hours:.1f} hours"
    )
    print()
    print(
        f"Nearest weather-relevant game: "
        f"{away_team} @ {home_team}"
    )
    print(
        f"Kickoff: "
        f"{nearest_kickoff.isoformat()}"
    )
    print(
        f"Hours to kickoff: "
        f"{nearest_hours:.1f}"
    )
    print(
        f"Required refresh interval: "
        f"{interval_hours} hours"
    )
    print()

    if (
        snapshot["status"] != "VALID"
        and snapshot_age_hours >= 1
    ):
        print(
            "Latest snapshot is not VALID."
        )
        print(
            "Action: REFRESH NOW"
        )
        nfl_weather.main()
        return

    if snapshot_age_hours >= interval_hours:
        print(
            "Refresh interval reached."
        )
        print(
            "Action: REFRESH NOW"
        )
        nfl_weather.main()
        return

    remaining = (
        interval_hours
        - snapshot_age_hours
    )

    print(
        f"Next refresh due in about "
        f"{remaining:.1f} hours."
    )
    print(
        "Action: NO REFRESH"
    )


if __name__ == "__main__":
    main()
