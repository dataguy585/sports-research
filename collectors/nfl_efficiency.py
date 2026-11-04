from __future__ import annotations

import hashlib
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from database.db import DB_PATH


SEASON = 2026

SOURCE_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/pbp/play_by_play_2026.csv"
)

RAW_DIR = Path("data/raw/efficiency/nfl")



NFL_SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/schedules/games.csv"
)


def latest_completed_week(season):
    response = requests.get(
        NFL_SCHEDULE_URL,
        timeout=60,
    )
    response.raise_for_status()

    schedule = pd.read_csv(
        io.BytesIO(response.content),
        low_memory=False,
    )

    required = {
        "season", "week", "game_type",
        "game_id", "home_score", "away_score",
    }

    if not required.issubset(schedule.columns):
        raise RuntimeError("NFL schedule missing required columns")

    schedule = schedule[
        (schedule["season"] == season)
        & (schedule["game_type"] == "REG")
    ].copy()

    if schedule.empty:
        raise RuntimeError("No regular-season schedule found")

    schedule["completed"] = (
        schedule["home_score"].notna()
        & schedule["away_score"].notna()
    )

    week_status = schedule.groupby("week").agg(
        games=("game_id", "count"),
        completed=("completed", "sum"),
    )

    completed_through = 0

    for week in sorted(week_status.index):
        week = int(week)

        # Require consecutive weeks.
        if week != completed_through + 1:
            break

        row = week_status.loc[week]

        if row["games"] == 0:
            break

        if row["completed"] != row["games"]:
            break

        completed_through = week

    if completed_through == 0:
        raise RuntimeError(
            "No fully completed regular-season weeks found"
        )

    return completed_through


def safe_mean(series):
    series = series.dropna()

    if series.empty:
        return None

    return float(series.mean())

def aggregate_team_efficiency(
    df,
    before_week=None,
    recent_games=4,
):
    if before_week is not None:
        df = df[
            df["week"] < before_week
        ].copy()

    teams = sorted(
        set(df["posteam"].dropna())
        | set(df["defteam"].dropna())
    )

    results = []

    for team in teams:
        offense = df[
            df["posteam"] == team
        ]

        defense = df[
            df["defteam"] == team
        ]

        dropbacks = offense[
            offense["qb_dropback"] == 1
        ]

        rushes = offense[
            offense["rush"] == 1
        ]

        team_games = (
            df[
                (df["posteam"] == team)
                | (df["defteam"] == team)
            ][
                ["week", "game_id"]
            ]
            .drop_duplicates()
            .sort_values(
                ["week", "game_id"]
            )
            .tail(recent_games)
        )

        recent_game_ids = (
            team_games["game_id"]
            .tolist()
        )

        recent_offense = offense[
            offense["game_id"].isin(
                recent_game_ids
            )
        ]

        recent_defense = defense[
            defense["game_id"].isin(
                recent_game_ids
            )
        ]

        recent_dropbacks = (
            recent_offense[
                recent_offense[
                    "qb_dropback"
                ] == 1
            ]
        )

        recent_rushes = (
            recent_offense[
                recent_offense[
                    "rush"
                ] == 1
            ]
        )

        results.append(
            {
                "team": team,

                "off_epa_per_play": safe_mean(
                    offense["epa"]
                ),
                "def_epa_per_play": safe_mean(
                    defense["epa"]
                ),

                "off_success_rate": safe_mean(
                    offense["success"]
                ),
                "def_success_rate": safe_mean(
                    defense["success"]
                ),

                "dropback_epa_per_play": safe_mean(
                    dropbacks["epa"]
                ),
                "rush_epa_per_play": safe_mean(
                    rushes["epa"]
                ),

                "off_plays": len(offense),
                "def_plays": len(defense),

                "recent_games": len(
                    recent_game_ids
                ),

                "recent_off_epa_per_play": safe_mean(
                    recent_offense["epa"]
                ),
                "recent_def_epa_per_play": safe_mean(
                    recent_defense["epa"]
                ),

                "recent_off_success_rate": safe_mean(
                    recent_offense["success"]
                ),
                "recent_def_success_rate": safe_mean(
                    recent_defense["success"]
                ),

                "recent_dropback_epa_per_play": safe_mean(
                    recent_dropbacks["epa"]
                ),
                "recent_rush_epa_per_play": safe_mean(
                    recent_rushes["epa"]
                ),
            }
        )

    return results

