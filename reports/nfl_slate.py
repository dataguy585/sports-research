import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from models.elo import (
    predict_run,
    MODEL_VERSION,
    K_FACTOR,
    HOME_ADVANTAGE,
    OFFSEASON_REGRESSION,
)

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

    if previous_run_id is not None:
        previous_rows = conn.execute(
            """
            SELECT
                event_id,
                outcome_name,
                consensus_probability
            FROM market_benchmarks
            WHERE collection_run_id = ?
            """,
            (previous_run_id,),
        ).fetchall()

        previous_market = {
            (row["event_id"], row["outcome_name"]):
                row["consensus_probability"]
            for row in previous_rows
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

    if previous_run_id is not None:
        print(f"Movement baseline: Run {previous_run_id}")
    else:
        print("Movement baseline: None")

    print()

    ranked = []

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

        event_id = event["event_id"]
        home = event["home_team"]
        away = event["away_team"]

        old_home = previous_market.get(
            (event_id, home)
        )

        old_away = previous_market.get(
            (event_id, away)
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

        print("MARKET CONSENSUS")
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
                f"(Run {previous_run_id} → {args.run})"
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
