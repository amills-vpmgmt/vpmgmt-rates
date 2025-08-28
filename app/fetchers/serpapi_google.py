import os
import re
from datetime import date, timedelta, datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
RAW_DIR = Path("data/raw")

# -------------- helpers --------------
def _iso(d: date) -> str: return d.isoformat()
def _norm(t: str) -> str: return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
def _score(a: str, b: str) -> float: return SequenceMatcher(None, _norm(a), _norm(b)).ratio()
def _city_in(addr: str, city: str) -> bool: return city.lower() in (addr or "").lower()

def _to_int(val) -> Optional[int]:
    if val is None: return None
    if isinstance(val, (int, float)): return int(val)
    m = re.search(r"(\d[\d,]*)(?:\.\d+)?", str(val))
    if not m: return None
    return int(m.group(1).replace(",", ""))

def _nightly_ok(v: Optional[int]) -> bool:
    # Guardrails for Beckley market; adjust if needed
    return v is not None and 40 <= v <= 600

def _save_raw(hotel_name: str, checkin: date, body: str, suffix: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", hotel_name).strip("_")
    fname = f"{safe}_{checkin.isoformat()}_{suffix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out = RAW_DIR / fname
    out.write_text(body, encoding="utf-8")
    return out

# -------------- classify helpers --------------
def _is_member(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in ["member", "choice privileges", "hilton honors", "marriott bonvoy"])

def _is_refundable(text: str) -> Optional[bool]:
    t = _norm(text)
    if "nonrefundable" in t or "non-refundable" in t or "advance purchase" in t or "prepay" in t:
        return False
    if "free cancellation" in t or "refundable" in t or "cancel" in t:
        return True
    return None  # unknown

def _basis_from_keys(obj: Dict[str, Any]) -> Optional[str]:
    """
    Prefer before-tax nightly fields when present.
    """
    for k in ("extracted_before_taxes_fees", "before_taxes_fees"):
        if obj.get(k) is not None: return "nightly_before_tax"
    for k in ("extracted_lowest", "lowest", "price"):
        if obj.get(k) is not None: return "nightly_unknown"
    return None

def _collect_from_rate_obj(obj: Dict[str, Any]) -> List[int]:
    vals: List[int] = []
    for k in ("extracted_before_taxes_fees", "extracted_lowest", "before_taxes_fees", "lowest", "price"):
        v = _to_int(obj.get(k))
        if _nightly_ok(v): vals.append(v)
    return vals

# -------------- extraction --------------
def _offers_from_property(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    offers: List[Dict[str, Any]] = []
    # build context text for classification
    ctx_bits = []
    for k in ("rate_plan", "merchant", "description", "snippet", "source"):
        v = p.get(k)
        if isinstance(v, str): ctx_bits.append(v)
    ctx_txt = " ".join(ctx_bits)

    # rate_per_night may be int or object
    rpn = p.get("rate_per_night")
    if isinstance(rpn, dict):
        basis = _basis_from_keys(rpn) or "nightly_unknown"
        for price in _collect_from_rate_obj(rpn):
            offers.append({
                "price": price,
                "basis": basis,
                "member": _is_member(ctx_txt),
                "refundable": _is_refundable(ctx_txt),
                "source": "properties"
            })
    else:
        price = _to_int(rpn)
        if _nightly_ok(price):
            offers.append({
                "price": price, "basis": "nightly_unknown",
                "member": _is_member(ctx_txt),
                "refundable": _is_refundable(ctx_txt),
                "source": "properties"
            })

    # total_rate can mirror rpn
    tr = p.get("total_rate")
    if isinstance(tr, dict):
        basis = _basis_from_keys(tr) or "nightly_unknown"
        for price in _collect_from_rate_obj(tr):
            offers.append({
                "price": price, "basis": basis,
                "member": _is_member(ctx_txt),
                "refundable": _is_refundable(ctx_txt),
                "source": "properties"
            })
    else:
        price = _to_int(tr)
        if _nightly_ok(price):
            offers.append({
                "price": price, "basis": "nightly_unknown",
                "member": _is_member(ctx_txt),
                "refundable": _is_refundable(ctx_txt),
                "source": "properties"
            })

    # nested prices[]
    prices = p.get("prices")
    if isinstance(prices, list):
        for pr in prices:
            if not isinstance(pr, dict): continue
            sub_ctx = " ".join([ctx_txt, str(pr.get("rate_plan","")), str(pr.get("description",""))])
            v = pr.get("rate_per_night")
            if isinstance(v, dict):
                basis = _basis_from_keys(v) or "nightly_unknown"
                for price in _collect_from_rate_obj(v):
                    if _nightly_ok(price):
                        offers.append({
                            "price": price, "basis": basis,
                            "member": _is_member(sub_ctx),
                            "refundable": _is_refundable(sub_ctx),
                            "source": "properties"
                        })
            else:
                price = _to_int(v)
                if _nightly_ok(price):
                    offers.append({
                        "price": price, "basis": "nightly_unknown",
                        "member": _is_member(sub_ctx),
                        "refundable": _is_refundable(sub_ctx),
                        "source": "properties"
                    })
            pv = _to_int(pr.get("price"))
            if _nightly_ok(pv):
                offers.append({
                    "price": pv, "basis": "nightly_unknown",
                    "member": _is_member(sub_ctx),
                    "refundable": _is_refundable(sub_ctx),
                    "source": "properties"
                })
    return offers

def _offers_from_ad(ad: Dict[str, Any]) -> List[Dict[str, Any]]:
    offers: List[Dict[str, Any]] = []
    txt = " ".join([str(ad.get("name","")), str(ad.get("title","")), str(ad.get("description",""))])
    for k in ("extracted_price", "price"):
        price = _to_int(ad.get(k))
        if _nightly_ok(price):
            offers.append({
                "price": price,
                "basis": "nightly_unknown",
                "member": _is_member(txt),
                "refundable": _is_refundable(txt),
                "source": "ads"
            })
    return offers

# -------------- result picking --------------
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

def _categorize(offers: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    cats: Dict[str, List[Dict[str, Any]]] = {
        "public_refundable": [],
        "public_nonrefundable": [],
        "member_refundable": [],
        "member_nonrefundable": []
    }
    for o in offers:
        member = bool(o.get("member"))
        ref = o.get("refundable")
        # unknown refundable -> treat as refundable (safer comparison)
        if ref is None: ref = True
        key = (
            "member_refundable" if member and ref else
            "member_nonrefundable" if member and not ref else
            "public_refundable" if not member and ref else
            "public_nonrefundable"
        )
        cats[key].append(o)
    return cats

def _pick_primary(cats: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    # priority order
    order = ["public_refundable", "public_nonrefundable", "member_refundable", "member_nonrefundable"]
    for cat in order:
        items = cats.get(cat, [])
        if not items: continue
        # prefer before-tax nightly; then cheapest
        before_tax = [o for o in items if o.get("basis") == "nightly_before_tax"]
        pool = before_tax if before_tax else items
        best = sorted(pool, key=lambda o: o["price"])[0]
        return {"price": best["price"], "category": cat, "basis": best.get("basis","nightly_unknown"), "source": best.get("source")}
    return None

def _summarize_ranges(cats: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for cat, items in cats.items():
        prices = sorted({o["price"] for o in items if _nightly_ok(o["price"])})
        if prices:
            out[cat] = {"low": prices[0], "high": prices[-1]}
    return out

# -------------- main entry --------------
def fetch_categorized_rates_for_hotel(
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
) -> Optional[Dict[str, Any]]:
    if not SERPAPI_KEY:
        print(f"[MISS] {hotel_name} {checkin} -> SERPAPI_KEY missing")
        return None

    def _query(q: str, tag: str) -> Optional[Dict[str, Any]]:
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
        props = _properties_from(data)
        ads = _ads_from(data)

        offers: List[Dict[str, Any]] = []

        # properties
        if props:
            pr = _best_match(props, hotel_name, city, ("name","title"))
            if pr:
                offers += _offers_from_property(pr)

        # ads
        if ads:
            ad = _best_match(ads, hotel_name, city, ("name","title"))
            if ad:
                offers += _offers_from_ad(ad)

        offers = [o for o in offers if _nightly_ok(o.get("price"))]
        if not offers:
            print(f"[MISS] {hotel_name} {checkin} -> no usable offers ({tag})")
            return None

        cats = _categorize(offers)
        primary = _pick_primary(cats)
        ranges = _summarize_ranges(cats)

        return {"primary": primary, "ranges": ranges}

    # precise first, then relaxed
    res = _query(f"{hotel_name}, {address}", "addr")
    if res is not None:
        return res
    return _query(f"{hotel_name}, {city}", "city")
