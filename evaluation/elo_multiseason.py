import io
import math

import pandas as pd
import requests


START_RATING = 1500.0

K_VALUES = [10.0, 15.0, 20.0, 25.0, 30.0]
HOME_ADVANTAGE_VALUES = [25.0, 40.0, 50.0, 60.0, 75.0]

REGRESSION_VALUES = [
    0.00,
    0.25,
    0.50,
    0.75,
    1.00,
]

NFLVERSE_GAMES_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/schedules/games.csv"
)


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
        df["season"].isin([2024, 2025, 2026])
        & df["home_score"].notna()
        & df["away_score"].notna()
        & df["game_type"].isin(
            ["REG", "WC", "DIV", "CON", "SB"]
        )
    ].copy()

    return df.sort_values(
        ["gameday", "game_id"]
    )


def evaluate_configuration(
    games,
    k_factor,
    home_advantage,
    offseason_regression,
):
    ratings = {}
    current_season = None
    stats = {
        2024: {
            "correct": 0,
            "total": 0,
            "brier": [],
            "log": [],
        },
        2025: {
            "correct": 0,
            "total": 0,
            "brier": [],
            "log": [],
        },
        2026: {
            "correct": 0,
            "total": 0,
            "brier": [],
            "log": [],
        },
    }

    for _, game in games.iterrows():
        season = int(game["season"])
               
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
                    * (1.0 - offseason_regression)
                )

            current_season = season
        home = str(game["home_team"])
        away = str(game["away_team"])

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

        if (
            season in stats
            and home_result in (0.0, 1.0)
        ):
            bucket = stats[season]

            bucket["total"] += 1

            predicted_home = (
                home_probability >= 0.5
            )

            actual_home = (
                home_result == 1.0
            )

            if predicted_home == actual_home:
                bucket["correct"] += 1

            bucket["brier"].append(
                brier_score(
                    home_probability,
                    home_result,
                )
            )

            bucket["log"].append(
                log_loss(
                    home_probability,
                    home_result,
                )
            )

        # Walk-forward update only after prediction.
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

    result = {
        "k_factor": k_factor,
        "home_advantage": home_advantage,
        "offseason_regression": offseason_regression,
    }

    for season, bucket in stats.items():
        result[f"{season}_games"] = bucket["total"]

        result[f"{season}_accuracy"] = (
            bucket["correct"] / bucket["total"]
            if bucket["total"]
            else 0.0
        )

        result[f"{season}_brier"] = (
            sum(bucket["brier"])
            / len(bucket["brier"])
        )

        result[f"{season}_log"] = (
            sum(bucket["log"])
            / len(bucket["log"])
        )

    return result


def main():
    games = load_games()

    results = []
    for k_factor in K_VALUES:
        for home_advantage in HOME_ADVANTAGE_VALUES:
            for offseason_regression in REGRESSION_VALUES:
                results.append(
                    evaluate_configuration(
                        games,
                        k_factor,
                        home_advantage,
                        offseason_regression,
                    )
                )
    # Parameter selection uses 2024 ONLY.
    # Stage 1:
    # Select K and home advantage using 2024 only.
    kh_candidates = {}

    for row in results:
        key = (
            row["k_factor"],
            row["home_advantage"],
        )

        if key not in kh_candidates:
            kh_candidates[key] = row

    best_kh = min(
        kh_candidates.values(),
        key=lambda row: (
            row["2024_brier"],
            row["2024_log"],
        ),
    )

    selected_k = best_kh["k_factor"]
    selected_home = best_kh["home_advantage"]

    # Stage 2:
    # With K/H frozen, select offseason regression
    # using 2025 only.
    regression_candidates = [
        row
        for row in results
        if row["k_factor"] == selected_k
        and row["home_advantage"] == selected_home
    ]

    best = min(
        regression_candidates,
        key=lambda row: (
            row["2025_brier"],
            row["2025_log"],
        ),
    )

    # Keep the full table sorted by 2024 performance for display.
    results.sort(
        key=lambda row: (
            row["2024_brier"],
            row["2024_log"],
            row["offseason_regression"],
        )
    )

    print("=== NFL ELO MULTI-SEASON ROBUSTNESS ===")
    print("Parameter tuning: 2024")
    print("Validation #1:    2025")
    print("Validation #2:    2026")
    print()
    print(f"Configurations tested: {len(results)}")
    print()

    print(
        f"{'Rank':<5}"
        f"{'K':>6}"
        f"{'Home':>7}"
        f"{'Reg':>7}"
        f"{'2024 Brier':>13}"
        f"{'2025 Brier':>13}"
        f"{'2026 Brier':>13}"
    )

    print("-" * 64)

    for rank, row in enumerate(
        results,
        start=1,
    ):
        print(
            f"{rank:<5}"
            f"{row['k_factor']:>6.1f}"
            f"{row['home_advantage']:>7.1f}"
            f"{row['offseason_regression']:>7.2f}"
            f"{row['2024_brier']:>13.4f}"
            f"{row['2025_brier']:>13.4f}"
            f"{row['2026_brier']:>13.4f}"
        )

    print()
    print("=== STAGED MODEL SELECTION ===")
    print(
        f"2024 selected K/Home: "
        f"{selected_k} / {selected_home}"
    )
    print(
        f"2025 selected regression: "
        f"{best['offseason_regression']:.2f}"
    )
    print(
        f"K factor:             "
        f"{best['k_factor']}"
    )
    print(
        f"Home advantage:       "
        f"{best['home_advantage']}"
    )
    print(
        f"Offseason regression: "
        f"{best['offseason_regression']:.2f}"
    )

    for season in [2024, 2025, 2026]:
        print()
        print(f"{season}:")
        print(
            f"  Games:    "
            f"{best[f'{season}_games']}"
        )
        print(
            f"  Accuracy: "
            f"{best[f'{season}_accuracy'] * 100:.2f}%"
        )
        print(
            f"  Brier:    "
            f"{best[f'{season}_brier']:.4f}"
        )
        print(
            f"  Log loss: "
            f"{best[f'{season}_log']:.4f}"
        )

if __name__ == "__main__":
    main()
