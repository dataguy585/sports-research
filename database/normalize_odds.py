import json
import sqlite3
from pathlib import Path

DB_PATH = Path("database/sports.db")


def get_latest_valid_run(conn):
    return conn.execute(
        """
        SELECT id, retrieved_at, snapshot_path
        FROM collection_runs
        WHERE status = 'VALID'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()


def normalize_snapshot():
    with sqlite3.connect(DB_PATH) as conn:
        run = get_latest_valid_run(conn)

        if run is None:
            print("No VALID collection run found.")
            return

        collection_run_id, snapshot_time, snapshot_path = run

        path = Path(snapshot_path)

        if not path.exists():
            print(f"Snapshot file not found: {path}")
            return

        with open(path) as f:
            record = json.load(f)

        events = record.get("payload", [])

        if not isinstance(events, list):
            print("Snapshot payload is not a list.")
            return

        # Prevent accidentally importing the same run twice.
        existing = conn.execute(
            """
            SELECT COUNT(*)
            FROM odds_snapshots
            WHERE collection_run_id = ?
            """,
            (collection_run_id,),
        ).fetchone()[0]

        if existing:
            print(
                f"Collection run {collection_run_id} "
                f"already contains {existing} normalized odds rows."
            )
            return

        rows = []

        for event in events:
            event_id = event.get("id")
            commence_time = event.get("commence_time")
            home_team = event.get("home_team")
            away_team = event.get("away_team")

            for bookmaker in event.get("bookmakers", []):
                sportsbook_key = bookmaker.get("key")
                sportsbook_name = bookmaker.get("title")
                last_update = bookmaker.get("last_update")

                for market in bookmaker.get("markets", []):
                    market_key = market.get("key")

                    for outcome in market.get("outcomes", []):
                        rows.append(
                            (
                                collection_run_id,
                                snapshot_time,
                                event_id,
                                commence_time,
                                home_team,
                                away_team,
                                sportsbook_key,
                                sportsbook_name,
                                market_key,
                                outcome.get("name"),
                                outcome.get("price"),
                                outcome.get("point"),
                                last_update,
                            )
                        )

        conn.executemany(
            """
            INSERT INTO odds_snapshots (
                collection_run_id,
                snapshot_time,
                event_id,
                commence_time,
                home_team,
                away_team,
                sportsbook_key,
                sportsbook_name,
                market_key,
                outcome_name,
                price,
                point,
                last_update
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        conn.commit()

        print(f"Collection run: {collection_run_id}")
        print(f"Events processed: {len(events)}")
        print(f"Odds rows inserted: {len(rows)}")
        print(f"Source snapshot: {snapshot_path}")


if __name__ == "__main__":
    normalize_snapshot()
