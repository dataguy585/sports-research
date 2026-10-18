import io

import pandas as pd
import requests


START_RATING = 1500.0
K_FACTOR = 30.0
HOME_ADVANTAGE = 25.0

NFLVERSE_GAMES_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/schedules/games.csv"
)

EDGE_THRESHOLDS = [
    0.00,
    0.02,
    0.04,
    0.06,
    0.08,
    0.10,
    0.15,
]


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

    return (
        home_implied / total,
        away_implied / total,
    )


def american_profit(price):
    price = float(price)

    if price > 0:
        return price / 100.0

    return 100.0 / abs(price)


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
        & df["game_type"].isin(
            ["REG", "WC", "DIV", "CON", "SB"]
        )
    ].copy()

    return df.sort_values(
        ["gameday", "game_id"]
    )

def print_bucket_table(candidates, title):
    print()
    print(title)
    print(
        f"{'Edge':<10}"
        f"{'Bets':>7}"
        f"{'Wins':>7}"
        f"{'Win%':>9}"
        f"{'Units':>10}"
        f"{'ROI':>9}"
    )
    print("-" * 52)

    for threshold in EDGE_THRESHOLDS:
        bets = [
            row
            for row in candidates
            if row["edge"] >= threshold
        ]

        wins = 0
        profit = 0.0

        for bet in bets:
            if bet["won"]:
                wins += 1
                profit += american_profit(
                    bet["price"]
                )
            else:
                profit -= 1.0

        count = len(bets)

        win_pct = (
            wins / count
            if count
            else 0.0
        )

        roi = (
            profit / count
            if count
            else 0.0
        )

        print(
            f">={threshold * 100:>4.0f} pp"
            f"{count:>7}"
            f"{wins:>7}"
            f"{win_pct * 100:>8.2f}%"
            f"{profit:>+10.2f}"
            f"{roi * 100:>8.2f}%"
        )
def print_price_split(candidates, title):
    print()
    print(title)

    for label, selector in [
        (
            "FAVORITES",
            lambda row: row["price"] < 0,
        ),
        (
            "UNDERDOGS",
            lambda row: row["price"] > 0,
        ),
    ]:
        group = [
            row
            for row in candidates
            if selector(row)
        ]

        print()
        print(f"--- {label} ---")
        print(
            f"{'Edge':<10}"
            f"{'Bets':>7}"
            f"{'Wins':>7}"
            f"{'Win%':>9}"
            f"{'AvgOdds':>10}"
            f"{'Units':>10}"
            f"{'ROI':>9}"
        )
        print("-" * 62)

        for threshold in EDGE_THRESHOLDS:
            bets = [
                row
                for row in group
                if row["edge"] >= threshold
            ]

            wins = 0
            profit = 0.0

            for bet in bets:
                if bet["won"]:
                    wins += 1
                    profit += american_profit(
                        bet["price"]
                    )
                else:
                    profit -= 1.0

            count = len(bets)

            win_pct = (
                wins / count
                if count
                else 0.0
            )

            roi = (
                profit / count
                if count
                else 0.0
            )

            avg_odds = (
                sum(
                    bet["price"]
                    for bet in bets
                ) / count
                if count
                else 0.0
            )

            print(
                f">={threshold * 100:>4.0f} pp"
                f"{count:>7}"
                f"{wins:>7}"
                f"{win_pct * 100:>8.2f}%"
                f"{avg_odds:>+10.0f}"
                f"{profit:>+10.2f}"
                f"{roi * 100:>8.2f}%"
            )
def main():
    games = load_games()

    ratings = {}
    candidates = []

    for _, game in games.iterrows():
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

        elo_home = expected_probability(
            home_rating + HOME_ADVANTAGE,
            away_rating,
        )

        elo_away = 1.0 - elo_home

        if game["home_score"] > game["away_score"]:
            home_result = 1.0
        elif game["home_score"] < game["away_score"]:
            home_result = 0.0
        else:
            home_result = 0.5

        if (
            int(game["season"]) == 2026
            and home_result in (0.0, 1.0)
            and pd.notna(game["home_moneyline"])
            and pd.notna(game["away_moneyline"])
        ):
            home_implied = american_to_implied(
                game["home_moneyline"]
            )

            away_implied = american_to_implied(
                game["away_moneyline"]
            )

            market_home, market_away = remove_vig(
                home_implied,
                away_implied,
            )

            home_edge = elo_home - market_home
            away_edge = elo_away - market_away

            if home_edge >= away_edge:
                side = "HOME"
                team = home
                edge = home_edge
                price = float(
                    game["home_moneyline"]
                )
                won = home_result == 1.0
                market_probability = market_home
                model_probability = elo_home
            else:
                side = "AWAY"
                team = away
                edge = away_edge
                price = float(
                    game["away_moneyline"]
                )
                won = home_result == 0.0
                market_probability = market_away
                model_probability = elo_away

            candidates.append(
                 {
                     "game_id": game["game_id"],
                     "gameday": str(game["gameday"]),
                     "team": team,
                     "side": side,
                     "price": price,
                     "edge": edge,
                     "won": won,
                     "market_probability": market_probability,
                     "model_probability": model_probability,
                 }
             )
        rating_change = (
            K_FACTOR
            * (home_result - elo_home)
        )

        ratings[home] = (
            home_rating + rating_change
        )

        ratings[away] = (
            away_rating - rating_change
        )
    print("=== NFL ELO EDGE ANALYSIS ===")
    print("Validation season: 2026")
    print("Model: K=30 / Home Advantage=25")

    candidates.sort(
        key=lambda row: row["gameday"]
    )

    midpoint = len(candidates) // 2

    early = candidates[:midpoint]
    late = candidates[midpoint:]

    print_bucket_table(
        candidates,
        "=== FULL 2026 VALIDATION ===",
    )

    print_bucket_table(
        early,
        "=== EARLY 2026 HALF ===",
    )

    print_bucket_table(
        late,
        "=== LATE 2026 HALF ===",
    )
    print_price_split(
        candidates,
        "=== FAVORITE VS UNDERDOG SPLIT ===",
    )
    print_price_split(
        early,
        "=== EARLY 2026 FAVORITE VS UNDERDOG ===",
    )

    print_price_split(
        late,
        "=== LATE 2026 FAVORITE VS UNDERDOG ===",
    )

    print()
    print("=== LARGEST EDGES ===")

    candidates.sort(
        key=lambda row: row["edge"],
        reverse=True,
    )

    for row in candidates[:15]:
        result = (
            "WIN"
            if row["won"]
            else "LOSS"
        )

        print(
            f"{row['team']:25} "
            f"{row['price']:+.0f} | "
            f"Market {row['market_probability'] * 100:5.2f}% | "
            f"Elo {row['model_probability'] * 100:5.2f}% | "
            f"Edge {row['edge'] * 100:+5.2f} pp | "
            f"{result}"
        )


if __name__ == "__main__":
    main()
