import argparse
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from database.db import DB_PATH

EASTERN = ZoneInfo("America/New_York")
EPS = 1e-15


def utc_time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Missing timezone")
    return dt.astimezone(timezone.utc)


def result_time(row):
    dt = datetime.fromisoformat(row["commence_time"])

    if row["source"] == "nflverse":
        if dt.tzinfo is not None:
            raise ValueError("Unexpected nflverse timezone")
        dt = dt.replace(tzinfo=EASTERN)
    elif dt.tzinfo is None:
        raise ValueError("Missing result timezone")

    return dt.astimezone(timezone.utc)


def brier(p, outcome):
    return (p - outcome) ** 2


def logloss(p, outcome):
    p = min(max(p, EPS), 1 - EPS)
    return -(outcome * math.log(p) +
             (1 - outcome) * math.log(1 - p))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write grades to database"
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    predictions = conn.execute("""
        SELECT ps.*
        FROM prediction_snapshots ps
        LEFT JOIN prediction_grades pg
          ON pg.prediction_snapshot_id = ps.id
        WHERE pg.id IS NULL
    """).fetchall()

    results = conn.execute("""
        SELECT *
        FROM game_results
        WHERE status = 'COMPLETED'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
    """).fetchall()

    stats = Counter()
    eligible = []

    for p in predictions:
        stats["examined"] += 1

        try:
            kickoff = utc_time(p["commence_time"])
            created = utc_time(p["created_at"])

            if created >= kickoff:
                stats["post_kickoff"] += 1
                continue

            probs = [
                p["home_model_probability"],
                p["away_model_probability"],
                p["home_market_probability"],
                p["away_market_probability"]
            ]

            if any(
                v is None or not math.isfinite(v)
                or not 0 < v < 1
                for v in probs
            ):
                stats["invalid_probability"] += 1
                continue

            exact = []
            fallback = []

            for g in results:
                if g["sport"] != p["sport"]:
                    continue

                if g["home_team"] != p["home_team"]:
                    continue

                if g["away_team"] != p["away_team"]:
                    continue

                if g["event_id"] == p["event_id"]:
                    exact.append(g)
                    continue

                if g["source"] != "nflverse":
                    continue

                delta = abs(
                    (kickoff - result_time(g)).total_seconds()
                )

                if delta <= 900:
                    fallback.append(g)

            candidates = exact if exact else fallback

            if len(candidates) != 1:
                stats[
                    "ambiguous" if candidates else "unmatched"
                ] += 1
                continue

            g = candidates[0]

            if g["home_score"] == g["away_score"]:
                stats["ties_skipped"] += 1
                continue

            winner = (
                p["home_team"]
                if g["home_score"] > g["away_score"]
                else p["away_team"]
            )

            model_pick = (
                p["home_team"]
                if p["home_model_probability"] >=
                   p["away_model_probability"]
                else p["away_team"]
            )

            market_pick = (
                p["home_team"]
                if p["home_market_probability"] >=
                   p["away_market_probability"]
                else p["away_team"]
            )

            outcome = int(winner == p["home_team"])

            values = (
                p["id"],
                datetime.now(timezone.utc).isoformat(),
                g["id"],
                g["home_score"],
                g["away_score"],
                winner,
                model_pick,
                market_pick,
                int(model_pick == winner),
                int(market_pick == winner),
                brier(p["home_model_probability"], outcome),
                brier(p["home_market_probability"], outcome),
                logloss(p["home_model_probability"], outcome),
                logloss(p["home_market_probability"], outcome)
            )

            eligible.append(values)
            stats["eligible"] += 1

        except (ValueError, TypeError, OverflowError):
            stats["invalid_data"] += 1

    print("\n=== MARKETEDGE NFL GRADING V2 ===")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")

    for key, value in stats.items():
        print(f"{key}: {value}")

    print("Unique games:", len({
        row[2] for row in eligible
    }))

    if args.apply:
        with conn:
            conn.executemany("""
                INSERT OR IGNORE INTO prediction_grades (
                    prediction_snapshot_id,
                    graded_at,
                    game_result_id,
                    home_score,
                    away_score,
                    winner,
                    model_pick,
                    market_pick,
                    model_correct,
                    market_correct,
                    home_model_brier,
                    home_market_brier,
                    home_model_log_loss,
                    home_market_log_loss
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, eligible)

        print("Database grading transaction completed.")
    else:
        print("Database modified: NO")

    conn.close()


if __name__ == "__main__":
    main()
