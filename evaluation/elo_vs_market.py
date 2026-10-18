import io
import math

import pandas as pd
import requests


START_RATING = 1500.0

# Frozen from 2025 tuning only.
K_FACTOR = 30.0
HOME_ADVANTAGE = 25.0

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


def american_to_implied(price):
    if pd.isna(price):
        return None

    price = float(price)

    if price > 0:
        return 100.0 / (price + 100.0)

    if price < 0:
        return abs(price) / (abs(price) + 100.0)

    return None


def remove_vig(home_implied, away_implied):
    total = home_implied + away_implied

    if total <= 0:
        return None, None

    return (
        home_implied / total,
        away_implied / total,
    )


def brier(probability, result):
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

    if "game_type" in df.columns:
        df = df[
            df["game_type"].isin(
                ["REG", "WC", "DIV", "CON", "SB"]
            )
        ].copy()

    df = df.sort_values(
        ["gameday", "game_id"]
    )

    return df


def main():
    games = load_games()

    ratings = {}

    elo_brier = []
    elo_log = []

    market_brier = []
    market_log = []

    elo_correct = 0
    market_correct = 0

    evaluated = 0
    skipped_market = 0

    disagreements = []

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

        elo_home_prob = expected_probability(
            home_rating + HOME_ADVANTAGE,
            away_rating,
        )

        if game["home_score"] > game["away_score"]:
            home_result = 1.0
        elif game["home_score"] < game["away_score"]:
            home_result = 0.0
        else:
            home_result = 0.5

        season = int(game["season"])

        # Evaluate only untouched 2026 validation games.
        if season == 2026 and home_result in (0.0, 1.0):
            home_implied = american_to_implied(
                game["home_moneyline"]
            )

            away_implied = american_to_implied(
                game["away_moneyline"]
            )

            if (
                home_implied is None
                or away_implied is None
            ):
                skipped_market += 1

            else:
                market_home_prob, _ = remove_vig(
                    home_implied,
                    away_implied,
                )

                evaluated += 1

                elo_brier.append(
                    brier(
                        elo_home_prob,
                        home_result,
                    )
                )

                market_brier.append(
                    brier(
                        market_home_prob,
                        home_result,
                    )
                )

                elo_log.append(
                    log_loss(
                        elo_home_prob,
                        home_result,
                    )
                )

                market_log.append(
                    log_loss(
                        market_home_prob,
                        home_result,
                    )
                )

                actual_home = (
                    home_result == 1.0
                )

                if (
                    elo_home_prob >= 0.5
                ) == actual_home:
                    elo_correct += 1

                if (
                    market_home_prob >= 0.5
                ) == actual_home:
                    market_correct += 1

                disagreements.append(
                    {
                        "away": away,
                        "home": home,
                        "elo": elo_home_prob,
                        "market": market_home_prob,
                        "result": home_result,
                        "difference": (
                            elo_home_prob
                            - market_home_prob
                        ),
                    }
                )

        # Update Elo only after predicting this game.
        rating_change = (
            K_FACTOR
            * (home_result - elo_home_prob)
        )

        ratings[home] = (
            home_rating + rating_change
        )

        ratings[away] = (
            away_rating - rating_change
        )

    print("=== NFL ELO VS MARKET ===")
    print("Validation season: 2026")
    print(f"K factor: {K_FACTOR}")
    print(
        f"Home advantage: "
        f"{HOME_ADVANTAGE}"
    )
    print()

    print(f"Games evaluated: {evaluated}")
    print(
        "Games skipped for missing market odds: "
        f"{skipped_market}"
    )
    print()

    if not evaluated:
        print("No comparable market games found.")
        return

    elo_accuracy = (
        elo_correct / evaluated
    )

    market_accuracy = (
        market_correct / evaluated
    )

    avg_elo_brier = (
        sum(elo_brier) / len(elo_brier)
    )

    avg_market_brier = (
        sum(market_brier)
        / len(market_brier)
    )

    avg_elo_log = (
        sum(elo_log) / len(elo_log)
    )

    avg_market_log = (
        sum(market_log)
        / len(market_log)
    )

    print("                 Elo        Market")
    print("----------------------------------")
    print(
        f"Accuracy      "
        f"{elo_accuracy * 100:6.2f}%    "
        f"{market_accuracy * 100:6.2f}%"
    )
    print(
        f"Brier          "
        f"{avg_elo_brier:.4f}      "
        f"{avg_market_brier:.4f}"
    )
    print(
        f"Log loss       "
        f"{avg_elo_log:.4f}      "
        f"{avg_market_log:.4f}"
    )

    print()
    print("Difference, Elo minus Market:")
    print(
        f"Brier:    "
        f"{avg_elo_brier - avg_market_brier:+.4f}"
    )
    print(
        f"Log loss: "
        f"{avg_elo_log - avg_market_log:+.4f}"
    )

    disagreements.sort(
        key=lambda row: abs(
            row["difference"]
        ),
        reverse=True,
    )

    print()
    print(
        "=== BIGGEST ELO / MARKET "
        "DISAGREEMENTS ==="
    )

    for row in disagreements[:10]:
        winner = (
            row["home"]
            if row["result"] == 1.0
            else row["away"]
        )

        print()
        print(
            f"{row['away']} @ "
            f"{row['home']}"
        )
        print(
            f"  Elo home:    "
            f"{row['elo'] * 100:.2f}%"
        )
        print(
            f"  Market home: "
            f"{row['market'] * 100:.2f}%"
        )
        print(
            f"  Difference:  "
            f"{row['difference'] * 100:+.2f} pp"
        )
        print(
            f"  Winner:      "
            f"{winner}"
        )


if __name__ == "__main__":
    main()
