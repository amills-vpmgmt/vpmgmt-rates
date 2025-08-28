import os
import re
from datetime import date, timedelta, datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
RAW_DIR = Path("data/raw")

# ----------------- helpers -----------------
def _iso(d: date) -> str: return d.isoformat()
def _norm(t: str) -> str: return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
def _score(a: str, b: str) -> float: return SequenceMatcher(None, _norm(a), _norm(b)).ratio()
def _city_in(addr: str, city: str) -> bool: return city.lower() in (addr or "").lower()

def _to_int(val) -> Optional[int]:
    if val is None: return None
    if isinstance(val, (int, float)): return int(val)
    m = re.search(r"(\d[\d,]*)(?:\.\d+)?", str(val))
    return int(m.group(1).replace(",", "")) if m else None

def _nightly_ok(v: Optional[int]) -> bool:
    return v is not None and 40 <= v <= 600  # guardrails

def _save_raw(hotel_name: str, checkin: date, body: str, suffix: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", hotel_name).strip("_")
    fname = f"{safe}_{checkin.isoformat()}_{suffix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out = RAW_DIR / fname
    out.write_text(body, encoding="utf-8")
    return out

# ----------------- brand provider matching -----------------
BRAND_PATTERNS = {
    "choice":       [r"choice\s*hotels", r"choicehotels", r"choicehotels\.com", r"comfort inn", r"quality inn", r"sleep inn", r"clarion"],
    "hilton":       [r"hilton", r"hilton\.com", r"hampton", r"tru by hilton", r"tru"],
    "marriott":     [r"marriott", r"marriott\.com", r"courtyard", r"fairfield"],
    "bestwestern":  [r"best\s*western", r"bestwestern", r"bestwestern\.com"],
    "radisson":     [r"radisson", r"country inn", r"country inn & suites"],
}

def _is_brand_provider(text: str, brand: Optional[str]) -> bool:
    if not brand or brand not in BRAND_PATTERNS: 
        return False
    t = _norm(text or "")
    for pat in BRAND_PATTERNS[brand]:
        if re.search(pat, t):
            return True
    return False

def _gather_provider_context(obj: Dict[str, Any]) -> str:
    """
    Try to find any field that hints at the provider/merchant:
    'provider', 'merchant', 'source', 'rate_plan', 'displayed_provider', 'seller', 'description', 'title'.
    """
    keys = ("provider","merchant","source","displayed_provider","seller","rate_plan","description","title","name")
    parts = []
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v:
            parts.append(v)
    return " | ".join(parts)

# ----------------- offer extraction -----------------
def _collect_from_rate_obj(obj: Dict[str, Any]) -> List[int]:
    vals: List[int] = []
    for k in ("extracted_before_taxes_fees","extracted_lowest","before_taxes_fees","lowest","price"):
        v = _to_int(obj.get(k))
        if _nightly_ok(v): vals.append(v)
    return vals

def _offers_from_property(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    offers: List[Dict[str, Any]] = []
    ctx_txt = _gather_provider_context(p)

    # rate_per_night
    rpn = p.get("rate_per_night")
    if isinstance(rpn, dict):
        for price in _collect_from_rate_obj(rpn):
            offers.append({"price": price, "basis": "nightly", "provider_ctx": ctx_txt, "source": "properties"})
    else:
        v = _to_int(rpn)
        if _nightly_ok(v):
            offers.append({"price": v, "basis": "nightly", "provider_ctx": ctx_txt, "source": "properties"})

    # total_rate
    tr = p.get("total_rate")
    if isinstance(tr, dict):
        for price in _collect_from_rate_obj(tr):
            offers.append({"price": price, "basis": "nightly", "provider_ctx": ctx_txt, "source": "properties"})
    else:
        v = _to_int(tr)
        if _nightly_ok(v):
            offers.append({"price": v, "basis": "nightly", "provider_ctx": ctx_txt, "source": "properties"})

    # nested prices[]
    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if not isinstance(pr, dict): continue
            sub_ctx = " | ".join([ctx_txt, _gather_provider_context(pr)])
            v = pr.get("rate_per_night")
            if isinstance(v, dict):
                for price in _collect_from_rate_obj(v):
                    offers.append({"price": price, "basis": "nightly", "provider_ctx": sub_ctx, "source": "properties"})
            else:
                vv = _to_int(v)
                if _nightly_ok(vv):
                    offers.append({"price": vv, "basis": "nightly", "provider_ctx": sub_ctx, "source": "properties"})
            pv = _to_int(pr.get("price"))
            if _nightly_ok(pv):
                offers.append({"price": pv, "basis": "nightly", "provider_ctx": sub_ctx, "source": "properties"})
    return offers

def _offers_from_ad(ad: Dict[str, Any]) -> List[Dict[str, Any]]:
    offers: List[Dict[str, Any]] = []
    ctx = _gather_provider_context(ad)
    for k in ("extracted_price", "price"):
        price = _to_int(ad.get(k))
        if _nightly_ok(price):
            offers.append({"price": price, "basis": "nightly", "provider_ctx": ctx, "source": "ads"})
    return offers

# ----------------- picking -----------------
def _properties_from(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("properties", "hotel_results"):
        arr = data.get(key)
        if isinstance(arr, list) and arr: return arr
    org = data.get("organic_results")
    if isinstance(org, list):
        hotels = [x for x in org if isinstance(x, dict) and x.get("type") == "hotel"]
        if hotels: return hotels
    return []

def _ads_from(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    arr = data.get("ads")
    return arr if isinstance(arr, list) else []

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

# ----------------- main entry: BRAND FILTER -----------------
def fetch_brand_primary_for_hotel(
    hotel_name: str,
    address: str,
    city: str,
    checkin: date,
    brand: Optional[str] = None,  # e.g. "choice" to force Choice-only offers
    nights: int = 1,
    adults: int = 2,
    gl: str = "us",
    hl: str = "en",
    currency: str = "USD",
    timeout_s: float = 25.0,
    retries: int = 2,
) -> Optional[int]:
    """
    Returns a single primary nightly price restricted to the hotel's brand provider
    (e.g., Choice Hotels for Comfort Inn) if 'brand' is provided.
    Falls back to None if no brand-direct offers are present.
    """

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

        # collect offers from best-matched property and ads
        offers: List[Dict[str, Any]] = []

        props = _properties_from(data)
        if props:
            pr = _best_match(props, hotel_name, city, ("name","title"))
            if pr:
                offers += _offers_from_property(pr)

        ads = _ads_from(data)
        if ads:
            ad = _best_match(ads, hotel_name, city, ("name","title"))
            if ad:
                offers += _offers_from_ad(ad)

        # filter by brand provider if asked
        filtered: List[Dict[str, Any]] = []
        for o in offers:
            if not _nightly_ok(o.get("price")):
                continue
            prov_ctx = o.get("provider_ctx", "")
            if brand:
                if _is_brand_provider(prov_ctx, brand):
                    filtered.append(o)
            else:
                filtered.append(o)

        if not filtered:
            print(f"[MISS] {hotel_name} {checkin} -> no brand-direct offers matched ({brand or 'any'}) ({tag})")
            return None

        # choose the lowest brand-direct nightly price
        best = sorted(filtered, key=lambda x: x["price"])[0]
        print(f"[OK]   {hotel_name} {checkin} -> ${best['price']} (brand={brand}, via {best.get('source')})")
        return best["price"]

    # precise then relaxed
    res = _query(f"{hotel_name}, {address}", "addr")
    if res is not None:
        return res
    return _query(f"{hotel_name}, {city}", "city")
