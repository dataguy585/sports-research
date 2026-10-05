import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path

from config.load_config import load_sport_config


DB_PATH = Path("database/sports.db")


def main():
    parser = argparse.ArgumentParser(
        description="Market line movement report"
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

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                mb.collection_run_id,
                mb.snapshot_time,
                mb.event_id,
                mb.home_team,
                mb.away_team,
                mb.outcome_name,
                mb.consensus_probability
            FROM market_benchmarks mb
            JOIN collection_runs cr
              ON cr.id = mb.collection_run_id
            WHERE cr.sport = ?
            ORDER BY
                mb.event_id,
                mb.outcome_name,
                mb.snapshot_time,
                mb.collection_run_id
            """,
            (sport,),
        ).fetchall()

    if not rows:
        print("=== MARKET LINE MOVEMENT ===")
        print(f"Sport: {config['name'].upper()}")
        print("\nNo market benchmark history found.")
        return

    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["event_id"],
            row["outcome_name"],
        )
        grouped[key].append(row)

    print("=== MARKET LINE MOVEMENT ===")
    print(f"Sport: {config['name'].upper()}\n")

    seen_events = set()
    movement_found = False

    for (event_id, outcome_name), history in grouped.items():
        if len(history) < 2:
            continue

        movement_found = True

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

    if not movement_found:
        print("No multi-snapshot line movement available yet.")

    print()


if __name__ == "__main__":
    main()
