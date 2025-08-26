import os, re, httpx
from datetime import date, timedelta

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def _to_iso(d: date) -> str:
    return d.isoformat()

def _clean_price(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val)
    m = re.search(r"(\d[\d,]*)", s)
    return int(m.group(1).replace(",", "")) if m else None

def fetch_min_rate_for_hotel(
    hotel_query: str,
    checkin: date,
    nights: int = 1,
    adults: int = 2,
    gl: str = "us",
    hl: str = "en",
) -> int | None:
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY not set")

    checkout = checkin + timedelta(days=nights)
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_hotels",
        "q": hotel_query,
        "check_in_date": _to_iso(checkin),
        "check_out_date": _to_iso(checkout),
        "adults": adults,
        "gl": gl,
        "hl": hl,
        "currency": "USD",
        "api_key": SERPAPI_KEY,
    }

    with httpx.Client(timeout=httpx.Timeout(20, read=20, write=10, connect=10)) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    candidates: list[int] = []

    def add(v):
        p = _clean_price(v)
        if p:
            candidates.append(p)

    for p in data.get("properties", []) or []:
        add(p.get("rate_per_night"))
        add(p.get("price"))
        add(p.get("rate_per_night_low"))
        add(p.get("rate_per_night_high"))
        if isinstance(p.get("prices"), list):
            for pr in p["prices"]:
                add(pr.get("rate_per_night"))
                add(pr.get("price"))

    if not candidates:
        for v in data.values():
            if isinstance(v, (str, int, float)):
                add(v)
            elif isinstance(v, dict):
                for vv in v.values():
                    add(vv)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        add(item.get("price"))
                    else:
                        add(item)

    return min(candidates) if candidates else None
