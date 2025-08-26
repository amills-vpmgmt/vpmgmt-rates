from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import json
import os
import yaml

from app.fetchers.serpapi_google import fetch_min_rate_for_hotel
from app.fetchers.brand_playwright import fetch_brand_total, nightly_from_total

DATA = Path("data/beckley_rates.json")
CONFIG = Path("config/properties.yml")

# --- load hotel list + optional brand URLs from config ---
def _load_hotels():
    hotels = []
    brand_urls = {}
    if CONFIG.exists():
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        for p in cfg.get("properties", []):
            name = p.get("name")
            if not name:
                continue
            hotels.append(name)
            url = p.get("brand_booking_url")  # optional; add in config when ready
            if url:
                brand_urls[name] = url
    else:
        # fallback list
        hotels = [
            "Courtyard Beckley",
            "Hampton Inn Beckley",
            "Tru by Hilton Beckley",
            "Fairfield Inn Beckley",
            "Best Western Beckley",
            "Country Inn Beckley",
            "Comfort Inn Beckley",
        ]
    return hotels, brand_urls

YOUR = "Comfort Inn Beckley"
ALL_HOTELS, BRAND_URLS = _load_hotels()
if YOUR not in ALL_HOTELS:
    ALL_HOTELS.append(YOUR)

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
    # adding city/state helps precision
    return f"{hotel_name}, Beckley, WV"

def fetch_day_rates(checkin: date) -> dict[str, int | str]:
    day_rates: dict[str, int | str] = {}
    for hotel in ALL_HOTELS:
        price: int | None = None

        # 1) Try brand site (if configured)
        brand_url = BRAND_URLS.get(hotel)
        if brand_url:
            try:
                total = fetch_brand_total(brand_url, checkin, nights=1, adults=2)
                if total:
                    price = nightly_from_total(total, nights=1)
            except Exception as e:
                print(f"[brand fail] {hotel} {checkin}: {e}")

        # 2) Fallback to SerpAPI Google Hotels
        if price is None:
            try:
                price = fetch_min_rate_for_hotel(_query_for(hotel), checkin, nights=1, adults=2)
            except Exception as e:
                print(f"[serpapi fail] {hotel} {checkin}: {e}")

        day_rates[hotel] = max(int(price), 0) if isinstance(price, int) else "N/A"
    return day_rates

def main():
    if not os.getenv("SERPAPI_KEY"):
        print("WARNING: SERPAPI_KEY not set; SerpAPI fetch will fail.")

    today = date.today()
    labels = _label_dates(today)
    rates_by_day = {label: fetch_day_rates(d) for label, d in labels.items()}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rates_by_day": rates_by_day,
    }

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {DATA.resolve()}")

if __name__ == "__main__":
    main()
