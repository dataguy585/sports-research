from database.decisions import record_decision
from models.market_baseline import load_market_baseline


RULE_VERSION = "BASELINE-RULES-v0"
BET_EDGE_THRESHOLD = 0.04
WATCH_EDGE_THRESHOLD = 0.02


def classify_decision(edge):
    if edge >= BET_EDGE_THRESHOLD:
        return "BET", 0.5, "Model edge meets BET threshold"

    if edge >= WATCH_EDGE_THRESHOLD:
        return "WATCH", 0.0, "Model edge meets WATCH threshold"

    return "NO_BET", 0.0, "Model edge below threshold"


def generate_decisions(collection_run_id):
    rows = load_market_baseline(collection_run_id)

    created = []

    for row in rows:
        market_probability = row["market_probability"]
        model_probability = row["model_probability"]

        edge = model_probability - market_probability

        decision, stake_units, reason = classify_decision(edge)

        decision_id = record_decision(
            sport=row["sport"],
            collection_run_id=row["collection_run_id"],
            event_id=row["event_id"],
            commence_time=None,
            home_team=row["home_team"],
            away_team=row["away_team"],
            market_key="h2h",
            outcome_name=row["outcome_name"],
            sportsbook_key=None,
            offered_price=None,
            market_probability=market_probability,
            model_probability=model_probability,
            decision=decision,
            stake_units=stake_units,
            model_version=row["model_version"],
            rule_version=RULE_VERSION,
            reason=reason,
        )

        created.append(decision_id)

    return created
