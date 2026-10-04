import sqlite3
from pathlib import Path

DB_PATH = Path("database/sports.db")
SCHEMA_PATH = Path("database/schema.sql")

def main():
    schema = SCHEMA_PATH.read_text()

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema)
        conn.commit()

    print(f"Database initialized: {DB_PATH}")

if __name__ == "__main__":
    main()
