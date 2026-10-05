import argparse
import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")


def main():
    parser = argparse.ArgumentParser(
        description="Sports Research slate report"
    )

    parser.add_argument(
        "--run-id",
        type=int,
        required=True,
        help="Collection run ID to report",
    )

    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        run = conn.execute(
            """
            SELECT
                id,
                retrieved_at,
                sport,
                market,
                status
            FROM collection_runs
            WHERE id = ?
            """,
            (args.run_id,),
        ).fetchone()

        if run is None:
            print("STATUS: RUN_NOT_FOUND")
            return

        rows = conn.execute(
            """
            SELECT
                d.id AS decision_id,
                d.event_id,
                d.away_team,
                d.home_team,
                d.outcome_name,
                d.market_probability,
                d.model_probability,
                d.model_edge,
                d.decision,
                d.stake_units,
                d.model_version,
                d.rule_version,
                d.settled_status,
                d.result,
                d.profit_units,
                gr.status AS game_status,
                gr.away_score,
                gr.home_score,
                gr.winner
            FROM decisions d
            LEFT JOIN game_results gr
              ON gr.event_id = d.event_id
             AND gr.sport = d.sport
            WHERE d.collection_run_id = ?
            ORDER BY
                d.event_id,
                d.outcome_name
            """,
            (args.run_id,),
        ).fetchall()

    print("=== SPORTS RESEARCH SLATE ===")
    print(f"Run ID: {run['id']}")
    print(f"Sport: {run['sport']}")
    print(f"Snapshot: {run['retrieved_at']}")
    print(f"Collection status: {run['status']}")

    if not rows:
        print("\nNo decisions found for this run.")
        return

    print(f"Decision rows: {len(rows)}\n")

    current_event = None

    for row in rows:
        if row["event_id"] != current_event:
            if current_event is not None:
                print()

            current_event = row["event_id"]

            matchup = (
                f"{row['away_team']} @ "
                f"{row['home_team']}"
            )

            print(matchup)

            if row["game_status"]:
                print(f"  Game status: {row['game_status']}")

                if (
                    row["away_score"] is not None
                    and row["home_score"] is not None
                ):
                    print(
                        f"  Score: "
                        f"{row['away_team']} {row['away_score']} - "
                        f"{row['home_team']} {row['home_score']}"
                    )

                if row["winner"]:
                    print(f"  Winner: {row['winner']}")

        market_pct = (
            row["market_probability"] * 100
            if row["market_probability"] is not None
            else None
        )

        model_pct = (
            row["model_probability"] * 100
            if row["model_probability"] is not None
            else None
        )

        edge_pp = (
            row["model_edge"] * 100
            if row["model_edge"] is not None
            else None
        )

        print(f"  {row['outcome_name']}")

        if market_pct is not None:
            print(f"    Market:   {market_pct:.2f}%")

        if model_pct is not None:
            print(f"    Model:    {model_pct:.2f}%")

        if edge_pp is not None:
            print(f"    Edge:     {edge_pp:+.2f} pp")

        print(f"    Decision: {row['decision']}")
        print(f"    Stake:    {row['stake_units'] or 0:.2f} units")
        print(f"    Status:   {row['settled_status']}")

        if row["result"]:
            print(f"    Result:   {row['result']}")

        if row["profit_units"] is not None:
            print(
                f"    Profit:   "
                f"{row['profit_units']:+.2f} units"
            )

    print()

    counts = {}

    for row in rows:
        counts[row["decision"]] = (
            counts.get(row["decision"], 0) + 1
        )

    print("=== DECISION SUMMARY ===")

    for decision in sorted(counts):
        print(f"{decision}: {counts[decision]}")

    total_profit = sum(
        row["profit_units"] or 0.0
        for row in rows
    )

    print(f"Profit units: {total_profit:+.2f}")


if __name__ == "__main__":
    main()
