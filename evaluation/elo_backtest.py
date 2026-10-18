import io
import math

import pandas as pd
import requests


START_RATING = 1500.0

K_VALUES = [10.0, 15.0, 20.0, 25.0, 30.0]
HOME_ADVANTAGE_VALUES = [25.0, 40.0, 50.0, 60.0, 75.0]

NFLVERSE_GAMES_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/schedules/games.csv"
)


TEAM_MAP = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "JAC": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams",
    "LAR": "Los Angeles Rams",
    "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}


def team_name(code):
    return TEAM_MAP.get(str(code), str(code))


def expected_probability(rating_a, rating_b):
    return 1.0 / (
        1.0 + 10 ** ((rating_b - rating_a) / 400.0)
    )


def brier_score(probability, result):
    return (probability - result) ** 2


def log_loss(probability, result):
    probability = max(
        min(probability, 0.999999),
        0.000001,
    )

    return -(
        result * math.log(probability)
        + (1.0 - result) * math.log(1.0 - probability)
    )


def load_games():
    response = requests.get(
        NFLVERSE_GAMES_URL,
        timeout=60,
    )
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        low_memory=False,
    )

    df = df[
        df["season"].isin([2025, 2026])
        & df["home_score"].notna()
        & df["away_score"].notna()
    ].copy()

    df = df[
        df["game_type"].isin(
            ["REG", "WC", "DIV", "CON", "SB"]
        )
    ].copy()

    df = df.sort_values(
        ["gameday", "game_id"]
    )

    return df


def evaluate_configuration(
    games,
    k_factor,
    home_advantage,
):
    ratings = {}

    tuning_correct = 0
    tuning_total = 0
    tuning_brier = []
    tuning_log = []

    validation_correct = 0
    validation_total = 0
    validation_brier = []
    validation_log = []

    for _, game in games.iterrows():
        home = team_name(game["home_team"])
        away = team_name(game["away_team"])

        home_rating = ratings.get(
            home,
            START_RATING,
        )

        away_rating = ratings.get(
            away,
            START_RATING,
        )

        home_probability = expected_probability(
            home_rating + home_advantage,
            away_rating,
        )

        if game["home_score"] > game["away_score"]:
            home_result = 1.0
        elif game["home_score"] < game["away_score"]:
            home_result = 0.0
        else:
            home_result = 0.5

        season = int(game["season"])

        if home_result in (0.0, 1.0):
            predicted_home = (
                home_probability >= 0.5
            )

            actual_home = (
                home_result == 1.0
            )

            if season == 2025:
                tuning_total += 1

                if predicted_home == actual_home:
                    tuning_correct += 1

                tuning_brier.append(
                    brier_score(
                        home_probability,
                        home_result,
                    )
                )

                tuning_log.append(
                    log_loss(
                        home_probability,
                        home_result,
                    )
                )

            elif season == 2026:
                validation_total += 1

                if predicted_home == actual_home:
                    validation_correct += 1

                validation_brier.append(
                    brier_score(
                        home_probability,
                        home_result,
                    )
                )

                validation_log.append(
                    log_loss(
                        home_probability,
                        home_result,
                    )
                )

        # Update only after predicting the game.
        rating_change = (
            k_factor
            * (home_result - home_probability)
        )

        ratings[home] = (
            home_rating + rating_change
        )

        ratings[away] = (
            away_rating - rating_change
        )

    return {
        "k_factor": k_factor,
        "home_advantage": home_advantage,

        "tuning_games": tuning_total,
        "tuning_accuracy": (
            tuning_correct / tuning_total
        ),
        "tuning_brier": (
            sum(tuning_brier)
            / len(tuning_brier)
        ),
        "tuning_log_loss": (
            sum(tuning_log)
            / len(tuning_log)
        ),

        "validation_games": validation_total,
        "validation_accuracy": (
            validation_correct
            / validation_total
        ),
        "validation_brier": (
            sum(validation_brier)
            / len(validation_brier)
        ),
        "validation_log_loss": (
            sum(validation_log)
            / len(validation_log)
        ),
    }


def main():
    games = load_games()

    results = []

    for k_factor in K_VALUES:
        for home_advantage in HOME_ADVANTAGE_VALUES:
            results.append(
                evaluate_configuration(
                    games,
                    k_factor,
                    home_advantage,
                )
            )

    results.sort(
        key=lambda row: (
            row["tuning_brier"],
            row["tuning_log_loss"],
        )
    )

    print("=== NFL ELO TEMPORAL VALIDATION ===")
    print("Tuning season:     2025")
    print("Validation season: 2026")
    print(
        f"Configurations tested: "
        f"{len(results)}"
    )
    print()

    print(
        f"{'Rank':<5}"
        f"{'K':>6}"
        f"{'Home':>7}"
        f"{'2025 Brier':>13}"
        f"{'2025 Log':>11}"
        f"{'2026 Brier':>13}"
        f"{'2026 Log':>11}"
    )

    print("-" * 66)

    for index, row in enumerate(
        results,
        start=1,
    ):
        print(
            f"{index:<5}"
            f"{row['k_factor']:>6.1f}"
            f"{row['home_advantage']:>7.1f}"
            f"{row['tuning_brier']:>13.4f}"
            f"{row['tuning_log_loss']:>11.4f}"
            f"{row['validation_brier']:>13.4f}"
            f"{row['validation_log_loss']:>11.4f}"
        )

    best = results[0]

    print()
    print("=== FROZEN CONFIG FROM 2025 ===")
    print(
        f"K factor:       "
        f"{best['k_factor']}"
    )
    print(
        f"Home advantage: "
        f"{best['home_advantage']}"
    )

    print()
    print("2025 tuning:")
    print(
        f"  Games:    "
        f"{best['tuning_games']}"
    )
    print(
        f"  Accuracy: "
        f"{best['tuning_accuracy'] * 100:.2f}%"
    )
    print(
        f"  Brier:    "
        f"{best['tuning_brier']:.4f}"
    )
    print(
        f"  Log loss: "
        f"{best['tuning_log_loss']:.4f}"
    )

    print()
    print("2026 validation:")
    print(
        f"  Games:    "
        f"{best['validation_games']}"
    )
    print(
        f"  Accuracy: "
        f"{best['validation_accuracy'] * 100:.2f}%"
    )
    print(
        f"  Brier:    "
        f"{best['validation_brier']:.4f}"
    )
    print(
        f"  Log loss: "
        f"{best['validation_log_loss']:.4f}"
    )


if __name__ == "__main__":
    main()
