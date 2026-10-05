import argparse

from collectors.results import collect_results
from config.load_config import load_sport_config


def main():
    parser = argparse.ArgumentParser(
        description="Sports Research results collector"
    )

    parser.add_argument(
        "--sport",
        choices=["mlb", "nfl"],
        required=True,
        help="Sport results to collect",
    )

    parser.add_argument(
        "--days-from",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="Number of previous days of completed games to request",
    )

    args = parser.parse_args()

    config = load_sport_config(args.sport)

    print("=== SPORTS RESEARCH RESULTS COLLECTION ===")
    print(f"Sport: {config['name'].upper()}")

    collect_results(
        sport=config["sport"],
        days_from=args.days_from,
    )


if __name__ == "__main__":
    main()
