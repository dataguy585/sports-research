import argparse
import io

import pandas as pd
import requests

from database.results import upsert_game_result


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
    return TEAM_MAP.get(code, code)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical NFL results from nflverse"
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        required=True,
        help="NFL seasons to backfill",
    )

    args = parser.parse_args()

    print("=== NFL HISTORICAL RESULT BACKFILL ===")
    print(
        "Seasons:",
        ", ".join(str(season) for season in args.seasons),
    )

    response = requests.get(
        NFLVERSE_GAMES_URL,
        timeout=60,
    )
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        low_memory=False,
    )

    df = df[df["season"].isin(args.seasons)].copy()

    # Only completed games with actual final scores.
    df = df[
        df["home_score"].notna()
        & df["away_score"].notna()
    ].copy()

    # Elo v1 should train on regular season + postseason,
    # but not preseason.
    if "game_type" in df.columns:
        df = df[
            df["game_type"].isin(
                ["REG", "WC", "DIV", "CON", "SB"]
            )
        ].copy()

    inserted = 0

    for _, game in df.iterrows():
        game_id = str(game["game_id"])

        home_team = team_name(str(game["home_team"]))
        away_team = team_name(str(game["away_team"]))

        home_score = int(game["home_score"])
        away_score = int(game["away_score"])

        game_date = str(game["gameday"])

        commence_time = game_date

        if "gametime" in df.columns and pd.notna(game["gametime"]):
            commence_time = (
                f"{game_date}T{str(game['gametime'])}:00"
            )

        upsert_game_result(
            sport="americanfootball_nfl",
            event_id=f"nflverse:{game_id}",
            commence_time=commence_time,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            status="COMPLETED",
            completed_at=None,
            source="nflverse",
            source_payload={
                "game_id": game_id,
                "season": int(game["season"]),
                "week": (
                    int(game["week"])
                    if pd.notna(game["week"])
                    else None
                ),
                "game_type": game.get("game_type"),
                "gameday": game_date,
                "home_team": str(game["home_team"]),
                "away_team": str(game["away_team"]),
                "home_score": home_score,
                "away_score": away_score,
            },
        )

        inserted += 1

    print("STATUS: VALID")
    print(f"Completed games processed: {inserted}")


if __name__ == "__main__":
    main()
