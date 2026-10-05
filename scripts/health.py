import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from config.load_config import load_sport_config


DB_PATH = Path("database/sports.db")
STALE_AFTER_HOURS = 6


def parse_timestamp(value):
    if not value:
        return None

    return datetime.fromisoformat(value)


def hours_old(timestamp):
    now = datetime.now(timezone.utc)
    return (now - timestamp).total_seconds() / 3600


def main():
    parser = argparse.ArgumentParser(
        description="Sports Research health check"
    )

    parser.add_argument(
        "--sport",
        choices=["mlb", "nfl"],
        default="mlb",
        help="Sport to inspect",
    )

    args = parser.parse_args()

    config = load_sport_config(args.sport)

    sport = config["sport"]
    expected_sportsbooks = set(config["required_sportsbooks"])

    if not DB_PATH.exists():
        print("STATUS: DATABASE_MISSING")
        print(f"Database not found: {DB_PATH}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        latest_run = conn.execute(
            """
            SELECT *
            FROM collection_runs
            WHERE sport = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (sport,),
        ).fetchone()

        latest_valid = conn.execute(
            """
            SELECT *
            FROM collection_runs
            WHERE sport = ?
              AND status = 'VALID'
            ORDER BY id DESC
            LIMIT 1
            """,
            (sport,),
        ).fetchone()

        latest_failure = conn.execute(
            """
            SELECT *
            FROM collection_runs
            WHERE sport = ?
              AND status != 'VALID'
            ORDER BY id DESC
            LIMIT 1
            """,
            (sport,),
        ).fetchone()

        total_odds_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM odds_snapshots os
            JOIN collection_runs cr
              ON cr.id = os.collection_run_id
            WHERE cr.sport = ?
            """,
            (sport,),
        ).fetchone()[0]

        latest_normalized = conn.execute(
            """
            SELECT
                os.collection_run_id,
                COUNT(*) AS row_count
            FROM odds_snapshots os
            JOIN collection_runs cr
              ON cr.id = os.collection_run_id
            WHERE cr.sport = ?
            GROUP BY os.collection_run_id
            ORDER BY os.collection_run_id DESC
            LIMIT 1
            """,
            (sport,),
        ).fetchone()

        latest_sportsbooks = []

        if latest_normalized:
            latest_sportsbooks = conn.execute(
                """
                SELECT DISTINCT sportsbook_key
                FROM odds_snapshots
                WHERE collection_run_id = ?
                """,
                (latest_normalized["collection_run_id"],),
            ).fetchall()

    sportsbook_keys = {
        row["sportsbook_key"]
        for row in latest_sportsbooks
    }

    missing_sportsbooks = expected_sportsbooks - sportsbook_keys

    print("=== SPORTS RESEARCH HEALTH ===")
    print(f"Sport: {config['name'].upper()}")

    if latest_run is None:
        print("\nSTATUS: NO_DATA")
        print("No collection runs found for this sport.")
        return

    latest_time = parse_timestamp(latest_run["retrieved_at"])
    age = hours_old(latest_time)

    if latest_run["status"] != "VALID":
        overall_status = "DEGRADED"
    elif age > STALE_AFTER_HOURS:
        overall_status = "STALE"
    elif missing_sportsbooks:
        overall_status = "DEGRADED"
    else:
        overall_status = "HEALTHY"

    print(f"\nSTATUS: {overall_status}")

    print("\nLatest collection:")
    print(f"  Run ID: {latest_run['id']}")
    print(f"  Time: {latest_run['retrieved_at']}")
    print(f"  Age: {age:.2f} hours")
    print(f"  Status: {latest_run['status']}")
    print(f"  HTTP status: {latest_run['http_status']}")
    print(f"  Events: {latest_run['event_count']}")
    print(f"  Bookmaker blocks: {latest_run['bookmaker_count']}")
    print(f"  API requests remaining: {latest_run['requests_remaining']}")

    if latest_valid:
        print("\nLatest valid collection:")
        print(f"  Run ID: {latest_valid['id']}")
        print(f"  Time: {latest_valid['retrieved_at']}")
        print(f"  Snapshot: {latest_valid['snapshot_path']}")

    if latest_failure:
        print("\nLatest non-valid collection:")
        print(f"  Run ID: {latest_failure['id']}")
        print(f"  Time: {latest_failure['retrieved_at']}")
        print(f"  Status: {latest_failure['status']}")
        print(f"  HTTP status: {latest_failure['http_status']}")

        if latest_failure["error_message"]:
            print(f"  Error: {latest_failure['error_message']}")

    print("\nNormalized odds:")
    print(f"  Total rows for sport: {total_odds_rows}")

    if latest_normalized:
        print(
            f"  Latest normalized run: "
            f"{latest_normalized['collection_run_id']}"
        )
        print(
            f"  Rows in latest normalized run: "
            f"{latest_normalized['row_count']}"
        )

    print("\nSportsbook coverage:")
    print(f"  Expected: {', '.join(sorted(expected_sportsbooks))}")
    print(f"  Received: {', '.join(sorted(sportsbook_keys))}")

    if missing_sportsbooks:
        print(
            f"  Missing: "
            f"{', '.join(sorted(missing_sportsbooks))}"
        )
    else:
        print("  Missing: none")


if __name__ == "__main__":
    main()
