from __future__ import annotations

import argparse
import math
import sqlite3
from datetime import datetime, timezone

from database.db import DB_PATH


EPSILON = 1e-15


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def brier_score(probability, outcome):
    return (probability - outcome) ** 2


def log_loss(probability, outcome):
    probability = min(
        max(probability, EPSILON),
        1 - EPSILON,
    )

    return -(
        outcome * math.log(probability)
        + (1 - outcome) * math.log(1 - probability)
    )


def grade_predictions(run_id=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            ps.*,
            gr.id AS game_result_id,
            gr.home_score,
            gr.away_score,
            gr.winner,
            gr.status AS game_status
        FROM prediction_snapshots AS ps
        JOIN game_results AS gr
          ON gr.sport = ps.sport
         AND gr.event_id = ps.event_id
        LEFT JOIN prediction_grades AS pg
          ON pg.prediction_snapshot_id = ps.id
        WHERE gr.status = 'COMPLETED'
          AND pg.id IS NULL
    """

    params = []

    if run_id is not None:
        query += """
          AND ps.collection_run_id = ?
        """
        params.append(run_id)

    query += """
        ORDER BY ps.commence_time, ps.id
    """

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    if not rows:
        print("No ungraded completed predictions found.")
        conn.close()
        return

    inserted = 0

    for row in rows:
        home = row["home_team"]
        away = row["away_team"]
        winner = row["winner"]

        home_model_probability = (
            row["home_model_probability"]
        )
        home_market_probability = (
            row["home_market_probability"]
        )

        model_pick = (
            home
            if row["home_model_probability"]
            >= row["away_model_probability"]
            else away
        )

        market_pick = (
            home
            if row["home_market_probability"]
            >= row["away_market_probability"]
            else away
        )

        if winner == "TIE":
            model_correct = None
            market_correct = None
            home_outcome = 0.5
        else:
            model_correct = int(
                model_pick == winner
            )
            market_correct = int(
                market_pick == winner
            )
            home_outcome = int(
                winner == home
            )

        model_brier = brier_score(
            home_model_probability,
            home_outcome,
        )

        market_brier = brier_score(
            home_market_probability,
            home_outcome,
        )

        model_log_loss = log_loss(
            home_model_probability,
            home_outcome,
        )

        market_log_loss = log_loss(
            home_market_probability,
            home_outcome,
        )

        conn.execute(
            """
            INSERT INTO prediction_grades (
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
                home_market_log_loss,
                closing_collection_run_id,
                closing_home_market_probability,
                closing_away_market_probability,
                model_clv_pp,
                market_move_toward_model_pp,
                hypothetical_side,
                hypothetical_price,
                hypothetical_result,
                hypothetical_profit_units
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                NULL, NULL, NULL, NULL, NULL,
                NULL, NULL, NULL, NULL
            )
            """,
            (
                row["id"],
                utc_now(),
                row["game_result_id"],
                row["home_score"],
                row["away_score"],
                winner,
                model_pick,
                market_pick,
                model_correct,
                market_correct,
                model_brier,
                market_brier,
                model_log_loss,
                market_log_loss,
            ),
        )

        inserted += 1

        print(
            f"GRADED {away} @ {home} | "
            f"Winner: {winner} | "
            f"Model: {model_pick} | "
            f"Market: {market_pick}"
        )

    conn.commit()
    conn.close()

    print()
    print("Prediction grading complete.")
    print(f"Inserted: {inserted}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Grade completed NFL prediction snapshots."
        )
    )

    parser.add_argument(
        "--run",
        type=int,
        help=(
            "Optional prediction collection run ID "
            "to grade."
        ),
    )

    args = parser.parse_args()

    grade_predictions(
        run_id=args.run,
    )


if __name__ == "__main__":
    main()
