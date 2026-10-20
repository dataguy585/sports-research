from __future__ import annotations

from functools import lru_cache
from datetime import datetime
from zoneinfo import ZoneInfo

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


def get_current_nfl_week(
    season,
    now=None,
):
    df = load_schedule()

    if now is None:
        now = datetime.now(
            ZoneInfo("America/New_York")
        )

    games = df[
        (df["season"] == season)
        & (df["game_type"] == "REG")
    ].copy()

    games = games[
        games["gameday"].notna()
        & games["gametime"].notna()
        & games["week"].notna()
    ].copy()

    games["kickoff"] = pd.to_datetime(
        games["gameday"].astype(str)
        + " "
        + games["gametime"].astype(str),
        errors="coerce",
    )

    games = games[
        games["kickoff"].notna()
    ].copy()

    games["kickoff"] = (
        games["kickoff"]
        .dt.tz_localize(
            "America/New_York",
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
    )

    upcoming = games[
        games["kickoff"] >= now
    ].sort_values("kickoff")

    if not upcoming.empty:
        return int(
            upcoming.iloc[0]["week"]
        )

    latest = games.sort_values(
        "kickoff"
    ).tail(1)

    if latest.empty:
        return None

    return int(
        latest.iloc[0]["week"]
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
