import argparse
import sqlite3
from datetime import datetime
from statistics import median
from pathlib import Path
from zoneinfo import ZoneInfo

from models.elo import (
    predict_run,
    MODEL_VERSION,
    K_FACTOR,
    HOME_ADVANTAGE,
    OFFSEASON_REGRESSION,
)

from reports.injury_context import matchup_injury_context
from reports.nfl_week import get_nfl_week, normalize_team
from reports.efficiency_context import matchup_efficiency_context
from reports.weather_context import matchup_weather_context

DB_PATH = Path("database/sports.db")
ET = ZoneInfo("America/New_York")

def format_kickoff(value):
    if not value:
        return "Unknown"

    dt = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    return dt.astimezone(ET).strftime(
        "%a %b %d, %Y %I:%M %p ET"
    )


def research_status(edge):
    edge_pp = abs(edge) * 100

    if edge_pp >= 15:
        return "MAJOR DISAGREEMENT"
    if edge_pp >= 10:
        return "STRONG DISAGREEMENT"
    if edge_pp >= 6:
        return "WATCH"
    if edge_pp >= 4:
        return "LEAN"
    return "MARKET-ALIGNED"

def market_confidence(sportsbook_count):
    if sportsbook_count >= 8:
        return "HIGH"
    if sportsbook_count >= 5:
        return "MEDIUM"
    return "LOW"
def consensus_lines(conn, run_id, event_id):
    primary_books = (
        "fanduel",
        "draftkings",
        "betmgm",
    )

    placeholders = ",".join(
        "?"
        for _ in primary_books
    )

    spread_rows = conn.execute(
        f"""
        SELECT
            outcome_name,
            point
        FROM odds_snapshots
        WHERE collection_run_id = ?
          AND event_id = ?
          AND market_key = 'spreads'
          AND sportsbook_key IN ({placeholders})
          AND point IS NOT NULL
          AND commence_time IS NOT NULL
          AND snapshot_time < commence_time
        """,
        (
            run_id,
            event_id,
            *primary_books,
        ),
    ).fetchall()

    total_rows = conn.execute(
        f"""
        SELECT
            outcome_name,
            point
        FROM odds_snapshots
        WHERE collection_run_id = ?
          AND event_id = ?
          AND market_key = 'totals'
          AND sportsbook_key IN ({placeholders})
          AND point IS NOT NULL
          AND commence_time IS NOT NULL
          AND snapshot_time < commence_time
        """,
        (
            run_id,
            event_id,
            *primary_books,
        ),
    ).fetchall()

    spread_points = {}

    for row in spread_rows:
        spread_points.setdefault(
            row["outcome_name"],
            [],
        ).append(row["point"])

    spread_consensus = {
        team: median(points)
        for team, points in spread_points.items()
        if points
    }

    total_points = [
        row["point"]
        for row in total_rows
        if row["outcome_name"] == "Over"
    ]

    total_consensus = (
        median(total_points)
        if total_points
        else None
    )

    return spread_consensus, total_consensus
def best_moneylines(conn, run_id, event_id):
    rows = conn.execute(
        """
        SELECT
            outcome_name,
            sportsbook_name,
            price
        FROM odds_snapshots
        WHERE collection_run_id = ?
          AND event_id = ?
          AND market_key = 'h2h'
          AND price IS NOT NULL
          AND commence_time IS NOT NULL
          AND snapshot_time < commence_time
        """,
        (
            run_id,
            event_id,
        ),
    ).fetchall()

    best = {}

    for row in rows:
        team = row["outcome_name"]
        price = row["price"]

        current = best.get(team)

        if (
            current is None
            or price > current["price"]
        ):
            best[team] = {
                "price": price,
                "sportsbook": row["sportsbook_name"],
            }

    return best


def probability_to_american(probability):
    if probability <= 0 or probability >= 1:
        return None

    if probability >= 0.5:
        return round(
            -100 * probability
            / (1 - probability)
        )

    return round(
        100 * (1 - probability)
        / probability
    )
