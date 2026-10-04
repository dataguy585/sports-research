import sqlite3
from collections import defaultdict
from pathlib import Path

from evaluation.market_math import american_to_implied, remove_vig

DB_PATH = Path("database/sports.db")

REQUIRED_BOOKS = {
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
        ).fetchone()["run_id"]

        if latest_run is None:
            print("No normalized odds found.")
            return

        rows = conn.execute(
            """
            SELECT
                event_id,
                commence_time,
                home_team,
                away_team,
                sportsbook_key,
                sportsbook_name,
                outcome_name,
                price
            FROM odds_snapshots
            WHERE collection_run_id = ?
              AND market_key = 'h2h'
            ORDER BY commence_time, sportsbook_name, outcome_name
            """,
            (latest_run,),
        ).fetchall()

    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["event_id"],
            row["sportsbook_key"],
        )
        grouped[key].append(row)

    print("=== MARKET BENCHMARK REPORT ===")
    print(f"Collection run: {latest_run}\n")

    event_consensus = defaultdict(lambda: defaultdict(list))

    for (event_id, sportsbook_key), market_rows in grouped.items():

        if len(market_rows) != 2:
            print(
                f"[SKIP] Event {event_id} / {sportsbook_key}: "
                f"expected 2 outcomes, got {len(market_rows)}"
            )
            continue

        first = market_rows[0]

        matchup = (
            f"{first['away_team']} @ "
            f"{first['home_team']}"
        )

        prices = [
            market_rows[0]["price"],
            market_rows[1]["price"],
        ]

        raw_probs = [
            american_to_implied(price)
            for price in prices
        ]

        fair_probs = remove_vig(raw_probs)

        print(matchup)
        print(f"  {first['sportsbook_name']}")

        for row, raw_prob, fair_prob in zip(
            market_rows,
            raw_probs,
            fair_probs,
        ):
            print(
                f"    {row['outcome_name']}: "
                f"{row['price']:+.0f} | "
                f"raw={raw_prob:.4f} | "
                f"no-vig={fair_prob:.4f}"
            )

            if sportsbook_key in REQUIRED_BOOKS:
                event_consensus[event_id][
                    row["outcome_name"]
                ].append(fair_prob)

        print()

    print("=== CONSENSUS NO-VIG BENCHMARK ===\n")

    seen_events = set()

    for row in rows:
        event_id = row["event_id"]

        if event_id in seen_events:
            continue

        seen_events.add(event_id)

        matchup = (
            f"{row['away_team']} @ "
            f"{row['home_team']}"
        )

        print(matchup)

        outcome_data = event_consensus[event_id]

        if not outcome_data:
            print("  No required-book consensus available.\n")
            continue

        for outcome_name, probs in sorted(
            outcome_data.items()
        ):
            consensus = sum(probs) / len(probs)

            print(
                f"  {outcome_name}: "
                f"{consensus:.4f} "
                f"({consensus * 100:.2f}%) "
                f"from {len(probs)} books"
            )

        print()


if __name__ == "__main__":
    main()
