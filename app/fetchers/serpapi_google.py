import os
import re
from datetime import date, timedelta, datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
RAW_DIR = Path("data/raw")  # saved per-request for debugging

# --------------------------
# Helpers
# --------------------------
def _iso(d: date) -> str:
    return d.isoformat()

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

def _name_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _addr_ok(addr: str, city: str) -> bool:
    return city.lower() in (addr or "").lower()

def _clean_price(val) -> Optional[int]:
    """
    Accepts '$129', 'USD 129', 129, '129 per night', etc.
    Returns integer dollars in a sane range (guardrails), else None.
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
    return p if 40 <= p <= 600 else None

def _extract_price_candidates(p: Dict[str, Any]) -> List[int]:
    vals: List[int] = []
    # common direct fields
    for k in ("rate_per_night", "price", "rate_per_night_low", "rate_per_night_high", "min_price", "max_price"):
        v = _clean_price(p.get(k))
        if v is not None: vals.append(v)
    # nested list
    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if isinstance(pr, dict):
                v = _clean_price(pr.get("rate_per_night") or pr.get("price"))
                if v is not None: vals.append(v)
    # unique + sorted (min first)
    return sorted(set(vals))

def _save_raw(hotel_name: str, checkin: date, body: str, suffix: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_hotel = re.sub(r"[^a-zA-Z0-9]+", "_", hotel_name).strip("_")
    fname = f"{safe_hotel}_{checkin.isoformat()}_{suffix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out = RAW_DIR / fname
    out.write_text(body, encoding="utf-8")
    return out

# --------------------------
# Main fetch
# --------------------------
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
    retries: int = 2,
) -> Optional[int]:
    """
    Returns MIN nightly price (int USD) for the specific hotel, or None.
    Precision tactics:
      - Query uses brand + full address
      - Select best match by fuzzy name score
      - Require address contains expected city
      - Accept prices only from known fields + range-validated
    Saves raw JSON for each request under data/raw/.
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

    # simple retry loop (handles transient 5xx/429/network hiccups)
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_s, read=timeout_s, write=timeout_s/2, connect=10)) as client:
                r = client.get("https://serpapi.com/search.json", params=params)
                r.raise_for_status()
                body = r.text
            break
        except Exception as e:
            last_exc = e
            if attempt == retries:
                p = _save_raw(hotel_name, checkin, f'{{"error":"{type(e).__name__}","detail":"{str(e)}"}}', "http_error")
                print(f"[RAW] HTTP error saved -> {p}")
                return None

    p_ok = _save_raw(hotel_name, checkin, body, "ok")
    print(f"[RAW] Saved -> {p_ok}")

    data = r.json()
    props = data.get("properties") or data.get("hotel_results") or []
    if not isinstance(props, list) or not props:
        return None

    # best by name score
    best = None
    best_score = 0.0
    for pr in props:
        nm = (pr.get("name") or pr.get("title") or "").strip()
        sc = _name_score(nm, hotel_name)
        if sc > best_score:
            best, best_score = pr, sc

    if not best:
        return None

    addr = (best.get("formatted_address") or best.get("address") or "")
    if not _addr_ok(addr, city):
        return None

    cands = _extract_price_candidates(best)
    return cands[0] if cands else None
