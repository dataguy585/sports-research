from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import math
import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")

MODEL_VERSION = "NFL-ELO-v1.2"

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

    snapshot_dt = datetime.fromisoformat(snapshot_time)

def build_ratings(sport, snapshot_time):
    eastern = ZoneInfo("America/New_York")

    snapshot_dt = datetime.fromisoformat(
        snapshot_time.replace("Z", "+00:00")
    )

    if snapshot_dt.tzinfo is None:
        raise ValueError("Snapshot time must include timezone")

    snapshot_utc = snapshot_dt.astimezone(timezone.utc)

    cutoff = snapshot_utc - timedelta(
        hours=COMPLETION_BUFFER_HOURS
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        candidates = conn.execute(
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
            """,
            (sport,),
        ).fetchall()

    eligible = []

    for game in candidates:
        local = datetime.fromisoformat(
            game["commence_time"]
        )

        if local.tzinfo is not None:
            raise ValueError(
                f"Unexpected timezone: {game['event_id']}"
            )

        kickoff_utc = local.replace(
            tzinfo=eastern
        ).astimezone(timezone.utc)

        if kickoff_utc <= cutoff:
            eligible.append((kickoff_utc, game))

    eligible.sort(
        key=lambda item: (
            item[0],
            item[1]["event_id"]
        )
    )

    ratings = {}
    current_season = None
    training_games = []

    for kickoff_utc, game in eligible:
        event_id = game["event_id"]

        season = int(
            event_id.split(":", 1)[1].split("_", 1)[0]
        )

        if current_season is None:
            current_season = season

        elif season != current_season:
            for team in ratings:
                ratings[team] = (
                    START_RATING
                    + (ratings[team] - START_RATING)
                    * (1.0 - OFFSEASON_REGRESSION)
                )

            current_season = season

        home = game["home_team"]
        away = game["away_team"]

        home_rating = ratings.get(home, START_RATING)
        away_rating = ratings.get(away, START_RATING)

        home_expected = expected_probability(
            home_rating + HOME_ADVANTAGE,
            away_rating
        )

        if game["home_score"] > game["away_score"]:
            home_result = 1.0
        elif game["home_score"] < game["away_score"]:
            home_result = 0.0
        else:
            home_result = 0.5

        change = K_FACTOR * (home_result - home_expected)

        ratings[home] = home_rating + change
        ratings[away] = away_rating - change

        training_games.append(game)

    return ratings, training_games

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
