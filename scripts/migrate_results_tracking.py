import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path("database/sports.db")


def migrate(db_path):
    conn = sqlite3.connect(db_path)

    try:
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(game_results)"
            )
        }

        if "first_retrieved_at" not in columns:
            conn.execute("""
                ALTER TABLE game_results
                ADD COLUMN first_retrieved_at TEXT
            """)

        conn.execute("""
            UPDATE game_results
            SET first_retrieved_at = retrieved_at
            WHERE first_retrieved_at IS NULL
        """)

        conn.commit()

        count = conn.execute("""
            SELECT COUNT(*)
            FROM game_results
            WHERE first_retrieved_at IS NOT NULL
        """).fetchone()[0]

        print("STATUS: VALID")
        print(f"Database: {db_path}")
        print(f"Results with first retrieval timestamp: {count}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB
    )

    args = parser.parse_args()
    migrate(args.db)


if __name__ == "__main__":
    main()