def store_efficiency_snapshot(
    retrieved_at,
    latest_week,
    through_week,
    status,
    snapshot_path,
    payload_sha256,
    usable,
    team_metrics,
):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO efficiency_snapshots (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retrieved_at.isoformat(),
                SEASON,
                through_week,
                latest_week,
                status,
                len(usable),
                len(team_metrics),
                SOURCE_URL,
                str(snapshot_path),
                payload_sha256,
                None,
            ),
        )

        snapshot_id = cursor.lastrowid

        rows = []

        for row in team_metrics:
            rows.append(
                (
                    snapshot_id,
                    SEASON,
                    through_week,
                    row["team"],
                    row["off_epa_per_play"],
                    row["def_epa_per_play"],
                    row["off_success_rate"],
                    row["def_success_rate"],
                    row["dropback_epa_per_play"],
                    row["rush_epa_per_play"],
                    row["off_plays"],
                    row["def_plays"],
                    row["recent_games"],
                    row["recent_off_epa_per_play"],
                    row["recent_def_epa_per_play"],
                    row["recent_off_success_rate"],
                    row["recent_def_success_rate"],
                    row["recent_dropback_epa_per_play"],
                    row["recent_rush_epa_per_play"],
                )
            )

        conn.executemany(
            """
            INSERT INTO team_efficiency (
                efficiency_snapshot_id,
                season,
                through_week,
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
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )

        return snapshot_id, len(rows)

def main():
    retrieved_at = datetime.now(timezone.utc)

    print("=== NFL EFFICIENCY COLLECTOR ===")
    print(f"Season: {SEASON}")
    print()

    columns = [
        "season",
        "week",
        "season_type",
        "game_id",
        "posteam",
        "defteam",
        "play_type",
        "epa",
        "success",
        "pass",
        "rush",
        "qb_dropback",
        "down",
        "qb_kneel",
        "qb_spike",
    ]

    df = pd.read_csv(
        SOURCE_URL,
        usecols=columns,
    )
    df = df[
        (df["season"] == SEASON)
        & (df["season_type"] == "REG")
    ].copy()

    if df.empty:
        raise RuntimeError(
            "No regular-season play-by-play rows found."
        )

    source_latest_week = int(df["week"].max())

    completed_week = latest_completed_week(SEASON)

    latest_week = min(
        source_latest_week,
        completed_week,
    )

    print(f"Source latest week: {source_latest_week}")
    print(f"Schedule completed through: {completed_week}")

    df = df[
        df["week"] <= latest_week
    ].copy()

    if df.empty:
        raise RuntimeError(
            "No play-by-play data through completed weeks"
        )

    usable = df[
        df["posteam"].notna()
        & df["defteam"].notna()
        & df["epa"].notna()
        & (
            (df["pass"] == 1)
            | (df["rush"] == 1)
        )
        & (df["qb_kneel"] != 1)
        & (df["qb_spike"] != 1)
    ].copy()
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = retrieved_at.strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    output_path = RAW_DIR / (
        f"efficiency_{timestamp}.csv"
    )

    usable.to_csv(
        output_path,
        index=False,
    )

    payload = output_path.read_bytes()

    sha256 = hashlib.sha256(
        payload
    ).hexdigest()

    team_metrics = aggregate_team_efficiency(
        usable,
        before_week=latest_week + 1,
    )
    through_week = latest_week
    status = "VALID"

    snapshot_id, inserted_rows = store_efficiency_snapshot(
        retrieved_at=retrieved_at,
        latest_week=latest_week,
        through_week=through_week,
        status=status,
        snapshot_path=output_path,
        payload_sha256=sha256,
        usable=usable,
        team_metrics=team_metrics,
    )

    print(f"Latest week:   {latest_week}")
    print(f"Usable plays:  {len(usable)}")
    print(f"Teams:         {len(team_metrics)}")
    print(
        f"Retrieved at:  "
        f"{retrieved_at.isoformat()}"
    )
    print(f"SHA256:        {sha256}")
    print(f"Saved snapshot: {output_path}")

    print()
    print(f"Database snapshot ID: {snapshot_id}")
    print(f"Database rows inserted: {inserted_rows}")
    print()

    print("SAMPLE TEAM METRICS")
    for row in team_metrics[:5]:
        print(
            row["team"],
            "off EPA/play=",
            round(
                row["off_epa_per_play"],
                4,
            ),
            "def EPA/play=",
            round(
                row["def_epa_per_play"],
                4,
            ),
            "off success=",
            round(
                row["off_success_rate"],
                4,
            ),
        )


if __name__ == "__main__":
    main()
