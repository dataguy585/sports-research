import json
from pathlib import Path


CONFIG_DIR = Path("config")


def load_sport_config(name):
    path = CONFIG_DIR / f"{name}.json"

    if not path.exists():
        raise FileNotFoundError(f"Sport config not found: {path}")

    with open(path) as f:
        config = json.load(f)

    required = {
        "name",
        "sport",
        "regions",
        "markets",
        "odds_format",
        "required_sportsbooks",
    }

    missing = required - set(config)

    if missing:
        raise ValueError(
            f"Missing config fields: {', '.join(sorted(missing))}"
        )

    return config

