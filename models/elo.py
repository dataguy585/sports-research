from datetime import datetime, timedelta
import math
import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")

MODEL_VERSION = "NFL-ELO-v1.1"

START_RATING = 1500.0
K_FACTOR = 30.0
HOME_ADVANTAGE = 25.0
OFFSEASON_REGRESSION = 0.50

# Conservative buffer so we do not accidentally train on
# a game that had started but was not truly finished when
# the market snapshot was taken.
COMPLETION_BUFFER_HOURS = 6


def expected_probability(rating_a, rating_b):
    return 1.0 / (
        1.0 + 10 ** ((rating_b - rating_a) / 400.0)
    )


def load_run(run_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        return conn.execute(
            """
            SELECT
                id,
                retrieved_at,
                sport
            FROM collection_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
def build_ratings(sport, snapshot_time):
    snapshot_dt = datetime.fromisoformat(snapshot_time)

    cutoff = snapshot_dt - timedelta(
        hours=COMPLETION_BUFFER_HOURS
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        games = conn.execute(
            """
            SELECT
                event_id,
                commence_time,
                home_team,
                away_team,
                home_score,
                away_score,
                source
            FROM game_results
            WHERE sport = ?
              AND source = 'nflverse'
              AND status = 'COMPLETED'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND commence_time IS NOT NULL
              AND commence_time <= ?
            ORDER BY commence_time, event_id
            """,
            (
                sport,
                cutoff.isoformat(),
            ),
        ).fetchall()

    ratings = {}
    current_season = None

    for game in games:
        event_id = game["event_id"]

        # nflverse IDs are stored as:
        # nflverse:2025_01_DAL_PHI
        season = int(
            event_id.split(":", 1)[1].split("_", 1)[0]
        )

        if current_season is None:
            current_season = season

        elif season != current_season:
            for team in ratings:
                ratings[team] = (
                    START_RATING
                    + (
                        ratings[team]
                        - START_RATING
                    )
                    * (1.0 - OFFSEASON_REGRESSION)
                )

            current_season = season

        home = game["home_team"]
        away = game["away_team"]

        home_rating = ratings.get(
            home,
            START_RATING,
        )

        away_rating = ratings.get(
            away,
            START_RATING,
        )

        adjusted_home_rating = (
            home_rating + HOME_ADVANTAGE
        )

        home_expected = expected_probability(
            adjusted_home_rating,
            away_rating,
        )

        if game["home_score"] > game["away_score"]:
            home_result = 1.0
        elif game["home_score"] < game["away_score"]:
            home_result = 0.0
        else:
            home_result = 0.5

        rating_change = (
            K_FACTOR
            * (home_result - home_expected)
        )

        ratings[home] = (
            home_rating + rating_change
        )

        ratings[away] = (
            away_rating - rating_change
        )

    return ratings, games

def predict_run(run_id):
    run = load_run(run_id)

    if run is None:
        raise ValueError(
            f"Collection run {run_id} not found"
        )

    ratings, training_games = build_ratings(
        run["sport"],
        run["retrieved_at"],
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        events = conn.execute(
            """
            SELECT DISTINCT
                event_id,
                commence_time,
                home_team,
                away_team
            FROM odds_snapshots
            WHERE collection_run_id = ?
            ORDER BY commence_time, event_id
            """,
            (run_id,),
        ).fetchall()

    predictions = []

    for event in events:
        home = event["home_team"]
        away = event["away_team"]

        home_rating = ratings.get(
            home,
            START_RATING,
        )

        away_rating = ratings.get(
            away,
            START_RATING,
        )

        home_probability = expected_probability(
            home_rating + HOME_ADVANTAGE,
            away_rating,
        )

        away_probability = 1.0 - home_probability

        predictions.append(
            {
                "collection_run_id": run_id,
                "sport": run["sport"],
                "event_id": event["event_id"],
                "commence_time": event["commence_time"],
                "home_team": home,
                "away_team": away,
                "outcome_name": home,
                "model_probability": home_probability,
                "model_version": MODEL_VERSION,
                "home_rating": home_rating,
                "away_rating": away_rating,
                "training_game_count": len(
                    training_games
                ),
            }
        )

        predictions.append(
            {
                "collection_run_id": run_id,
                "sport": run["sport"],
                "event_id": event["event_id"],
                "commence_time": event["commence_time"],
                "home_team": home,
                "away_team": away,
                "outcome_name": away,
                "model_probability": away_probability,
                "model_version": MODEL_VERSION,
                "home_rating": home_rating,
                "away_rating": away_rating,
                "training_game_count": len(
                    training_games
                ),
            }
        )

    return predictions
