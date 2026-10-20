from __future__ import annotations

import subprocess
import sys


COLLECTORS = [
    ("nflverse", [sys.executable, "-m", "collectors.nfl_injuries"]),
    ("nfl.com", [sys.executable, "-m", "collectors.nfl_injuries_official"]),
]


def main() -> int:
    failures = []

    for name, command in COLLECTORS:
        print()
        print("=" * 72)
        print(f"REFRESHING INJURY SOURCE: {name}")
        print("=" * 72)

        result = subprocess.run(command)

        if result.returncode != 0:
            failures.append((name, result.returncode))

    if failures:
        print()
        print("One or more injury collectors returned an error:")
        for name, code in failures:
            print(f"  {name}: exit {code}")
        return 1

    print()
    print("NFL injury refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
