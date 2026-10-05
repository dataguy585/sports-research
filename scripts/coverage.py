import argparse
import sqlite3
from pathlib import Path

from config.load_config import load_sport_config


DB_PATH = Path("database/sports.db")


def main():
    parser = argparse.ArgumentParser(
        description="Sportsbook event coverage check"
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

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        latest_run = conn.execute(
            """
            SELECT MAX(os.collection_run_id) AS run_id
            FROM odds_snapshots os
            JOIN collection_runs cr
              ON cr.id = os.collection_run_id
            WHERE cr.sport = ?
            """,
            (sport,),
        ).fetchone()

        if not latest_run or latest_run["run_id"] is None:
            print("STATUS: NO_NORMALIZED_DATA")
            print(f"Sport: {config['name'].upper()}")
            return

        run_id = latest_run["run_id"]

        events = conn.execute(
            """
            SELECT DISTINCT
                event_id,
                home_team,
                away_team,
                commence_time
            FROM odds_snapshots
            WHERE collection_run_id = ?
            ORDER BY commence_time
            """,
            (run_id,),
        ).fetchall()

        print("=== SPORTSBOOK EVENT COVERAGE ===")
        print(f"Sport: {config['name'].upper()}")
        print(f"Collection run: {run_id}")
        print(
            f"Required books: "
            f"{', '.join(sorted(expected_sportsbooks))}\n"
        )

        degraded = False

        for event in events:
            books = conn.execute(
                """
                SELECT DISTINCT sportsbook_key
                FROM odds_snapshots
                WHERE collection_run_id = ?
                  AND event_id = ?
                """,
                (run_id, event["event_id"]),
            ).fetchall()

            received = {
                row["sportsbook_key"]
                for row in books
            }

            missing = expected_sportsbooks - received

            matchup = (
                f"{event['away_team']} @ "
                f"{event['home_team']}"
            )

            if missing:
                degraded = True
                print(f"[DEGRADED] {matchup}")
                print(
                    f"  Missing: "
                    f"{', '.join(sorted(missing))}"
                )
            else:
                print(f"[OK]       {matchup}")

        print()

        if degraded:
            print("STATUS: DEGRADED")
        else:
            print("STATUS: HEALTHY")


if __name__ == "__main__":
    main()
