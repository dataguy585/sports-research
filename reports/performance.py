import argparse
import sqlite3
from pathlib import Path

from config.load_config import load_sport_config


DB_PATH = Path("database/sports.db")


def main():
    parser = argparse.ArgumentParser(
        description="Sports Research performance report"
    )

    parser.add_argument(
        "--sport",
        choices=["mlb", "nfl"],
        required=True,
        help="Sport to evaluate",
    )

    args = parser.parse_args()

    config = load_sport_config(args.sport)
    sport = config["sport"]

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM decisions
            WHERE sport = ?
            ORDER BY created_at, id
            """,
            (sport,),
        ).fetchall()

    print("=== SPORTS RESEARCH PERFORMANCE ===")
    print(f"Sport: {config['name'].upper()}")

    if not rows:
        print("\nNo decisions recorded.")
        return

    total = len(rows)

    decision_counts = {
        "BET": 0,
        "WATCH": 0,
        "NO_BET": 0,
    }

    result_counts = {
        "WIN": 0,
        "LOSS": 0,
        "PUSH": 0,
        "NO_ACTION": 0,
    }

    settled = 0
    unsettled = 0
    total_staked = 0.0
    profit_units = 0.0

    edges = []

    for row in rows:
        decision = row["decision"]

        if decision in decision_counts:
            decision_counts[decision] += 1

        if row["settled_status"] == "SETTLED":
            settled += 1
        else:
            unsettled += 1

        result = row["result"]

        if result in result_counts:
            result_counts[result] += 1

        if decision == "BET":
            total_staked += row["stake_units"] or 0.0

        profit_units += row["profit_units"] or 0.0

        if row["model_edge"] is not None:
            edges.append(row["model_edge"])

    avg_edge = (
        sum(edges) / len(edges)
        if edges
        else None
    )

    roi = (
        profit_units / total_staked
        if total_staked > 0
        else None
    )

    print(f"\nTotal decision rows: {total}")

    print("\nDecisions:")
    print(f"  BET:     {decision_counts['BET']}")
    print(f"  WATCH:   {decision_counts['WATCH']}")
    print(f"  NO_BET:  {decision_counts['NO_BET']}")

    print("\nSettlement:")
    print(f"  Settled:   {settled}")
    print(f"  Unsettled: {unsettled}")
    print(f"  Wins:      {result_counts['WIN']}")
    print(f"  Losses:    {result_counts['LOSS']}")
    print(f"  Pushes:    {result_counts['PUSH']}")
    print(f"  No action: {result_counts['NO_ACTION']}")

    print("\nPerformance:")
    print(f"  Units staked: {total_staked:.2f}")
    print(f"  Profit units: {profit_units:+.2f}")

    if roi is None:
        print("  ROI:          N/A")
    else:
        print(f"  ROI:          {roi * 100:+.2f}%")

    if avg_edge is None:
        print("  Avg edge:     N/A")
    else:
        print(f"  Avg edge:     {avg_edge * 100:+.2f} pp")

    versions = sorted({
        (
            row["model_version"],
            row["rule_version"],
        )
        for row in rows
    })

    print("\nVersions:")

    for model_version, rule_version in versions:
        print(
            f"  Model: {model_version} | "
            f"Rules: {rule_version}"
        )


if __name__ == "__main__":
    main()
