from pathlib import Path
import json
import datetime as dt

DATA = Path("data/beckley_rates.json")
HOTELS = [
    "Comfort Inn Beckley",
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
]

def fetch_rates(date_label: str) -> dict:
    """
    TODO: replace with real fetchers/parsers.
    For now, return deterministic sample data so the app works.
    """
    base = {
        "Comfort Inn Beckley": 129,
        "Courtyard Beckley": 139,
        "Hampton Inn Beckley": 149,
        "Tru by Hilton Beckley": 144,
        "Fairfield Inn Beckley": 135,
        "Best Western Beckley": 119,
        "Country Inn Beckley": 125,
    }
    if date_label == "Tomorrow":
        base["Comfort Inn Beckley"] = 131
        base["Courtyard Beckley"] = 141
        base["Hampton Inn Beckley"] = 147
        base["Tru by Hilton Beckley"] = 140
        base["Fairfield Inn Beckley"] = 136
        base["Best Western Beckley"] = 118
        base["Country Inn Beckley"] = 126
    if date_label == "Friday":
        # small change so Friday isn't identical
        base["Comfort Inn Beckley"] = 128
    return base

def main():
    labels = ["Today", "Tomorrow", "Friday"]
    rates_by_day = {label: fetch_rates(label) for label in labels}

    DATA.parent.mkdir(parents=True, exist_ok=True)
    with DATA.open("w", encoding="utf-8") as f:
        json.dump({"rates_by_day": rates_by_day}, f, indent=2)

    print(f"Wrote {DATA.resolve()} on {dt.datetime.utcnow().isoformat()}Z")

if __name__ == "__main__":
    main()

