from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import json
import os
import yaml

from app.fetchers.serpapi_google import fetch_brand_categorized_for_hotel

DATA = Path("data/beckley_rates.json")
CONFIG = Path("config/properties.yml")
YOUR_HOTEL = "Comfort Inn Beckley"

def _load_hotels():
    if not CONFIG.exists():
        raise FileNotFoundError("config/properties.yml not found")
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    hotels = []
    for p in cfg.get("properties", []):
        hotels.append({
            "name": p.get("name"),
            "address": p.get("address") or f"{p.get('city','')}, {p.get('state','')}",
            "city": p.get("city") or "",
            "brand": (p.get("brand") or "").strip().lower()
        })
    return hotels

def _next_friday(today: date) -> date:
    wd = today.weekday()
    if wd == 3: return today + timedelta(days=8)
    return today + timedelta(days=(4 - wd) % 7)

def _label_dates(today: date) -> dict[str, date]:
    return {"Today": today, "Tomorrow": today + timedelta(days=1), "Friday": _next_friday(today)}

def fetch_day(checkin: date, hotels: list[dict]) -> dict[str, dict | str]:
    day: dict[str, dict | str] = {}
    for h in hotels:
        brand_for_primary = h["brand"] if h["name"] == YOUR_HOTEL else None
        res = fetch_brand_categorized_for_hotel(
            hotel_name=h["name"],
            address=h["address"],
            city=h["city"],
            checkin=checkin,
            brand=brand_for_primary,  # brand.com-only primary for YOUR hotel
            nights=1, adults=2
        )
        day[h["name"]] = res if isinstance(res, dict) else "N/A"
    return day

def main():
    if not os.getenv("SERPAPI_KEY"):
        print("WARNING: SERPAPI_KEY not set; live fetch will fail.")

    hotels = _load_hotels()
    if not any(h["name"] == YOUR_HOTEL for h in hotels):
        hotels.append({"name": YOUR_HOTEL, "address": "Beckley, WV", "city": "Beckley", "brand": "choice"})

    today = date.today()
    labels = _label_dates(today)
    rates_by_day = {label: fetch_day(d, hotels) for label, d in labels.items()}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rates_by_day": rates_by_day,
    }

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {DATA.resolve()}")

if __name__ == "__main__":
    main()
