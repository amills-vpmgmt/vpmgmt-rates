from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import json
import os

from app.fetchers.serpapi_google import fetch_min_rate_for_hotel

DATA = Path("data/beckley_rates.json")

# Hotels (exact names work best; you can tune queries later)
YOUR = "Comfort Inn Beckley"
COMPETITORS = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
]
ALL = COMPETITORS + [YOUR]

def _next_friday(today: date) -> date:
    weekday = today.weekday()
    if weekday == 3:  # Thursday -> skip to next week's Friday
        return today + timedelta(days=8)
    days_until = (4 - weekday) % 7
    return today + timedelta(days=days_until)

def _label_dates(today: date) -> dict[str, date]:
    return {
        "Today": today,
        "Tomorrow": today + timedelta(days=1),
        "Friday": _next_friday(today),
    }

def _query_for(hotel_name: str) -> str:
    # Adding city/state in query improves precision
    return f"{hotel_name}, Beckley, WV"

def fetch_day_rates(checkin: date) -> dict[str, int | str]:
    day_rates: dict[str, int | str] = {}
    for hotel in ALL:
        try:
            price = fetch_min_rate_for_hotel(_query_for(hotel), checkin, nights=1, adults=2)
            day_rates[hotel] = price if price is not None else "N/A"
        except Exception as e:
            # Don’t crash the whole run if one hotel fails
            day_rates[hotel] = "N/A"
            print(f"[WARN] {hotel} {checkin.isoformat()}: {e}")
    return day_rates

def main():
    # SERPAPI_KEY must be set either locally or in GitHub Actions secrets
    if not os.getenv("SERPAPI_KEY"):
        print("WARNING: SERPAPI_KEY not set. Run will probably fail to fetch live rates.")

    today = date.today()
    labels = _label_dates(today)

    rates_by_day = {}
    for label, d in labels.items():
        rates_by_day[label] = fetch_day_rates(d)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rates_by_day": rates_by_day,
    }

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {DATA.resolve()}")

if __name__ == "__main__":
    main()
