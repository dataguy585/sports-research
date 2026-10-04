import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = Path("database/sports.db")


def main():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                collection_run_id,
                snapshot_time,
                event_id,
                home_team,
                away_team,
                outcome_name,
                consensus_probability
            FROM market_benchmarks
            ORDER BY event_id, outcome_name, snapshot_time
            """
        ).fetchall()

    if not rows:
        print("No market benchmark history found.")
        return

    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["event_id"],
            row["outcome_name"],
        )
        grouped[key].append(row)

    print("=== MARKET LINE MOVEMENT ===\n")

    seen_events = set()

    for (event_id, outcome_name), history in grouped.items():
        if len(history) < 2:
            continue

        first = history[0]
        latest = history[-1]

        if event_id not in seen_events:
            matchup = (
                f"{first['away_team']} @ "
                f"{first['home_team']}"
            )

            print(matchup)
            seen_events.add(event_id)

        opening = first["consensus_probability"]
        current = latest["consensus_probability"]
        movement = current - opening

        print(
            f"  {outcome_name}"
            f"\n    First:   {opening * 100:.2f}% "
            f"(run {first['collection_run_id']})"
            f"\n    Latest:  {current * 100:.2f}% "
            f"(run {latest['collection_run_id']})"
            f"\n    Move:    {movement * 100:+.2f} pp"
        )

    print()


if __name__ == "__main__":
    main()

