from collectors.odds import collect
from database.normalize_odds import normalize_snapshot


def main():
    print("=== SPORTS RESEARCH ODDS PIPELINE ===")

    print("\n[1/2] Collecting odds...")
    status = collect()

    if status != "VALID":
        print(f"\nPipeline stopped: collection status = {status}")
        return

    print("\n[2/2] Normalizing latest valid snapshot...")
    normalize_snapshot()

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
