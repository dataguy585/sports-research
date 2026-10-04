import sqlite3
from pathlib import Path

DB_PATH = Path("database/sports.db")

EXPECTED_SPORTSBOOKS = {
    "fanduel",
    "draftkings",
    "betmgm",
}


def main():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        latest_run = conn.execute(
            """
            SELECT MAX(collection_run_id) AS run_id
            FROM odds_snapshots
            """
        ).fetchone()

        if not latest_run or latest_run["run_id"] is None:
            print("STATUS: NO_NORMALIZED_DATA")
            return

        run_id = latest_run["run_id"]

        events = conn.execute(
            """
            SELECT DISTINCT
                event_id,
                home_team,
                away_team
            FROM odds_snapshots
            WHERE collection_run_id = ?
            ORDER BY commence_time
            """,
            (run_id,),
        ).fetchall()

        print("=== SPORTSBOOK EVENT COVERAGE ===")
        print(f"Collection run: {run_id}\n")

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

            received = {row["sportsbook_key"] for row in books}
            missing = EXPECTED_SPORTSBOOKS - received

            matchup = f"{event['away_team']} @ {event['home_team']}"

            if missing:
                degraded = True
                print(f"[DEGRADED] {matchup}")
                print(f"  Missing: {', '.join(sorted(missing))}")
            else:
                print(f"[OK]       {matchup}")

        print()

        if degraded:
            print("STATUS: DEGRADED")
        else:
            print("STATUS: HEALTHY")


if __name__ == "__main__":
    main()
