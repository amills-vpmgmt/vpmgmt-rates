import os
import re
from datetime import date, timedelta, datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
RAW_DIR = Path("data/raw")

# ---------- helpers ----------
def _iso(d: date) -> str: return d.isoformat()
def _norm(t: str) -> str: return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
def _score(a: str, b: str) -> float: return SequenceMatcher(None, _norm(a), _norm(b)).ratio()
def _city_in(addr: str, city: str) -> bool: return city.lower() in (addr or "").lower()

def _to_int(val) -> Optional[int]:
    if val is None: return None
    if isinstance(val, (int, float)): v = int(val)
    else:
        m = re.search(r"(\d[\d,]*)(?:\.\d+)?", str(val))
        if not m: return None
        v = int(m.group(1).replace(",", ""))
    return v

def _price_ok(v: Optional[int]) -> bool:
    return v is not None and 40 <= v <= 600  # guardrails for nightly base

def _save_raw(hotel_name: str, checkin: date, body: str, suffix: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", hotel_name).strip("_")
    fname = f"{safe}_{checkin.isoformat()}_{suffix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out = RAW_DIR / fname
    out.write_text(body, encoding="utf-8")
    return out

# ---------- candidate extraction ----------
_PREF_ORDER = (
    "extracted_before_taxes_fees",
    "extracted_lowest",
    "before_taxes_fees",
    "lowest",
)

def _from_rate_obj(obj: Dict[str, Any]) -> List[int]:
    vals: List[int] = []
    for k in _PREF_ORDER:
        v = _to_int(obj.get(k))
        if _price_ok(v): vals.append(v)
    return vals

def _cands_from_property(p: Dict[str, Any]) -> List[int]:
    c: List[int] = []
    rpn = p.get("rate_per_night")
    if isinstance(rpn, dict): c += _from_rate_obj(rpn)
    else:
        v = _to_int(rpn)
        if _price_ok(v): c.append(v)

    tr = p.get("total_rate")
    if isinstance(tr, dict): c += _from_rate_obj(tr)
    else:
        v = _to_int(tr)
        if _price_ok(v): c.append(v)

    for k in ("price", "rate_per_night_low", "rate_per_night_high", "min_price", "max_price"):
        v = _to_int(p.get(k))
        if _price_ok(v): c.append(v)

    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if not isinstance(pr, dict): continue
            v = pr.get("rate_per_night")
            if isinstance(v, dict): c += _from_rate_obj(v)
            else:
                vv = _to_int(v)
                if _price_ok(vv): c.append(vv)
            vv = _to_int(pr.get("price"))
            if _price_ok(vv): c.append(vv)
    return c

def _cands_from_ad(ad: Dict[str, Any]) -> List[int]:
    c: List[int] = []
    for k in ("extracted_price", "price"):
        v = _to_int(ad.get(k))
        if _price_ok(v): c.append(v)
    return c

def _get_properties(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("properties", "hotel_results"):
        arr = data.get(key)
        if isinstance(arr, list) and arr: return arr
    org = data.get("organic_results")
    if isinstance(org, list):
        hotels = [x for x in org if isinstance(x, dict) and x.get("type") == "hotel"]
        if hotels: return hotels
    return []

def _get_ads(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    ads = data.get("ads")
    return ads if isinstance(ads, list) else []

def _best_match(items: List[Dict[str, Any]], hotel_name: str, city: str, name_keys=("name","title")) -> Optional[Dict[str, Any]]:
    best, best_score = None, 0.0
    for it in items:
        nm = ""
        for k in name_keys:
            nm = (it.get(k) or "").strip()
            if nm: break
        sc = _score(nm, hotel_name)
        if sc > best_score:
            best, best_score = it, sc
    if not best: return None
    addr = (best.get("formatted_address") or best.get("address") or "")
    if addr and not _city_in(addr, city):
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

# ---------- main ----------
def fetch_rate_range_for_hotel(
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
) -> Optional[Dict[str, int | str]]:
    if not SERPAPI_KEY:
        print(f"[MISS] {hotel_name} {checkin} -> SERPAPI_KEY missing")
        return None

    def _query(q: str, tag: str) -> Optional[Dict[str, int | str]]:
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

        candidates: List[int] = []
        source_bits: List[str] = []

        # Properties
        props = _get_properties(data)
        if props:
            pr = _best_match(props, hotel_name, city, ("name","title"))
            if pr:
                got = _cands_from_property(pr)
                if got:
                    candidates += got
                    source_bits.append("properties")

        # Ads
        ads = _get_ads(data)
        if ads:
            ad = _best_match(ads, hotel_name, city, ("name","title"))
            if ad:
                got = _cands_from_ad(ad)
                if got:
                    candidates += got
                    source_bits.append("ads")

        candidates = sorted(set([v for v in candidates if _price_ok(v)]))
        if not candidates:
            print(f"[MISS] {hotel_name} {checkin} -> no usable price fields ({tag})")
            return None

        return {"low": candidates[0], "high": candidates[-1], "source": "|".join(source_bits) or "unknown"}

    # precise, then relaxed
    res = _query(f"{hotel_name}, {address}", "addr")
    if res is not None:
        return res
    return _query(f"{hotel_name}, {city}", "city")
