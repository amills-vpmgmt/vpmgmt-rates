import os
import re
import httpx
from datetime import date, timedelta

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def _to_iso(d: date) -> str:
    return d.isoformat()

def _clean_price(val) -> int | None:
    """
    Accepts strings like '$129', '$129/night', 'USD 129', or numbers.
    Returns integer dollars or None.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val)
    m = re.search(r"(\d[\d,]*)", s)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))

def fetch_min_rate_for_hotel(
    hotel_query: str,
    checkin: date,
    nights: int = 1,
    adults: int = 2,
    gl: str = "us",
    hl: str = "en",
) -> int | None:
    """
    Queries Google Hotels via SerpAPI and returns a *best available* nightly price (int dollars) for
    the hotel_query on the given dates, or None if not found.

    NOTE: SerpAPI result fields can vary. We try several likely places for a nightly price.
    """
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY not set. Add it as a GitHub Action secret and/or local env.")

    checkout = checkin + timedelta(days=nights)
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_hotels",
        "q": hotel_query,                        # e.g., "Comfort Inn Beckley, WV"
        "check_in_date": _to_iso(checkin),
        "check_out_date": _to_iso(checkout),
        "adults": adults,
        "gl": gl,
        "hl": hl,
        "currency": "USD",
        "api_key": SERPAPI_KEY,
    }

    # Conservative timeouts; SerpAPI is fast
    with httpx.Client(timeout=httpx.Timeout(20.0, read=20.0, write=10.0, connect=10.0)) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    # Try to find a price. SerpAPI responses often contain lists like:
    # - data["properties"] (each with "rate_per_night" or "price", sometimes nested)
    # - data["prices"] or "offers"
    # We try common fields and fall back to scanning strings.
    candidates = []

    def add_candidate(v):
        p = _clean_price(v)
        if p:
            candidates.append(p)

    props = data.get("properties") or []
    for p in props:
        add_candidate(p.get("rate_per_night"))
        add_candidate(p.get("price"))
        # Sometimes inside "prices" or "rate_per_night_low", etc.
        if isinstance(p.get("prices"), list):
            for pr in p["prices"]:
                add_candidate(pr.get("rate_per_night"))
                add_candidate(pr.get("price"))
        add_candidate(p.get("rate_per_night_low"))
        add_candidate(p.get("rate_per_night_high"))

    # As a last resort, scan top-level fields for any price-like strings
    if not candidates:
        for k, v in data.items():
            if isinstance(v, str):
                add_candidate(v)
            elif isinstance(v, dict):
                for vv in v.values():
                    add_candidate(vv)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, (str, int, float, dict)):
                        add_candidate(item if not isinstance(item, dict) else item.get("price"))

    return min(candidates) if candidates else None