def previous_line_run(conn, current_run, event_id):
    row = conn.execute(
        """
        SELECT
            cr.id
        FROM collection_runs AS cr
        WHERE cr.sport = 'americanfootball_nfl'
          AND cr.status = 'VALID'
          AND cr.retrieved_at < ?
          AND EXISTS (
              SELECT 1
              FROM odds_snapshots AS os
              WHERE os.collection_run_id = cr.id
                AND os.event_id = ?
                AND os.market_key IN ('spreads', 'totals')
                AND os.point IS NOT NULL
                AND os.commence_time IS NOT NULL
                AND os.snapshot_time < os.commence_time
          )
        ORDER BY cr.retrieved_at DESC
        LIMIT 1
        """,
        (
            current_run["retrieved_at"],
            event_id,
        ),
    ).fetchone()

    return row["id"] if row else None
def load_run(conn, run_id):
    return conn.execute(
        """
        SELECT *
        FROM collection_runs
        WHERE id = ?
          AND sport = 'americanfootball_nfl'
        """,
        (run_id,),
    ).fetchone()


def previous_nfl_run(conn, run):
    return conn.execute(
        """
        SELECT id
        FROM collection_runs
        WHERE sport = 'americanfootball_nfl'
          AND status = 'VALID'
          AND retrieved_at < ?
        ORDER BY retrieved_at DESC
        LIMIT 1
        """,
        (run["retrieved_at"],),
    ).fetchone()


