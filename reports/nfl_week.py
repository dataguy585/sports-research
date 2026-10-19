from __future__ import annotations

from functools import lru_cache

import pandas as pd


SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/schedules/games.csv"
)

TEAM_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


@lru_cache(maxsize=1)
def load_schedule():
    return pd.read_csv(SCHEDULE_URL)


def normalize_team(team):
    return TEAM_ABBR.get(
        team,
        team,
    )


def get_nfl_week(
    away_team,
    home_team,
    season,
):
    df = load_schedule()

    away_team = normalize_team(away_team)
    home_team = normalize_team(home_team)

    matches = df[
        (df["season"] == season)
        & (df["game_type"] == "REG")
        & (df["away_team"] == away_team)
        & (df["home_team"] == home_team)
    ]

    if matches.empty:
        return None

    weeks = (
        matches["week"]
        .dropna()
        .astype(int)
        .unique()
    )

    if len(weeks) != 1:
        return None

    return int(weeks[0])
