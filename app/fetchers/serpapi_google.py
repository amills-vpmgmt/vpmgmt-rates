import os
import re
from datetime import date, timedelta, datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
RAW_DIR = Path("data/raw")

# ---------- small helpers ----------
def _iso(d: date) -> str: return d.isoformat()
def _norm(t: str) -> str: return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
def _score(a: str, b: str) -> float: return SequenceMatcher(None, _norm(a), _norm(b)).ratio()
def _city_in(addr: str, city: str) -> bool: return city.lower() in (addr or "").lower()

def _clean_int(val) -> Optional[int]:
    """Parse an int from strings like '$165', 'USD 135', '135.00' or raw numbers."""
    if val is None: return None
    if isinstance(val, (int, float)): v = int(val)
    else:
        m = re.search(r"(\d[\d,]*)(?:\.\d+)?", str(val))
        if not m: return None
        v = int(m.group(1).replace(",", ""))
    return v

def _price_ok(v: Optional[int]) -> bool:
    return v is not None and 40 <= v <= 600  # nightly base guardrails

def _save_raw(hotel_name: str, checkin: date, body: str, suffix: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", hotel_name).strip("_")
    fname = f"{safe}_{checkin.isoformat()}_{suffix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out = RAW_DIR / fname
    out.write_text(body, encoding="utf-8")
    return out

# ---------- extract candidates from a single hotel object ----------
def _extract_price_candidates_from_property(p: Dict[str, Any]) -> List[int]:
    """Works for Google Hotels 'properties[]' shapes."""
    cands: List[int] = []

    # 1) rate_per_night can be INT or OBJECT {lowest, extracted_lowest, before_taxes_fees, extracted_before_taxes_fees}
    rpn = p.get("rate_per_night")
    if isinstance(rpn, dict):
        for k in ("extracted_before_taxes_fees", "extracted_lowest", "before_taxes_fees", "lowest"):
            v = _clean_int(rpn.get(k))
            if _price_ok(v): cands.append(v)
    else:
        v = _clean_int(rpn)
        if _price_ok(v): cands.append(v)

    # 2) total_rate may mirror rate_per_night
    tr = p.get("total_rate")
    if isinstance(tr, dict):
        for k in ("extracted_before_taxes_fees", "extracted_lowest", "before_taxes_fees", "lowest"):
            v = _clean_int(tr.get(k))
            if _price_ok(v): cands.append(v)
    else:
        v = _clean_int(tr)
        if _price_ok(v): cands.append(v)

    # 3) legacy flat keys some responses still expose
    for k in ("price", "rate_per_night_low", "rate_per_night_high", "min_price", "max_price"):
        v = _clean_int(p.get(k))
        if _price_ok(v): cands.append(v)

    # 4) nested prices[]
    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if isinstance(pr, dict):
                for k in ("rate_per_night", "price"):
                    v = pr.get(k)
                    if isinstance(v, dict):  # sometimes nested object again
                        vv = _clean_int(v.get("extracted_lowest") or v.get("extracted_before_taxes_fees") or v.get("lowest"))
                    else:
                        vv = _clean_int(v)
                    if _price_ok(vv): cands.append(vv)

    return sorted(set(cands))

def _extract_price_candidates_from_ad(ad: Dict[str, Any]) -> List[int]:
    """Fallback for Comfort Inn cases that show under 'ads[]'."""
    cands: List[int] = []
    for k in ("extracted_price", "price"):
        v = _clean_int(ad.get(k))
        if _price_ok(v): cands.append(v)
    return sorted(set(cands))

# ---------- find hotels in response ----------
def _get_properties_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    props = data.get("properties")
    if isinstance(props, list) and props: return props
    props = data.get("hotel_results")
    if isinstance(props, list) and props: return props
    # extremely rare: hotels under organic_results
    org = data.get("organic_results")
    if isinstance(org, list):
        hotels = [x for x in org if isinstance(x, dict) and x.get("type") == "hotel"]
        if hotels: return hotels
    return []

def _get_ads_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    ads = data.get("ads")
    return ads if isinstance(ads, list) else []

def _pick_best_match(items: List[Dict[str, Any]], hotel_name: str, city: str, name_keys=("name","title")) -> Optional[Dict[str, Any]]:
    # choose highest name score, but require city match in address
    best, best_score = None, 0.0
    for it in items:
        nm = ""
        for k in name_keys:
            nm = (it.get(k) or "").strip()
            if nm: break
        sc = _score(nm, hotel_name)
        if sc > best_score:
            best, best_score = it, sc
    if not best:
        return None

    # Address / location sanity (properties use 'formatted_address'/'address', ads don't always have one)
    addr = (best.get("formatted_address") or best.get("address") or "")
    if addr and not _city_in(addr, city):
        # try next-best that DOES match the city
        ranked = sorted(
            [(it, _score((it.get("name") or it.get("title") or "").strip(), hotel_name)) for it in items],
            key=lambda x: x[1], reverse=True
        )
        for it, _ in ranked[:5]:
            a2 = (it.get("formatted_address") or it.get("address") or "")
            if a2 and _city_in(a2, city):
                return it
        return None
    return best

# ---------- main fetch ----------
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
    if not SERPAPI_KEY:
        print(f"[MISS] {hotel_name} {checkin} -> SERPAPI_KEY missing")
        return None

    def _query(q: str, tag: str) -> Optional[int]:
        params = {
            "engine": "google_hotels",
            "q": q,
            "check_in_date": _iso(checkin),
            "check_out_date": _iso(checkin + timedelta(days=nights)),
            "adults": adults,
            "currency": currency,
            "gl": gl,
            "hl": hl,
            "api_key": SERPAPI_KEY,
        }
        body = ""
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=httpx.Timeout(timeout_s, read=timeout_s, write=timeout_s/2, connect=10)) as client:
                    r = client.get("https://serpapi.com/search.json", params=params)
                    r.raise_for_status()
                    body = r.text
                break
            except Exception as e:
                if attempt == retries:
                    p_err = _save_raw(hotel_name, checkin, f'{{"error":"{type(e).__name__}","detail":"{str(e)}"}}', f"{tag}_http_error")
                    print(f"[MISS] {hotel_name} {checkin} -> HTTP error ({tag}). Raw: {p_err.name}")
                    return None

        p_ok = _save_raw(hotel_name, checkin, body, f"{tag}_ok")
        print(f"[RAW]  {hotel_name} {checkin} -> {p_ok.name}")

        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            print(f"[MISS] {hotel_name} {checkin} -> SerpAPI error: {data.get('error')} ({tag})")
            return None

        # 1) Try properties[] first (Best Western, Courtyard, Country Inn return here)
        props = _get_properties_list(data)
        if props:
            pr = _pick_best_match(props, hotel_name, city, ("name","title"))
            if pr:
                cands = _extract_price_candidates_from_property(pr)
                if cands:
                    price = min(cands)
                    print(f"[OK]   {hotel_name} {checkin} -> ${price} ({tag}/properties)")
                    return price
                else:
                    nm = (pr.get("name") or pr.get("title") or "").strip()
                    print(f"[MISS] {hotel_name} {checkin} -> matched '{nm}' but no price fields ({tag}/properties)")
            else:
                # show some context
                head = "; ".join([(x.get("name") or x.get("title") or "").strip() for x in props[:3]])
                print(f"[MISS] {hotel_name} {checkin} -> no city/name match in properties. Top: {head} ({tag})")

        # 2) Fall back to ads[] (Comfort Inn often appears here with extracted_price)
        ads = _get_ads_list(data)
        if ads:
            ad = _pick_best_match(ads, hotel_name, city, ("name","title"))
            if ad:
                cands = _extract_price_candidates_from_ad(ad)
                if cands:
                    price = min(cands)
                    print(f"[OK]   {hotel_name} {checkin} -> ${price} ({tag}/ads)")
                    return price
                else:
                    nm = (ad.get("name") or ad.get("title") or "").strip()
                    print(f"[MISS] {hotel_name} {checkin} -> matched ad '{nm}' but no ad price fields ({tag})")
            else:
                head = "; ".join([(x.get("name") or x.get("title") or "").strip() for x in ads[:3]])
                print(f"[MISS] {hotel_name} {checkin} -> no city/name match in ads. Top: {head} ({tag})")

        print(f"[MISS] {hotel_name} {checkin} -> no usable price fields in response ({tag})")
        return None

    # Primary: brand + full address (precise)
    price = _query(f"{hotel_name}, {address}", "addr")
    if price is not None:
        return price

    # Fallback: brand + city (less strict; helps if address formatting differs)
    return _query(f"{hotel_name}, {city}", "city")