def main():
    parser = argparse.ArgumentParser(
        description="Generate MarketEdge NFL slate report."
    )

    parser.add_argument(
        "--run",
        type=int,
        required=True,
        help="NFL collection run ID",
    )

    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    run = load_run(conn, args.run)

    if run is None:
        raise SystemExit(
            f"NFL collection run {args.run} not found."
        )

    if run["status"] != "VALID":
        raise SystemExit(
            f"Run {args.run} is not VALID: {run['status']}"
        )

    previous = previous_nfl_run(conn, run)
    previous_run_id = (
        previous["id"]
        if previous
        else None
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
        (args.run,),
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
        (args.run,),
    ).fetchall()

    market = {
        (row["event_id"], row["outcome_name"]):
            row["consensus_probability"]
        for row in market_rows
    }

    previous_market = {}

    for event in events:
        previous_rows = conn.execute(
            """
            SELECT
                mb.collection_run_id,
                mb.event_id,
                mb.outcome_name,
                mb.consensus_probability
            FROM market_benchmarks AS mb
            JOIN collection_runs AS cr
              ON cr.id = mb.collection_run_id
            WHERE mb.event_id = ?
              AND cr.sport = 'americanfootball_nfl'
              AND cr.status = 'VALID'
              AND cr.retrieved_at < ?
              AND EXISTS (
                  SELECT 1
                  FROM odds_snapshots AS os
                  WHERE os.collection_run_id = mb.collection_run_id
                    AND os.event_id = mb.event_id
                    AND os.commence_time IS NOT NULL
                    AND os.snapshot_time < os.commence_time
              )
            ORDER BY cr.retrieved_at DESC
            """,
            (
                event["event_id"],
                run["retrieved_at"],
            ),
        ).fetchall()

        if previous_rows:
            previous_run = previous_rows[0]["collection_run_id"]

            for row in previous_rows:
                if row["collection_run_id"] != previous_run:
                    break

                previous_market[
                    (
                        row["event_id"],
                        row["outcome_name"],
                    )
                ] = {
                    "probability":
                        row["consensus_probability"],
                    "run_id":
                        row["collection_run_id"],
                }
    predictions = predict_run(args.run)

    elo = {
        (row["event_id"], row["outcome_name"]):
            row["model_probability"]
        for row in predictions
    }

    print()
    print("=" * 76)
    print("MARKETEDGE LAB — NFL SLATE REPORT")
    print("=" * 76)

    print(f"Run:               {args.run}")
    print(f"Snapshot:          {run['retrieved_at']}")
    print(f"Events:            {len(events)}")
    print(f"Bookmaker blocks:  {run['bookmaker_count']}")
    print(f"Model:             {MODEL_VERSION}")
    print(f"K / HFA / Regress: {K_FACTOR} / {HOME_ADVANTAGE} / "
          f"{OFFSEASON_REGRESSION:.2f}")

    print(
        "Movement baseline: latest eligible "
        "pregame snapshot per event"
    )
    print()

    ranked = []

    for event in events:
        event_id = event["event_id"]
        home = event["home_team"]
        away = event["away_team"]
        nfl_week = get_nfl_week(
            away_team=away,
            home_team=home,
            season=2026,
        )
        if nfl_week is None:
            efficiency_context = {
                "status": "UNAVAILABLE",
                "reason": (
                    "Unable to determine NFL week "
                    "for efficiency lookup."
                ),
                "snapshot": None,
                "away": None,
                "home": None,
            }
        else:
            efficiency_context = matchup_efficiency_context(
                away_team=normalize_team(away),
                home_team=normalize_team(home),
                season=2026,
                nfl_week=nfl_week,
            )
        if nfl_week is None:
            injury_context = {
                "status": "UNAVAILABLE",
                "reason": (
                    "Unable to determine NFL week "
                    "for this matchup."
                ),
                "snapshot": None,
                "away": [],
                "home": [],
            }
        else:
            injury_context = matchup_injury_context(
                away_team=away,
                home_team=home,
                season=2026,
                expected_week=nfl_week,
            )
        home_market = market.get(
            (event_id, home)
        )
        away_market = market.get(
            (event_id, away)
        )

        home_elo = elo.get(
            (event_id, home)
        )
        away_elo = elo.get(
            (event_id, away)
        )

        if None in (
            home_market,
            away_market,
            home_elo,
            away_elo,
        ):
            continue

        home_edge = home_elo - home_market
        away_edge = away_elo - away_market

        if home_edge >= away_edge:
            edge_team = home
            edge = home_edge
        else:
            edge_team = away
            edge = away_edge

        ranked.append(
            {
                "event": event,
                "home_market": home_market,
                "away_market": away_market,
                "home_elo": home_elo,
                "away_elo": away_elo,
                "edge_team": edge_team,
                "edge": edge,
                "market_confidence": market_confidence(
                    event["sportsbook_count"]
                ),
            }
        )

    ranked.sort(
        key=lambda row: abs(row["edge"]),
        reverse=True,
    )
    notable_line_moves = []

    for row in ranked:
        event = row["event"]

        current_spread, current_total = consensus_lines(
            conn,
            args.run,
            event["event_id"],
        )

        prior_run_id = previous_line_run(
            conn,
            run,
            event["event_id"],
        )

        if prior_run_id is None:
            continue

        prior_spread, prior_total = consensus_lines(
            conn,
            prior_run_id,
            event["event_id"],
        )

        home = event["home_team"]
        away = event["away_team"]

        old_home = prior_spread.get(home)
        new_home = current_spread.get(home)

        if old_home is not None and new_home is not None:
            move = new_home - old_home

            if abs(move) >= 0.5:
                notable_line_moves.append(
                    (
                        event,
                        "spread",
                        home,
                        old_home,
                        new_home,
                        move,
                        prior_run_id,
                    )
                )
        if (
            prior_total is not None
            and current_total is not None
        ):
            move = current_total - prior_total

            if abs(move) >= 0.5:
                notable_line_moves.append(
                    (
                        event,
                        "total",
                        None,
                        prior_total,
                        current_total,
                        move,
                        prior_run_id,
                    )
                )
    print("=" * 76)
    print("NOTABLE LINE MOVEMENT")
    print("=" * 76)

    if not notable_line_moves:
        print("No spread or total moves of 0.5+ points.")
    else:
        for (
            event,
            market_type,
            team,
            old_line,
            new_line,
            move,
            prior_run_id,
        ) in notable_line_moves:
            matchup = (
                f"{event['away_team']} @ "
                f"{event['home_team']}"
            )

            if market_type == "spread":
                print(
                    f"{matchup} | "
                    f"{team} "
                    f"{old_line:+.1f} → "
                    f"{new_line:+.1f} "
                    f"({move:+.1f}) | "
                    f"Run {prior_run_id} → {args.run}"
                )
            else:
                print(
                    f"{matchup} | "
                    f"Total "
                    f"{old_line:.1f} → "
                    f"{new_line:.1f} "
                    f"({move:+.1f}) | "
                    f"Run {prior_run_id} → {args.run}"
                )

    print()
    print("=" * 76)
    print("GAMES TO INVESTIGATE")
    print("=" * 76)

    attention = [
        row
        for row in ranked
        if abs(row["edge"]) * 100 >= 6
    ]

    if not attention:
        print(
            "No games currently exceed the "
            "6 pp watch threshold."
        )
    else:
        for index, row in enumerate(
            attention,
            start=1,
        ):
            event = row["event"]

            print(
                f"{index}. "
                f"{event['away_team']} @ "
                f"{event['home_team']} | "
                f"{row['edge_team']} "
                f"{row['edge'] * 100:+.2f} pp | "
                f"{research_status(row['edge'])} | "
                f"{row['market_confidence']} confidence | "
                f"{event['sportsbook_count']} books"
            )

    print()
    for index, row in enumerate(ranked, start=1):
        event = row["event"]
        spread_consensus, total_consensus = consensus_lines(
            conn,
            args.run,
            event["event_id"],
        )

        previous_line_run_id = previous_line_run(
            conn,
            run,
            event["event_id"],
        )

        previous_spread_consensus = {}
        previous_total_consensus = None

        if previous_line_run_id is not None:
            (
                previous_spread_consensus,
                previous_total_consensus,
            ) = consensus_lines(
                conn,
                previous_line_run_id,
                event["event_id"],
            )
        event_id = event["event_id"]
        home = event["home_team"]
        away = event["away_team"]
        best_ml = best_moneylines(
            conn,
            args.run,
            event_id,
        )
        nfl_week = get_nfl_week(
            away_team=away,
            home_team=home,
            season=2026,
        )

        if nfl_week is None:
            injury_context = {
                "status": "UNAVAILABLE",
                "reason": (
                    "Unable to determine NFL week "
                    "for this matchup."
                ),
                "snapshot": None,
                "away": [],
                "home": [],
            }

            efficiency_context = {
                "status": "UNAVAILABLE",
                "reason": (
                    "Unable to determine NFL week "
                    "for efficiency lookup."
                ),
                "snapshot": None,
                "away": None,
                "home": None,
            }

            weather_context = {
                "status": "UNAVAILABLE",
                "reason": (
                    "Unable to determine NFL week "
                    "for weather lookup."
                ),
                "snapshot": None,
                "weather": None,
            }

        else:
            injury_context = matchup_injury_context(
                away_team=away,
                home_team=home,
                season=2026,
                expected_week=nfl_week,
            )

            efficiency_context = matchup_efficiency_context(
                away_team=normalize_team(away),
                home_team=normalize_team(home),
                season=2026,
                nfl_week=nfl_week,
            )

            weather_context = matchup_weather_context(
                away_team=away,
                home_team=home,
                season=2026,
                week=nfl_week,
            )
        home_best_ml = best_ml.get(home)
        away_best_ml = best_ml.get(away)

        home_fair_ml = probability_to_american(
            row["home_market"]
        )

        away_fair_ml = probability_to_american(
            row["away_market"]
        )
        old_home_entry = previous_market.get(
            (event["event_id"], home)
        )

        old_away_entry = previous_market.get(
            (event["event_id"], away)
        )

        old_home = (
            old_home_entry["probability"]
            if old_home_entry
            else None
        )

        old_away = (
            old_away_entry["probability"]
            if old_away_entry
            else None
        )

        movement_run_id = (
            old_home_entry["run_id"]
            if old_home_entry
            else None
        )
        print("-" * 76)
        print(
            f"#{index}  {away} @ {home}"
        )
        print(
            f"Kickoff:     "
            f"{format_kickoff(event['commence_time'])}"
        )
        print(
            f"Sportsbooks: {event['sportsbook_count']}"
        )
        print(
             f"Market confidence: "
            f"{row['market_confidence']}"
        )
        print()
        print("INJURY CONTEXT")
        if nfl_week is not None:
            print(f"  NFL week: {nfl_week}")

        if injury_context["status"] == "VALID":
            print("  Status: VALID")
            print(
                f"  {away}: "
                f"{len(injury_context['away'])} listed"
            )
            print(
                f"  {home}: "
                f"{len(injury_context['home'])} listed"
            )

        elif injury_context["status"] == "STALE":
            print("  Status: STALE")
            print(
                f"  {injury_context['reason']}"
            )
            print(
                "  Injury context withheld from analysis."
            )

        else:
            print("  Status: UNAVAILABLE")
            print(
                f"  {injury_context['reason']}"
            )
        print()
        print("EFFICIENCY CONTEXT")

        if efficiency_context["status"] == "VALID":
            away_eff = efficiency_context["away"]
            home_eff = efficiency_context["home"]

            through_week = (
                efficiency_context["snapshot"]["through_week"]
            )

            print(f"  Through Week {through_week}")

            recent_games = away_eff["recent_games"]

            print(
                f"  Season vs Last {recent_games} Games"
            )
            print()

            print(f"  {away}")
            print(
                f"    Off EPA/play:      "
                f"{away_eff['off_epa_per_play']:+.4f} season | "
                f"{away_eff['recent_off_epa_per_play']:+.4f} recent"
            )
            print(
                f"    Def EPA/play:      "
                f"{away_eff['def_epa_per_play']:+.4f} season | "
                f"{away_eff['recent_def_epa_per_play']:+.4f} recent"
            )
            print(
                f"    Off success rate:  "
                f"{away_eff['off_success_rate'] * 100:.1f}% season | "
                f"{away_eff['recent_off_success_rate'] * 100:.1f}% recent"
            )
            print(
                f"    Dropback EPA/play: "
                f"{away_eff['dropback_epa_per_play']:+.4f} season | "
                f"{away_eff['recent_dropback_epa_per_play']:+.4f} recent"
            )
            print(
                f"    Rush EPA/play:     "
                f"{away_eff['rush_epa_per_play']:+.4f} season | "
                f"{away_eff['recent_rush_epa_per_play']:+.4f} recent"
            )

            print()

            print(f"  {home}")
            print(
                f"    Off EPA/play:      "
                f"{home_eff['off_epa_per_play']:+.4f} season | "
                f"{home_eff['recent_off_epa_per_play']:+.4f} recent"
            )
            print(
                f"    Def EPA/play:      "
                f"{home_eff['def_epa_per_play']:+.4f} season | "
                f"{home_eff['recent_def_epa_per_play']:+.4f} recent"
            )
            print(
                f"    Off success rate:  "
                f"{home_eff['off_success_rate'] * 100:.1f}% season | "
                f"{home_eff['recent_off_success_rate'] * 100:.1f}% recent"
            )
            print(
                f"    Dropback EPA/play: "
                f"{home_eff['dropback_epa_per_play']:+.4f} season | "
                f"{home_eff['recent_dropback_epa_per_play']:+.4f} recent"
            )
            print(
                f"    Rush EPA/play:     "
                f"{home_eff['rush_epa_per_play']:+.4f} season | "
                f"{home_eff['recent_rush_epa_per_play']:+.4f} recent"
            )

        else:
            print(
                f"  Status: "
                f"{efficiency_context['status']}"
            )
            print(
                f"  {efficiency_context['reason']}"
            )

        print()
        print("WEATHER / VENUE CONTEXT")

        if weather_context["status"] == "UNAVAILABLE":
            print(
                f"  Status: "
                f"{weather_context['status']}"
            )
            print(
                f"  {weather_context['reason']}"
            )
        else:
            weather = weather_context["weather"]

            print(
                f"  Stadium: "
                f"{weather['stadium']}"
            )
            print(
                f"  Roof:    "
                f"{weather['roof_type'].upper()}"
            )

            if not weather["weather_relevant"]:
                print(
                    "  Weather impact: "
                    "NONE - indoor venue"
                )
            else:
                if weather["roof_type"] == "retractable":
                    print(
                        "  Weather exposure: "
                        "DEPENDS ON ROOF STATUS"
                    )
            freshness = weather_context.get(
                "freshness"
            )

            if freshness is not None:
                hours_to_kickoff = (
                    freshness["hours_to_kickoff"]
                )

                print(
                    f"  Forecast status: "
                    f"{freshness['label']}"
                )
                print(
                    f"  Forecast horizon: "
                    f"{hours_to_kickoff:.1f} hours "
                    f"before kickoff"
                )
                if weather["temperature_f"] is None:
                    print(
                        "  Forecast: UNAVAILABLE"
                    )
                else:
                    print(
                        f"  Temperature: "
                        f"{weather['temperature_f']:.1f} F"
                    )
                    print(
                        f"  Wind:        "
                        f"{weather['wind_mph']:.1f} mph"
                    )
                    print(
                        f"  Gusts:       "
                        f"{weather['wind_gust_mph']:.1f} mph"
                    )
                    print(
                        f"  Precip:      "
                        f"{weather['precipitation_in']:.2f} in"
                    )

        if away_best_ml or home_best_ml:
            print()
            print("BEST AVAILABLE MONEYLINE")

            if away_best_ml:
                away_price = int(away_best_ml["price"])
                away_sign = "+" if away_price > 0 else ""

                print(
                    f"  {away:<25} "
                    f"{away_sign}{away_price} "
                    f"({away_best_ml['sportsbook']})"
                )

            if home_best_ml:
                home_price = int(home_best_ml["price"])
                home_sign = "+" if home_price > 0 else ""

                print(
                    f"  {home:<25} "
                    f"{home_sign}{home_price} "
                    f"({home_best_ml['sportsbook']})"
                )

            print()
            print("FAIR MONEYLINE — NO VIG")

            if away_fair_ml is not None:
                away_fair_sign = "+" if away_fair_ml > 0 else ""

                print(
                    f"  {away:<25} "
                    f"{away_fair_sign}{away_fair_ml}"
                )

            if home_fair_ml is not None:
                home_fair_sign = "+" if home_fair_ml > 0 else ""

                print(
                    f"  {home:<25} "
                    f"{home_fair_sign}{home_fair_ml}"
                )
        if spread_consensus:
            print()
            print("MARKET LINES")

            for team, point in sorted(
                spread_consensus.items()
            ):
                sign = "+" if point > 0 else ""
                print(
                    f"  Spread {team:<20} "
                    f"{sign}{point:.1f}"
                )

            if total_consensus is not None:
                print(
                    f"  Total                    "
                    f"{total_consensus:.1f}"
                )
        if previous_line_run_id is not None:
            print()
            print(
                f"LINE MOVEMENT "
                f"(Run {previous_line_run_id} → {args.run})"
            )

            old_home_spread = previous_spread_consensus.get(home)
            new_home_spread = spread_consensus.get(home)

            old_away_spread = previous_spread_consensus.get(away)
            new_away_spread = spread_consensus.get(away)

            if (
                old_home_spread is not None
                and new_home_spread is not None
            ):
                home_spread_move = (
                    new_home_spread - old_home_spread
                )

                print(
                    f"  Spread {home:<20} "
                    f"{old_home_spread:+.1f} → "
                    f"{new_home_spread:+.1f} "
                    f"({home_spread_move:+.1f})"
                )

            if (
                old_away_spread is not None
                and new_away_spread is not None
            ):
                away_spread_move = (
                    new_away_spread - old_away_spread
                )

                print(
                    f"  Spread {away:<20} "
                    f"{old_away_spread:+.1f} → "
                    f"{new_away_spread:+.1f} "
                    f"({away_spread_move:+.1f})"
                )

            if (
                previous_total_consensus is not None
                and total_consensus is not None
            ):
                total_move = (
                    total_consensus
                    - previous_total_consensus
                )

                print(
                    f"  Total                    "
                    f"{previous_total_consensus:.1f} → "
                    f"{total_consensus:.1f} "
                    f"({total_move:+.1f})"
                )
        print()

        print("MARKET CONSENSUS - NO VIG")
        print(
            f"  {away:<25} "
            f"{row['away_market'] * 100:6.2f}%"
        )
        print(
            f"  {home:<25} "
            f"{row['home_market'] * 100:6.2f}%"
        )

        print()
        print(f"{MODEL_VERSION}")

        print(
            f"  {away:<25} "
            f"{row['away_elo'] * 100:6.2f}%"
        )
        print(
            f"  {home:<25} "
            f"{row['home_elo'] * 100:6.2f}%"
        )

        print()
        print(
            f"Model disagreement: "
            f"{row['edge_team']} "
            f"{row['edge'] * 100:+.2f} pp"
        )

        print(
            f"Research status:    "
            f"{research_status(row['edge'])}"
        )

        if (
            old_home is not None
            and old_away is not None
        ):
            home_move = (
                row["home_market"] - old_home
            ) * 100

            away_move = (
                row["away_market"] - old_away
            ) * 100

            print()
            print(
                f"MARKET MOVEMENT "
                f"(Run {movement_run_id} → {args.run})"
            )

            print(
                f"  {away:<25} "
                f"{old_away * 100:6.2f}% → "
                f"{row['away_market'] * 100:6.2f}% "
                f"({away_move:+.2f} pp)"
            )

            print(
                f"  {home:<25} "
                f"{old_home * 100:6.2f}% → "
                f"{row['home_market'] * 100:6.2f}% "
                f"({home_move:+.2f} pp)"
            )

        print()

    print("=" * 76)
    print("RESEARCH SUMMARY")
    print("=" * 76)

    major = 0
    strong = 0
    watch = 0
    lean = 0
    aligned = 0

    for row in ranked:
        edge_pp = abs(row["edge"]) * 100

        if edge_pp >= 15:
            major += 1
        elif edge_pp >= 10:
            strong += 1
        elif edge_pp >= 6:
            watch += 1
        elif edge_pp >= 4:
            lean += 1
        else:
            aligned += 1

    print(
        f"{'Major disagreement':<24}"
        f"15+ pp:       {major}"
    )
    print(
        f"{'Strong disagreement':<24}"
        f"10-14.99 pp: {strong}"
    )
    print(
        f"{'Watch':<24}"
        f"6-9.99 pp:   {watch}"
    )
    print(
        f"{'Lean':<24}"
        f"4-5.99 pp:   {lean}"
    )
    print(
        f"{'Market-aligned':<24}"
        f"<4 pp:       {aligned}"
    )

    print()
    print(
        f"Total games classified: "
        f"{major + strong + watch + lean + aligned}"
    )

    print()
    print(
        "Statuses describe model/market disagreement only; "
        "they are not betting recommendations."
    )
    print()
    conn.close()


if __name__ == "__main__":
    main()
