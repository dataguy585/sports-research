def american_to_implied(odds):
    odds = float(odds)

    if odds < 0:
        return (-odds) / ((-odds) + 100)

    return 100 / (odds + 100)


def remove_vig(probabilities):
    total = sum(probabilities)

    if total <= 0:
        raise ValueError("Probability total must be positive.")

    return [p / total for p in probabilities]


if __name__ == "__main__":
    odds = [-134, 114]

    raw = [american_to_implied(x) for x in odds]
    fair = remove_vig(raw)

    print("Raw implied probabilities:")
    for value in raw:
        print(f"  {value:.4f}")

    print("\nNo-vig probabilities:")
    for value in fair:
        print(f"  {value:.4f}")

    print(f"\nNo-vig total: {sum(fair):.4f}")
