from collectors.odds import collect
from database.normalize_odds import normalize_snapshot
from evaluation.market_benchmark import main as build_market_benchmark

def main():
    print("=== SPORTS RESEARCH ODDS PIPELINE ===")

    print("\n[1/3] Collecting odds...")
    status = collect()

    if status != "VALID":
        print(f"\nPipeline stopped: collection status = {status}")
        return

    print("\n[2/3] Normalizing latest valid snapshot...")
    normalize_snapshot()

    print("\n[3/3] Building market benchmark...")
    build_market_benchmark()

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
