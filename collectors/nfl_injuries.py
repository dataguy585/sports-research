from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from database.db import DB_PATH
from reports.nfl_week import get_current_nfl_week

SEASON = 2026

EXPECTED_WEEK = get_current_nfl_week(SEASON)

if EXPECTED_WEEK is None:
    raise RuntimeError(
        f"Unable to determine current NFL week "
        f"for season {SEASON}."
    )

SOURCE_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/injuries/injuries_2026.csv"
)

RAW_DIR = Path("data/raw/injuries/nfl")


def clean_value(value):
    if pd.isna(value):
        return None

    return value


def store_snapshot(
    retrieved_at,
    latest_week,
    status,
    snapshot_path,
    payload_sha256,
    season_df,
):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO injury_snapshots (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retrieved_at.isoformat(),
                SEASON,
                EXPECTED_WEEK,
                latest_week,
                status,
                len(season_df),
                SOURCE_URL,
                str(snapshot_path),
                payload_sha256,
                (
                    None
                    if status == "VALID"
                    else (
                        f"Source latest week {latest_week} "
                        f"is behind expected week {EXPECTED_WEEK}"
                    )
                ),
            ),
        )

        injury_snapshot_id = cursor.lastrowid

        rows = []

        for _, row in season_df.iterrows():
            rows.append(
                (
                    injury_snapshot_id,
                    int(row["season"]),
                    clean_value(row["season_type"]),
                    clean_value(row["game_type"]),
                    clean_value(row["team"]),
                    int(row["week"]),
                    clean_value(row["gsis_id"]),
                    clean_value(row["position"]),
                    clean_value(row["full_name"]),
                    clean_value(row["first_name"]),
                    clean_value(row["last_name"]),
                    clean_value(row["report_primary_injury"]),
                    clean_value(row["report_secondary_injury"]),
                    clean_value(row["report_status"]),
                    clean_value(row["practice_primary_injury"]),
                    clean_value(row["practice_secondary_injury"]),
                    clean_value(row["practice_status"]),
                )
            )

        conn.executemany(
            """
            INSERT INTO nfl_injuries (
                injury_snapshot_id,
                season,
                season_type,
                game_type,
                team,
                week,
                gsis_id,
                position,
                full_name,
                first_name,
                last_name,
                report_primary_injury,
                report_secondary_injury,
                report_status,
                practice_primary_injury,
                practice_secondary_injury,
                practice_status
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )

        return injury_snapshot_id, len(rows)


def main():
    retrieved_at = datetime.now(timezone.utc)

    print("=== NFL INJURY COLLECTOR ===")
    print(f"Season:        {SEASON}")
    print(f"Expected week: {EXPECTED_WEEK}")
    print()

    df = pd.read_csv(SOURCE_URL)

    if df.empty:
        raise RuntimeError(
            "Injury source returned zero rows."
        )

    source_seasons = sorted(
        df["season"].dropna().unique()
    )

    if SEASON not in source_seasons:
        raise RuntimeError(
            f"Season {SEASON} not present in injury source."
        )

    season_df = df[
        df["season"] == SEASON
    ].copy()

    latest_week = int(
        season_df["week"].max()
    )

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = retrieved_at.strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    output_path = RAW_DIR / (
        f"injuries_{timestamp}.csv"
    )

    season_df.to_csv(
        output_path,
        index=False,
    )

    payload = output_path.read_bytes()

    sha256 = hashlib.sha256(
        payload
    ).hexdigest()

    if latest_week >= EXPECTED_WEEK:
        status = "VALID"
    else:
        status = "STALE"

    snapshot_id, inserted_rows = store_snapshot(
        retrieved_at=retrieved_at,
        latest_week=latest_week,
        status=status,
        snapshot_path=output_path,
        payload_sha256=sha256,
        season_df=season_df,
    )

    print(f"STATUS:        {status}")
    print(f"Rows:          {len(season_df)}")
    print(f"Latest week:   {latest_week}")
    print(
        f"Retrieved at:  "
        f"{retrieved_at.isoformat()}"
    )
    print(f"SHA256:        {sha256}")
    print(f"Saved snapshot: {output_path}")
    print()
    print(f"Database snapshot ID: {snapshot_id}")
    print(f"Database rows inserted: {inserted_rows}")

    if status == "STALE":
        print()
        print(
            "WARNING: Injury data is behind "
            f"the expected NFL week "
            f"({latest_week} < {EXPECTED_WEEK})."
        )


if __name__ == "__main__":
    main()
