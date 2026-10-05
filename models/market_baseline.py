import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")

MODEL_VERSION = "MARKET-BASELINE-v0"


def load_market_baseline(collection_run_id):
    """
    Return one baseline model row per benchmark outcome.

    v0 intentionally sets model_probability equal to the
    no-vig market consensus probability.

    This is NOT intended to claim predictive edge.
    It exists to validate the downstream decision,
    settlement, and evaluation pipeline.
    """

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                mb.collection_run_id,
                cr.sport,
                mb.snapshot_time,
                mb.event_id,
                mb.home_team,
                mb.away_team,
                mb.outcome_name,
                mb.consensus_probability
            FROM market_benchmarks mb
            JOIN collection_runs cr
              ON cr.id = mb.collection_run_id
            WHERE mb.collection_run_id = ?
            ORDER BY
                mb.event_id,
                mb.outcome_name
            """,
            (collection_run_id,),
        ).fetchall()

    results = []

    for row in rows:
        results.append(
            {
                "collection_run_id": row["collection_run_id"],
                "sport": row["sport"],
                "snapshot_time": row["snapshot_time"],
                "event_id": row["event_id"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "outcome_name": row["outcome_name"],
                "market_probability": row["consensus_probability"],
                "model_probability": row["consensus_probability"],
                "model_version": MODEL_VERSION,
            }
        )

    return results
