import os
import re
import json
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
RAW_DIR = Path("data/raw")  # raw evidence for debugging/audits

def _to_iso(d: date) -> str:
    return d.isoformat()

def _clean_price(val) -> int | None:
    """
    Accepts '$129', 'USD 129', 129, '129 per night', '129.00', etc.
    Returns integer dollars within a sane nightly range, else None.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        p = int(val)
    else:
        s = str(val)
        m = re.search(r"(\d[\d,]*)(?:\.\d+)?", s)
        if not m:
            return None
        p = int(m.group(1).replace(",", ""))
    return p if 40 <= p <= 600 else None  # guardrails for Beckley-type markets

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

def _name_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _addr_ok(prop: dict, must_include: str = "beckley") -> bool:
    addr = (prop.get("formatted_address") or prop.get("address") or "").lower()
    return must_include in addr

def _best_property_for_name(hotels: list[dict], target_name: str, min_score: float = 0.72):
    best = None
    best_score = 0.0
    for p in hotels:
        name = p.get("name") or p.get("title") or ""
        score = _name_score(name, target_name)
        if score > best_score:
            best, best_score = p, score
    return (best, best_score) if best_score >= min_score else (None, 0.0)

def _extract_prices_from_property(p: dict) -> list[int]:
    vals: list[int] = []

    # direct fields commonly present
    for k in ("rate_per_night", "price", "rate_per_night_low", "rate_per_night_high"):
        v = _clean_price(p.get(k))
        if v is not None:
            vals.append(v)

    # nested prices list
    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if isinstance(pr, dict):
                for k in ("rate_per_night", "price"):
                    v = _clean_price(pr.get(k))
                    if v is not None:
                        vals.append(v)

    # light scan of a few string fields (avoid over-parsing the whole object)
    for k in ("description", "snippet"):
        v = _clean_price(p.get(k))
        if v is not None:
            vals.append(v)

    return sorted(set(vals))

def fetch_min_rate_for_hotel(
    hotel_query: str,              # e.g., "Comfort Inn Beckley, WV"
    checkin: date,
    nights: int = 1,
    adults: int = 2,
    gl: str = "us",
    hl: str = "en",
    currency: str = "USD",
) -> int | None:
    """
    Return the MIN nightly price (int USD) for the specific hotel, or None.
    """
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY not set. Add it as an env var/secret.")

    checkout = checkin + timedelta(days=nights)
    params = {
        "engine": "google_hotels",
        "q": hotel_query,
        "check_in_date": _to_iso(checkin),
        "check_out_date": _to_iso(checkout),
        "adults": adults,
        "gl": gl,
        "hl": hl,
        "currency": currency,
        "api_key": SERPAPI_KEY,
    }

    with httpx.Client(timeout=httpx.Timeout(25, read=25, write=15, connect=10)) as client:
        r = client.get("https://serpapi.com/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    # Save raw response for audit/debug
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_name = f"{_norm(hotel_query)}_{_to_iso(checkin)}.json"
    (RAW_DIR / raw_name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    hotels = data.get("properties") or data.get("hotel_results") or []
    if not isinstance(hotels, list) or not hotels:
        return None

    # choose best-matching property by name; require address to include Beckley
    target_name = hotel_query.split(",")[0].strip()
    prop, score = _best_property_for_name(hotels, target_name)
    if not prop or not _addr_ok(prop):
        return None

    prices = _extract_prices_from_property(prop)
    return prices[0] if prices else None
