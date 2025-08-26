import os
import re
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def _iso(d: date) -> str:
    return d.isoformat()

def _clean_price(val) -> Optional[int]:
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
    # Guardrail for nightly rates in this market; tweak if needed later
    return p if 40 <= p <= 600 else None

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

def _name_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _addr_ok(addr: str, city: str) -> bool:
    """
    Ensure result address mentions the expected city (e.g., 'beckley').
    """
    return city.lower() in (addr or "").lower()

def _extract_price_candidates(p: Dict[str, Any]) -> List[int]:
    vals: List[int] = []
    for k in ("rate_per_night", "price", "rate_per_night_low", "rate_per_night_high"):
        v = _clean_price(p.get(k))
        if v is not None:
            vals.append(v)
    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if isinstance(pr, dict):
                v = _clean_price(pr.get("rate_per_night") or pr.get("price"))
                if v is not None:
                    vals.append(v)
    return sorted(set(vals))

def fetch_min_rate_for_hotel(
    hotel_name: str,
    address: str,
    city: str,
    checkin: date,
    nights: int = 1,
    adults: int = 2,
    gl: str = "us",
    hl: str = "en",
    currency: str = "USD",
    timeout_s: float = 25.0,
) -> Optional[int]:
    """
    Returns MIN nightly price (int USD) for the specific hotel, or None.
    Uses precise query (brand + full address) and validates address & name.
    """
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY not set (GitHub secret or local env var).")

    checkout = checkin + timedelta(days=nights)
    params = {
        "engine": "google_hotels",
        "q": f"{hotel_name}, {address}",
        "check_in_date": _iso(checkin),
        "check_out_date": _iso(checkout),
        "adults": adults,
        "currency": currency,
        "gl": gl,
        "hl": hl,
        "api_key": SERPAPI_KEY,
    }

    with httpx.Client(timeout=httpx.Timeout(timeout_s, read=timeout_s, write=timeout_s/2, connect=10)) as client:
        r = client.get("https://serpapi.com/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    props = data.get("properties") or []
    if not isinstance(props, list) or not props:
        return None

    # pick best by fuzzy name, then require address includes city
    best = None
    best_score = 0.0
    for p in props:
        name = (p.get("name") or p.get("title") or "").strip()
        score = _name_score(name, hotel_name)
        if score > best_score:
            best = p
            best_score = score

    if not best:
        return None

    addr = (best.get("formatted_address") or best.get("address") or "")
    if not _addr_ok(addr, city):
        return None

    candidates = _extract_price_candidates(best)
    return candidates[0] if candidates else None
