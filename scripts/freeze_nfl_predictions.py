from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone

from database.db import DB_PATH
from models.elo import MODEL_VERSION, predict_run
from reports.efficiency_context import matchup_efficiency_context
from reports.injury_context import matchup_injury_context
from reports.nfl_slate import (
    best_moneylines,
    consensus_lines,
    load_run,
    probability_to_american,
    research_status,
)
from reports.nfl_week import get_nfl_week, normalize_team
from reports.weather_context import matchup_weather_context


def freeze_run(
    run_id: int,
    season: int,
    snapshot_type: str,
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    run = load_run(conn, run_id)

    if run is None:
        raise SystemExit(
            f"NFL collection run {run_id} not found."
        )

    if run["status"] != "VALID":
        raise SystemExit(
            f"Run {run_id} is not VALID: {run['status']}"
        )

    events = conn.execute(
        """
        SELECT
            event_id,
            MIN(commence_time) AS commence_time,
            MIN(away_team) AS away_team,
            MIN(home_team) AS home_team,
            COUNT(DISTINCT sportsbook_key) AS sportsbook_count
        FROM odds_snapshots
        WHERE collection_run_id = ?
          AND commence_time IS NOT NULL
          AND snapshot_time < commence_time
        GROUP BY event_id
        ORDER BY commence_time, event_id
        """,
        (run_id,),
    ).fetchall()

    market_rows = conn.execute(
        """
        SELECT
            event_id,
            outcome_name,
            consensus_probability
        FROM market_benchmarks
        WHERE collection_run_id = ?
        """,
        (run_id,),
    ).fetchall()

    market = {
        (row["event_id"], row["outcome_name"]):
            row["consensus_probability"]
        for row in market_rows
    }

    predictions = predict_run(run_id)

    elo = {
        (row["event_id"], row["outcome_name"]):
            row["model_probability"]
        for row in predictions
    }

    inserted = 0
    skipped = 0

    for event in events:
        event_id = event["event_id"]
        home = event["home_team"]
        away = event["away_team"]

        home_market = market.get(
            (event_id, home)
        )
        away_market = market.get(
            (event_id, away)
        )

        home_model = elo.get(
            (event_id, home)
        )
        away_model = elo.get(
            (event_id, away)
        )

        if None in (
            home_market,
            away_market,
            home_model,
            away_model,
        ):
            print(
                f"SKIP {away} @ {home}: "
                f"missing market or model probability"
            )
            skipped += 1
            continue

        nfl_week = get_nfl_week(
            away_team=away,
            home_team=home,
            season=season,
        )

        if nfl_week is None:
            injury_context = {
                "status": "UNAVAILABLE",
                "reason": "Unable to determine NFL week.",
                "snapshot": None,
                "away": [],
                "home": [],
            }

            efficiency_context = {
                "status": "UNAVAILABLE",
                "reason": "Unable to determine NFL week.",
                "snapshot": None,
                "away": None,
                "home": None,
            }

            weather_context = {
                "status": "UNAVAILABLE",
                "reason": "Unable to determine NFL week.",
                "snapshot": None,
                "weather": None,
                "freshness": None,
            }

        else:
            injury_context = matchup_injury_context(
                away_team=away,
                home_team=home,
                season=season,
                expected_week=nfl_week,
            )

            efficiency_context = matchup_efficiency_context(
                away_team=normalize_team(away),
                home_team=normalize_team(home),
                season=season,
                nfl_week=nfl_week,
            )

            weather_context = matchup_weather_context(
                away_team=away,
                home_team=home,
                season=season,
                week=nfl_week,
            )

        spread_consensus, total_consensus = consensus_lines(
            conn,
            run_id,
            event_id,
        )

        best_ml = best_moneylines(
            conn,
            run_id,
            event_id,
        )

        home_best_ml = best_ml.get(home)
        away_best_ml = best_ml.get(away)

        home_edge = home_model - home_market
        away_edge = away_model - away_market

        if home_edge >= away_edge:
            edge_team = home
            edge = home_edge
        else:
            edge_team = away
            edge = away_edge

        eff_snapshot = (
            efficiency_context.get("snapshot")
            or {}
        )

        injury_snapshot = (
            injury_context.get("snapshot")
            or {}
        )

        weather_snapshot = (
            weather_context.get("snapshot")
            or {}
        )

        home_eff = (
            efficiency_context.get("home")
            if efficiency_context["status"] == "VALID"
            else None
        )

        away_eff = (
            efficiency_context.get("away")
            if efficiency_context["status"] == "VALID"
            else None
        )

        weather = (
            weather_context.get("weather")
            or {}
        )

        freshness = (
            weather_context.get("freshness")
            or {}
        )

        values = {
            "created_at":
                datetime.now(timezone.utc).isoformat(),
            "sport":
                "americanfootball_nfl",
            "season":
                season,
            "week":
                nfl_week,

            "collection_run_id":
                run_id,
            "event_id":
                event_id,
            "commence_time":
                event["commence_time"],
            "home_team":
                home,
            "away_team":
                away,

            "model_version":
                MODEL_VERSION,
            "snapshot_type":
                snapshot_type,

            "sportsbook_count":
                event["sportsbook_count"],

            "home_market_probability":
                home_market,
            "away_market_probability":
                away_market,

            "home_model_probability":
                home_model,
            "away_model_probability":
                away_model,

            "model_disagreement_team":
                edge_team,
            "model_disagreement_pp":
                edge * 100,
            "research_status":
                research_status(edge),

            "home_best_moneyline":
                (
                    home_best_ml["price"]
                    if home_best_ml
                    else None
                ),
            "home_best_moneyline_book":
                (
                    home_best_ml["sportsbook"]
                    if home_best_ml
                    else None
                ),

            "away_best_moneyline":
                (
                    away_best_ml["price"]
                    if away_best_ml
                    else None
                ),
            "away_best_moneyline_book":
                (
                    away_best_ml["sportsbook"]
                    if away_best_ml
                    else None
                ),

            "home_fair_moneyline":
                probability_to_american(
                    home_market
                ),
            "away_fair_moneyline":
                probability_to_american(
                    away_market
                ),

            "home_spread":
                spread_consensus.get(home),
            "away_spread":
                spread_consensus.get(away),
            "total":
                total_consensus,

            "efficiency_snapshot_id":
                eff_snapshot.get("id"),
            "efficiency_through_week":
                eff_snapshot.get("through_week"),

            "home_off_epa_per_play":
                (
                    home_eff.get("off_epa_per_play")
                    if home_eff
                    else None
                ),
            "home_def_epa_per_play":
                (
                    home_eff.get("def_epa_per_play")
                    if home_eff
                    else None
                ),
            "home_off_success_rate":
                (
                    home_eff.get("off_success_rate")
                    if home_eff
                    else None
                ),
            "home_dropback_epa_per_play":
                (
                    home_eff.get("dropback_epa_per_play")
                    if home_eff
                    else None
                ),
            "home_rush_epa_per_play":
                (
                    home_eff.get("rush_epa_per_play")
                    if home_eff
                    else None
                ),
            "home_recent_games":
                (
                    home_eff.get("recent_games")
                    if home_eff
                    else None
                ),
            "home_recent_off_epa_per_play":
                (
                    home_eff.get("recent_off_epa_per_play")
                    if home_eff
                    else None
                ),
            "home_recent_def_epa_per_play":
                (
                    home_eff.get("recent_def_epa_per_play")
                    if home_eff
                    else None
                ),
            "home_recent_off_success_rate":
                (
                    home_eff.get("recent_off_success_rate")
                    if home_eff
                    else None
                ),
            "home_recent_dropback_epa_per_play":
                (
                    home_eff.get(
                        "recent_dropback_epa_per_play"
                    )
                    if home_eff
                    else None
                ),
            "home_recent_rush_epa_per_play":
                (
                    home_eff.get(
                        "recent_rush_epa_per_play"
                    )
                    if home_eff
                    else None
                ),

            "away_off_epa_per_play":
                (
                    away_eff.get("off_epa_per_play")
                    if away_eff
                    else None
                ),
            "away_def_epa_per_play":
                (
                    away_eff.get("def_epa_per_play")
                    if away_eff
                    else None
                ),
            "away_off_success_rate":
                (
                    away_eff.get("off_success_rate")
                    if away_eff
                    else None
                ),
            "away_dropback_epa_per_play":
                (
                    away_eff.get("dropback_epa_per_play")
                    if away_eff
                    else None
                ),
            "away_rush_epa_per_play":
                (
                    away_eff.get("rush_epa_per_play")
                    if away_eff
                    else None
                ),
            "away_recent_games":
                (
                    away_eff.get("recent_games")
                    if away_eff
                    else None
                ),
            "away_recent_off_epa_per_play":
                (
                    away_eff.get("recent_off_epa_per_play")
                    if away_eff
                    else None
                ),
            "away_recent_def_epa_per_play":
                (
                    away_eff.get("recent_def_epa_per_play")
                    if away_eff
                    else None
                ),
            "away_recent_off_success_rate":
                (
                    away_eff.get("recent_off_success_rate")
                    if away_eff
                    else None
                ),
            "away_recent_dropback_epa_per_play":
                (
                    away_eff.get(
                        "recent_dropback_epa_per_play"
                    )
                    if away_eff
                    else None
                ),
            "away_recent_rush_epa_per_play":
                (
                    away_eff.get(
                        "recent_rush_epa_per_play"
                    )
                    if away_eff
                    else None
                ),

            "injury_snapshot_id":
                injury_snapshot.get("id"),
            "injury_status":
                injury_context["status"],
            "injury_expected_week":
                (
                    injury_snapshot.get(
                        "expected_week"
                    )
                    if injury_snapshot
                    else nfl_week
                ),
            "injury_latest_week":
                injury_snapshot.get("latest_week"),

            "weather_snapshot_id":
                weather_snapshot.get("id"),
            "weather_status":
                weather_context["status"],
            "weather_freshness":
                freshness.get("label"),
            "weather_horizon_hours":
                freshness.get("hours_to_kickoff"),

            "stadium":
                weather.get("stadium"),
            "roof_type":
                weather.get("roof_type"),
            "weather_relevant":
                weather.get("weather_relevant"),
            "temperature_f":
                weather.get("temperature_f"),
            "precipitation_in":
                weather.get("precipitation_in"),
            "wind_mph":
                weather.get("wind_mph"),
            "wind_gust_mph":
                weather.get("wind_gust_mph"),

            "notes":
                None,
        }

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO prediction_snapshots (
                created_at,
                sport,
                season,
                week,
                collection_run_id,
                event_id,
                commence_time,
                home_team,
                away_team,
                model_version,
                snapshot_type,
                sportsbook_count,
                home_market_probability,
                away_market_probability,
                home_model_probability,
                away_model_probability,
                model_disagreement_team,
                model_disagreement_pp,
                research_status,
                home_best_moneyline,
                home_best_moneyline_book,
                away_best_moneyline,
                away_best_moneyline_book,
                home_fair_moneyline,
                away_fair_moneyline,
                home_spread,
                away_spread,
                total,
                efficiency_snapshot_id,
                efficiency_through_week,
                home_off_epa_per_play,
                home_def_epa_per_play,
                home_off_success_rate,
                home_dropback_epa_per_play,
                home_rush_epa_per_play,
                home_recent_games,
                home_recent_off_epa_per_play,
                home_recent_def_epa_per_play,
                home_recent_off_success_rate,
                home_recent_dropback_epa_per_play,
                home_recent_rush_epa_per_play,
                away_off_epa_per_play,
                away_def_epa_per_play,
                away_off_success_rate,
                away_dropback_epa_per_play,
                away_rush_epa_per_play,
                away_recent_games,
                away_recent_off_epa_per_play,
                away_recent_def_epa_per_play,
                away_recent_off_success_rate,
                away_recent_dropback_epa_per_play,
                away_recent_rush_epa_per_play,
                injury_snapshot_id,
                injury_status,
                injury_expected_week,
                injury_latest_week,
                weather_snapshot_id,
                weather_status,
                weather_freshness,
                weather_horizon_hours,
                stadium,
                roof_type,
                weather_relevant,
                temperature_f,
                precipitation_in,
                wind_mph,
                wind_gust_mph,
                notes
            )
            VALUES (
                :created_at,
                :sport,
                :season,
                :week,
                :collection_run_id,
                :event_id,
                :commence_time,
                :home_team,
                :away_team,
                :model_version,
                :snapshot_type,
                :sportsbook_count,
                :home_market_probability,
                :away_market_probability,
                :home_model_probability,
                :away_model_probability,
                :model_disagreement_team,
                :model_disagreement_pp,
                :research_status,
                :home_best_moneyline,
                :home_best_moneyline_book,
                :away_best_moneyline,
                :away_best_moneyline_book,
                :home_fair_moneyline,
                :away_fair_moneyline,
                :home_spread,
                :away_spread,
                :total,
                :efficiency_snapshot_id,
                :efficiency_through_week,
                :home_off_epa_per_play,
                :home_def_epa_per_play,
                :home_off_success_rate,
                :home_dropback_epa_per_play,
                :home_rush_epa_per_play,
                :home_recent_games,
                :home_recent_off_epa_per_play,
                :home_recent_def_epa_per_play,
                :home_recent_off_success_rate,
                :home_recent_dropback_epa_per_play,
                :home_recent_rush_epa_per_play,
                :away_off_epa_per_play,
                :away_def_epa_per_play,
                :away_off_success_rate,
                :away_dropback_epa_per_play,
                :away_rush_epa_per_play,
                :away_recent_games,
                :away_recent_off_epa_per_play,
                :away_recent_def_epa_per_play,
                :away_recent_off_success_rate,
                :away_recent_dropback_epa_per_play,
                :away_recent_rush_epa_per_play,
                :injury_snapshot_id,
                :injury_status,
                :injury_expected_week,
                :injury_latest_week,
                :weather_snapshot_id,
                :weather_status,
                :weather_freshness,
                :weather_horizon_hours,
                :stadium,
                :roof_type,
                :weather_relevant,
                :temperature_f,
                :precipitation_in,
                :wind_mph,
                :wind_gust_mph,
                :notes
            )
            """,
            values,
        )

        if cursor.rowcount == 1:
            inserted += 1
            print(
                f"FROZEN {away} @ {home} | "
                f"{research_status(edge)} | "
                f"{edge_team} {edge * 100:+.2f} pp"
            )
        else:
            skipped += 1
            print(
                f"EXISTS {away} @ {home} | "
                f"run {run_id} already frozen"
            )

    conn.commit()
    conn.close()

    print()
    print("Prediction ledger complete.")
    print(f"Run:          {run_id}")
    print(f"Model:        {MODEL_VERSION}")
    print(f"Snapshot type:{snapshot_type}")
    print(f"Inserted:     {inserted}")
    print(f"Skipped:      {skipped}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze a MarketEdge NFL run into "
            "the immutable prediction ledger."
        )
    )

    parser.add_argument(
        "--run",
        type=int,
        required=True,
        help="NFL odds collection run ID",
    )

    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="NFL season",
    )

    parser.add_argument(
        "--snapshot-type",
        default="RESEARCH",
        help="Ledger snapshot type",
    )

    args = parser.parse_args()

    freeze_run(
        run_id=args.run,
        season=args.season,
        snapshot_type=args.snapshot_type,
    )


if __name__ == "__main__":
    main()
