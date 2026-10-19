import argparse
import sqlite3

from collectors.odds import collect
from config.load_config import load_sport_config
from database.normalize_odds import normalize_snapshot
from evaluation.market_benchmark import main as build_market_benchmark


def main():
    parser = argparse.ArgumentParser(
        description="Sports Research odds pipeline"
    )

    parser.add_argument(
        "--sport",
        choices=["mlb", "nfl"],
        default="mlb",
        help="Sport configuration to use",
    )

    args = parser.parse_args()

    config = load_sport_config(args.sport)

    print("=== SPORTS RESEARCH ODDS PIPELINE ===")
    print(f"Sport: {config['name'].upper()}")

    print("\n[1/3] Collecting odds...")
    status, run_id = collect(config)

    if status != "VALID":
        print(f"\nPipeline stopped: collection status = {status}")
        return

    print("\n[2/3] Normalizing latest valid snapshot...")
    normalize_snapshot(run_id)
    with sqlite3.connect("database/sports.db") as conn:
        market_rows = conn.execute(
            """
            SELECT
                market_key,
                COUNT(*) AS row_count
            FROM odds_snapshots
            WHERE collection_run_id = ?
            GROUP BY market_key
            ORDER BY market_key
            """,
            (run_id,),
        ).fetchall()

    print("\nMarket rows:")
    for market_key, row_count in market_rows:
        print(
            f"  {market_key:<10} {row_count}"
        )
    print("\n[3/3] Building market benchmark...")
    build_market_benchmark(run_id=run_id, quiet=True)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
