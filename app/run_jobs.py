from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import json
import os
import yaml

from app.fetchers.serpapi_google import fetch_categorized_rates_for_hotel

DATA = Path("data/beckley_rates.json")
HISTORY = Path("data/history.json")
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
        })
    return hotels

def _next_friday(today: date) -> date:
    weekday = today.weekday()
    if weekday == 3: return today + timedelta(days=8)
    return today + timedelta(days=(4 - weekday) % 7)

def _label_dates(today: date) -> dict[str, date]:
    return {"Today": today, "Tomorrow": today + timedelta(days=1), "Friday": _next_friday(today)}

def fetch_day(checkin: date, hotels: list[dict]) -> dict[str, dict | str]:
    day: dict[str, dict | str] = {}
    for h in hotels:
        res = fetch_categorized_rates_for_hotel(h["name"], h["address"], h["city"], checkin, nights=1, adults=2)
        day[h["name"]] = res if isinstance(res, dict) else "N/A"
    return day

def _primary_price(entry):
    if isinstance(entry, dict) and entry.get("primary") and isinstance(entry["primary"].get("price"), int):
        return entry["primary"]["price"]
    try:
        return int(entry)  # backward compat if old format sneaks in
    except:
        return None

def _append_history(rates_by_day: dict):
    """
    history.json shape:
    {
      "Today":    [ {"observed_at": "...", "rates": {"Hotel A": 149, ...}}, ... ],
      "Tomorrow": [ ... ],
      "Friday":   [ ... ]
    }
    """
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY.exists():
        try:
            history = json.loads(HISTORY.read_text(encoding="utf-8"))
        except Exception:
            history = {}
    else:
        history = {}

    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for label, hotels_map in rates_by_day.items():
        # build simple dict of hotel -> primary price (int or None)
        flat = {h: _primary_price(v) for h, v in hotels_map.items()}
        arr = history.get(label, [])
        arr.append({"observed_at": observed_at, "rates": flat})
        # keep last 90 points only
        history[label] = arr[-90:]

    HISTORY.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Updated history -> {HISTORY.resolve()}")

def main():
    if not os.getenv("SERPAPI_KEY"):
        print("WARNING: SERPAPI_KEY not set; live fetch will fail.")

    hotels = _load_hotels()
    if not any(h["name"] == YOUR_HOTEL for h in hotels):
        hotels.append({"name": YOUR_HOTEL, "address": "Beckley, WV", "city": "Beckley"})

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

    # NEW: append to rolling history
    _append_history(rates_by_day)

if __name__ == "__main__":
    main()
