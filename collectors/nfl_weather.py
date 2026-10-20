from __future__ import annotations

import sqlite3

from reports.nfl_week import get_current_nfl_week
from database.db import DB_PATH
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from reports.nfl_venues import (
    get_stadium_location,
    normalize_roof,
    weather_relevant,
)


SEASON = 2026

WEEK = get_current_nfl_week(SEASON)

if WEEK is None:
    raise RuntimeError(
        f"Unable to determine current NFL week "
        f"for season {SEASON}."
    )

SCHEDULE_URL = (
    "https://github.com/nflverse/"
    "nflverse-data/releases/download/"
    "schedules/games.csv"
)

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
)

RAW_DIR = Path(
    "data/raw/weather/nfl"
)


def fetch_weather(
    latitude,
    longitude,
    timezone_name,
    game_date,
):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(
            [
                "temperature_2m",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
            ]
        ),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": timezone_name,
        "start_date": game_date,
        "end_date": game_date,
    }

    url = (
        WEATHER_URL
        + "?"
        + urlencode(params)
    )

    with urlopen(
        url,
        timeout=30,
    ) as response:
        return json.load(response)
def get_local_kickoff(
    gameday,
    gametime,
    stadium_timezone,
):
    kickoff_et = datetime.strptime(
        f"{gameday} {gametime}",
        "%Y-%m-%d %H:%M",
    ).replace(
        tzinfo=ZoneInfo(
            "America/New_York"
        )
    )

    return kickoff_et.astimezone(
        ZoneInfo(stadium_timezone)
    )


def get_kickoff_weather(
    payload,
    local_kickoff,
):
    hourly = payload.get(
        "hourly",
        {}
    )

    times = hourly.get(
        "time",
        []
    )

    if not times:
        return None

    target_hour = local_kickoff.replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    if local_kickoff.minute >= 30:
        target_hour = (
            target_hour
            + pd.Timedelta(hours=1)
        )

    target_text = target_hour.strftime(
        "%Y-%m-%dT%H:%M"
    )

    try:
        index = times.index(
            target_text
        )
    except ValueError:
        return None

    return {
        "forecast_time": target_text,
        "temperature_f": hourly[
            "temperature_2m"
        ][index],
        "precipitation_in": hourly[
            "precipitation"
        ][index],
        "weather_code": hourly[
            "weather_code"
        ][index],
        "wind_mph": hourly[
            "wind_speed_10m"
        ][index],
        "wind_gust_mph": hourly[
            "wind_gusts_10m"
        ][index],
    }

