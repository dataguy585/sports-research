import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from database.results import upsert_game_result


load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_scores(game):
    scores = game.get("scores") or []

    score_map = {
        item.get("name"): item.get("score")
        for item in scores
        if item.get("name") is not None
    }

    home_team = game.get("home_team")
    away_team = game.get("away_team")

    home_score = score_map.get(home_team)
    away_score = score_map.get(away_team)

    if home_score is not None:
        home_score = int(home_score)

    if away_score is not None:
        away_score = int(away_score)

    return home_score, away_score


def derive_status(game):
    if game.get("completed") is True:
        return "COMPLETED"

    if game.get("scores"):
        return "IN_PROGRESS"

    return "SCHEDULED"


def collect_results(sport, days_from=1):
    if not API_KEY:
        print("STATUS: CONFIGURATION_ERROR")
        print("ODDS_API_KEY is missing from .env")
        return "CONFIGURATION_ERROR"

    url = f"{BASE_URL}/sports/{sport}/scores/"

    params = {
        "apiKey": API_KEY,
        "daysFrom": days_from,
        "dateFormat": "iso",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        response.raise_for_status()
        games = response.json()

    except requests.RequestException as exc:
        print("STATUS: DATA_SOURCE_FAILURE")
        print(str(exc).replace(API_KEY, "[REDACTED]"))
        return "DATA_SOURCE_FAILURE"

    completed_count = 0
    in_progress_count = 0
    scheduled_count = 0

    for game in games:
        status = derive_status(game)

        home_score, away_score = parse_scores(game)

        if status == "COMPLETED":
            completed_count += 1
        elif status == "IN_PROGRESS":
            in_progress_count += 1
        else:
            scheduled_count += 1

        upsert_game_result(
            sport=game.get("sport_key", sport),
            event_id=game["id"],
            commence_time=game.get("commence_time"),
            home_team=game["home_team"],
            away_team=game["away_team"],
            home_score=home_score,
            away_score=away_score,
            status=status,
            completed_at=utc_now() if status == "COMPLETED" else None,
            source="the_odds_api_scores",
            source_payload=game,
        )

    print("STATUS: VALID")
    print(f"Sport: {sport}")
    print(f"Games received: {len(games)}")
    print(f"Completed: {completed_count}")
    print(f"In progress: {in_progress_count}")
    print(f"Scheduled: {scheduled_count}")

    remaining = response.headers.get("x-requests-remaining")
    used = response.headers.get("x-requests-used")
    last = response.headers.get("x-requests-last")

    if remaining is not None:
        print(f"API requests remaining: {remaining}")

    if used is not None:
        print(f"API requests used: {used}")

    if last is not None:
        print(f"API request cost: {last}")

    return "VALID"
