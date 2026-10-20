import argparse
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")

VALID_LABELS = (
    "TUE_PM",
    "THU_PM",
    "SAT_PM",
    "SUN_AM",
    "SUN_1230",
    "SUN_1530",
    "SUN_1945",
    "MON_1945",
)


def run_command(command):
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        raise SystemExit(result.returncode)

    return result.stdout


def main():
    parser = argparse.ArgumentParser(
        description="Collect fresh NFL odds and freeze the exact run as a MarketEdge checkpoint."
    )
    parser.add_argument(
        "--label",
        required=True,
        choices=VALID_LABELS,
        help="Checkpoint label stored in prediction_snapshots.snapshot_type",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2026,
    )
    args = parser.parse_args()

    now = datetime.now(ET)

    print("=" * 72)
    print("MARKETEDGE NFL CHECKPOINT")
    print(f"Checkpoint : {args.label}")
    print(f"Time ET    : {now.isoformat(timespec='seconds')}")
    print(f"Season     : {args.season}")
    print("=" * 72)

    print("\n[1/2] Collecting fresh NFL odds...\n")

    output = run_command(
        [
            sys.executable,
            "-m",
            "scripts.collect_odds",
            "--sport",
            "nfl",
        ]
    )

    match = re.search(r"Collection run:\s*(\d+)", output)

    if not match:
        raise SystemExit(
            "ERROR: Odds collection completed but collection run ID "
            "could not be identified. Prediction freeze was NOT attempted."
        )

    run_id = int(match.group(1))

    print(f"\nDetected NFL collection run: {run_id}")
    print("\n[2/2] Freezing MarketEdge prediction snapshot...\n")

    run_command(
        [
            sys.executable,
            "-m",
            "scripts.freeze_nfl_predictions",
            "--run",
            str(run_id),
            "--season",
            str(args.season),
            "--snapshot-type",
            args.label,
        ]
    )

    print("\n" + "=" * 72)
    print("CHECKPOINT COMPLETE")
    print(f"Run         : {run_id}")
    print(f"Snapshot    : {args.label}")
    print(f"Completed ET: {datetime.now(ET).isoformat(timespec='seconds')}")
    print("=" * 72)


if __name__ == "__main__":
    main()
