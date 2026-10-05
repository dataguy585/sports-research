import sqlite3
from pathlib import Path


DB_PATH = Path("database/sports.db")


def american_profit_units(price, stake_units):
    if price is None or stake_units is None:
        return None

    if stake_units == 0:
        return 0.0

    if price > 0:
        return stake_units * (price / 100.0)

    return stake_units * (100.0 / abs(price))


def settle_decision_row(decision, result):
    if decision["decision"] != "BET":
        return {
            "settled_status": "SETTLED",
            "result": "NO_ACTION",
            "profit_units": 0.0,
        }

    winner = result["winner"]

    if winner is None:
        return None

    if winner == "TIE":
        return {
            "settled_status": "SETTLED",
            "result": "PUSH",
            "profit_units": 0.0,
        }

    if decision["outcome_name"] == winner:
        profit = american_profit_units(
            decision["offered_price"],
            decision["stake_units"],
        )

        return {
            "settled_status": "SETTLED",
            "result": "WIN",
            "profit_units": profit,
        }

    return {
        "settled_status": "SETTLED",
        "result": "LOSS",
        "profit_units": -float(decision["stake_units"] or 0.0),
    }


def settle_completed_decisions():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                d.id,
                d.sport,
                d.event_id,
                d.market_key,
                d.outcome_name,
                d.offered_price,
                d.decision,
                d.stake_units,
                d.settled_status,
                gr.status AS game_status,
                gr.winner
            FROM decisions d
            JOIN game_results gr
              ON gr.event_id = d.event_id
             AND gr.sport = d.sport
            WHERE d.settled_status = 'UNSETTLED'
              AND gr.status = 'COMPLETED'
            ORDER BY d.id
            """
        ).fetchall()

        settled_count = 0

        for row in rows:
            if row["market_key"] != "h2h":
                continue

            settlement = settle_decision_row(
                row,
                {
                    "winner": row["winner"],
                },
            )

            if settlement is None:
                continue

            conn.execute(
                """
                UPDATE decisions
                SET
                    settled_status = ?,
                    result = ?,
                    profit_units = ?
                WHERE id = ?
                """,
                (
                    settlement["settled_status"],
                    settlement["result"],
                    settlement["profit_units"],
                    row["id"],
                ),
            )

            settled_count += 1

        conn.commit()

    return settled_count