def main():
    retrieved_at = datetime.now(
        timezone.utc
    )

    print("=== NFL WEATHER COLLECTOR ===")
    print(f"Season: {SEASON}")
    print(f"Week:   {WEEK}")
    print()

    schedule = pd.read_csv(
        SCHEDULE_URL
    )

    games = schedule[
        (schedule["season"] == SEASON)
        & (schedule["week"] == WEEK)
        & (schedule["game_type"] == "REG")
    ].copy()

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = retrieved_at.strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    rows = []
    indoor_game_count = 0
    weather_game_count = 0
    unavailable_count = 0

    for _, game in games.iterrows():
        stadium_id = str(
            game["stadium_id"]
        )

        roof = normalize_roof(
            stadium_id,
            game["roof"],
        )

        location = get_stadium_location(
            stadium_id
        )

        away_team = str(
            game["away_team"]
        )
        home_team = str(
            game["home_team"]
        )

        matchup = (
            f"{away_team} "
            f"@ {home_team}"
        )

        print(matchup)
        print(
            f"  Stadium: "
            f"{game['stadium']}"
        )
        print(
            f"  Roof:    {roof}"
        )

        row = {
            "season": SEASON,
            "week": WEEK,
            "away_team": away_team,
            "home_team": home_team,
            "stadium_id": stadium_id,
            "stadium": str(
                game["stadium"]
            ),
            "city": (
                location["city"]
                if location
                else None
            ),
            "roof_type": roof,
            "weather_relevant": int(
                weather_relevant(roof)
            ),
            "kickoff_et": None,
            "local_kickoff": None,
            "forecast_time": None,
            "temperature_f": None,
            "precipitation_in": None,
            "weather_code": None,
            "wind_mph": None,
            "wind_gust_mph": None,
            "snapshot_path": None,
        }

        if not weather_relevant(roof):
            indoor_game_count += 1

            print(
                "  Weather: SKIPPED "
                "(indoor venue)"
            )
            print()

            rows.append(row)
            continue

        if location is None:
            unavailable_count += 1

            print(
                "  Weather: UNAVAILABLE "
                "(missing coordinates)"
            )
            print()

            rows.append(row)
            continue

        game_date = str(
            game["gameday"]
        )

        local_kickoff = get_local_kickoff(
            gameday=game["gameday"],
            gametime=game["gametime"],
            stadium_timezone=location[
                "timezone"
            ],
        )

        kickoff_et = local_kickoff.astimezone(
            ZoneInfo(
                "America/New_York"
            )
        )

        row["kickoff_et"] = (
            kickoff_et.isoformat()
        )

        row["local_kickoff"] = (
            local_kickoff.isoformat()
        )

        print(
            f"  Local kickoff: "
            f"{local_kickoff.strftime('%Y-%m-%d %H:%M %Z')}"
        )

        try:
            payload = fetch_weather(
                latitude=location[
                    "latitude"
                ],
                longitude=location[
                    "longitude"
                ],
                timezone_name=location[
                    "timezone"
                ],
                game_date=game_date,
            )
        except Exception as exc:
            unavailable_count += 1

            print(
                f"  Weather: UNAVAILABLE "
                f"({exc})"
            )
            print()

            rows.append(row)
            continue

        kickoff_weather = (
            get_kickoff_weather(
                payload,
                local_kickoff,
            )
        )

        output_path = (
            RAW_DIR
            / (
                f"{stadium_id}_"
                f"{timestamp}.json"
            )
        )

        output_path.write_text(
            json.dumps(
                payload,
                indent=2,
            )
        )

        row["snapshot_path"] = str(
            output_path
        )

        if kickoff_weather is None:
            unavailable_count += 1

            print(
                "  Kickoff weather: "
                "UNAVAILABLE"
            )
        else:
            weather_game_count += 1

            row.update(
                kickoff_weather
            )

            print(
                f"  Forecast time: "
                f"{kickoff_weather['forecast_time']}"
            )
            print(
                f"  Temperature: "
                f"{kickoff_weather['temperature_f']} F"
            )
            print(
                f"  Wind: "
                f"{kickoff_weather['wind_mph']} mph"
            )
            print(
                f"  Gusts: "
                f"{kickoff_weather['wind_gust_mph']} mph"
            )
            print(
                f"  Precipitation: "
                f"{kickoff_weather['precipitation_in']} in"
            )

        print(
            f"  Weather snapshot: "
            f"{output_path}"
        )
        print()

        rows.append(row)

    status = (
        "VALID"
        if unavailable_count == 0
        else "PARTIAL"
    )

    with sqlite3.connect(
        DB_PATH
    ) as conn:
        cursor = conn.execute(
            """
            INSERT INTO weather_snapshots (
                retrieved_at,
                season,
                week,
                status,
                game_count,
                weather_game_count,
                indoor_game_count,
                source,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retrieved_at.isoformat(),
                SEASON,
                WEEK,
                status,
                len(rows),
                weather_game_count,
                indoor_game_count,
                WEATHER_URL,
                (
                    None
                    if unavailable_count == 0
                    else (
                        f"{unavailable_count} "
                        f"weather lookups unavailable"
                    )
                ),
            ),
        )

        weather_snapshot_id = (
            cursor.lastrowid
        )

        for row in rows:
            conn.execute(
                """
                INSERT INTO nfl_weather (
                    weather_snapshot_id,
                    season,
                    week,
                    away_team,
                    home_team,
                    stadium_id,
                    stadium,
                    city,
                    roof_type,
                    weather_relevant,
                    kickoff_et,
                    local_kickoff,
                    forecast_time,
                    temperature_f,
                    precipitation_in,
                    weather_code,
                    wind_mph,
                    wind_gust_mph,
                    snapshot_path
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    weather_snapshot_id,
                    row["season"],
                    row["week"],
                    row["away_team"],
                    row["home_team"],
                    row["stadium_id"],
                    row["stadium"],
                    row["city"],
                    row["roof_type"],
                    row["weather_relevant"],
                    row["kickoff_et"],
                    row["local_kickoff"],
                    row["forecast_time"],
                    row["temperature_f"],
                    row["precipitation_in"],
                    row["weather_code"],
                    row["wind_mph"],
                    row["wind_gust_mph"],
                    row["snapshot_path"],
                ),
            )

        conn.commit()

    print("DATABASE")
    print(
        f"  Weather snapshot ID: "
        f"{weather_snapshot_id}"
    )
    print(
        f"  Status:              "
        f"{status}"
    )
    print(
        f"  Games stored:        "
        f"{len(rows)}"
    )
    print(
        f"  Forecasts stored:    "
        f"{weather_game_count}"
    )
    print(
        f"  Indoor games:        "
        f"{indoor_game_count}"
    )
    print(
        f"  Unavailable:         "
        f"{unavailable_count}"
    )

if __name__ == "__main__":
    main()
