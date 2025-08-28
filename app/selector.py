import re
import statistics
from typing import List, Dict, Any, Optional, Tuple

# -------- Normalizers / detectors --------
def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

PROVIDERS = {
    "brand_choice":  [r"choicehotels", r"choice hotels", r"comfort inn", r"quality inn", r"sleep inn", r"clarion"],
    "brand_hilton":  [r"hilton\.com", r"hilton", r"hampton", r"tru by hilton", r"tru"],
    "brand_marriott":[r"marriott\.com", r"marriott", r"courtyard", r"fairfield"],
    "brand_bw":      [r"bestwestern\.com", r"best western"],
    "brand_radisson":[r"radisson", r"country inn"],
    # OTA groups (expand as needed)
    "ota_expedia":   [r"expedia", r"hotels\.com", r"travelocity", r"orbitz", r"ebookers", r"wotif"],
    "ota_booking":   [r"booking\.com", r"agoda", r"kayak", r"priceline", r"trip\.com"],
}

def detect_provider_group(provider_ctx: str) -> str:
    t = _norm(provider_ctx)
    for group, pats in PROVIDERS.items():
        for p in pats:
            if re.search(p, t):
                return group
    return "other"

def is_member(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in ["member", "loyalty", "privileges", "honors", "bonvoy"])

def is_refundable(text: str) -> Optional[bool]:
    t = _norm(text)
    if any(k in t for k in ["nonrefundable", "non refundable", "advance purchase", "prepay", "no refund"]):
        return False
    if any(k in t for k in ["free cancellation", "refundable", "cancel", "free to cancel"]):
        return True
    return None  # unknown

def nightly_ok(v: Optional[int]) -> bool:
    return v is not None and 40 <= v <= 600

# -------- Core selection logic --------
def summarize_prices(prices: List[int]) -> Optional[Dict[str, int]]:
    prices = [p for p in prices if nightly_ok(p)]
    if not prices:
        return None
    prices.sort()
    avg = int(round(statistics.mean(prices)))
    return {"low": prices[0], "high": prices[-1], "avg": avg, "count": len(prices)}

def bucket_offers(offers: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Each offer needs fields (already in your fetcher): 
      price:int, provider_ctx:str, source:'ads'|'properties', member:bool|None, refundable:bool|None
    """
    out: Dict[str, List[Dict[str, Any]]] = {
        "public_refundable": [],
        "public_nonrefundable": [],
        "member_refundable": [],
        "member_nonrefundable": [],
    }
    for o in offers:
        price = o.get("price")
        if not nightly_ok(price): 
            continue
        mem = bool(o.get("member"))
        ref = o.get("refundable")
        if ref is None:
            # unknown -> treat as refundable (Google often omits text but default basket is cancellable)
            ref = True
        key = (
            "member_refundable" if mem and ref else
            "member_nonrefundable" if mem and not ref else
            "public_refundable" if not mem and ref else
            "public_nonrefundable"
        )
        out[key].append(o)
    return out

def provider_summaries(offers: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    groups: Dict[str, List[int]] = {}
    for o in offers:
        g = detect_provider_group(o.get("provider_ctx",""))
        groups.setdefault(g, []).append(o.get("price"))
    return {g: summarize_prices(v) for g, v in groups.items() if summarize_prices(v)}

def choose_primary(offers: List[Dict[str, Any]], your_brand_group: str) -> Optional[Dict[str, Any]]:
    """
    Primary = brand.com, public, refundable, lowest nightly.
    If none: brand.com refundable (member ok), else fallback to *public refundable from any provider*.
    """
    def filt(pool, *, public=True, refundable=True):
        for o in pool:
            if public and o.get("member"): 
                continue
            if refundable and o.get("refundable") is False:
                continue
            yield o

    brand_offers = [o for o in offers if detect_provider_group(o.get("provider_ctx","")) == your_brand_group]

    # 1) brand.com public refundable
    c1 = sorted(filt(brand_offers, public=True, refundable=True), key=lambda x: x["price"])
    if c1:
        o = c1[0]
        return {"price": o["price"], "category": "public_refundable", "basis": "nightly", "source": o.get("source"), "provider_ctx": o.get("provider_ctx"), "confidence": 0.99}

    # 2) brand.com refundable (member allowed)
    c2 = sorted(filt(brand_offers, public=False, refundable=True), key=lambda x: x["price"])
    if c2:
        o = c2[0]
        return {"price": o["price"], "category": "member_refundable", "basis": "nightly", "source": o.get("source"), "provider_ctx": o.get("provider_ctx"), "confidence": 0.9}

    # 3) any provider public refundable
    c3 = sorted(filt(offers, public=True, refundable=True), key=lambda x: x["price"])
    if c3:
        o = c3[0]
        return {"price": o["price"], "category": "public_refundable", "basis": "nightly", "source": o.get("source"), "provider_ctx": o.get("provider_ctx"), "confidence": 0.75}

    # 4) give up (return cheapest anything so UI isn’t blank, mark low confidence)
    any_cheapest = sorted([o for o in offers if nightly_ok(o.get("price"))], key=lambda x: x["price"])
    if any_cheapest:
        o = any_cheapest[0]
        return {"price": o["price"], "category": "unknown", "basis": "nightly", "source": o.get("source"), "provider_ctx": o.get("provider_ctx"), "confidence": 0.5}

    return None

def sift_offers(offers: List[Dict[str, Any]], brand_hint: str) -> Dict[str, Any]:
    """
    Main entry:
      - normalizes refundable/member if missing
      - selects primary via policy above
      - builds ranges by category
      - builds OTA/provider summaries (Expedia etc.)
    """
    # Repair missing member/refundable from provider_ctx text
    fixed: List[Dict[str, Any]] = []
    for o in offers:
        ctx = o.get("provider_ctx","")
        o2 = o.copy()
        if o2.get("member") is None:
            o2["member"] = is_member(ctx)
        if o2.get("refundable") is None:
            o2["refundable"] = is_refundable(ctx)
        fixed.append(o2)

    buckets = bucket_offers(fixed)
    ranges = {}
    for k, items in buckets.items():
        prices = [it["price"] for it in items if nightly_ok(it.get("price"))]
        s = summarize_prices(prices)
        if s: ranges[k] = {"low": s["low"], "high": s["high"]}

    primary = choose_primary(fixed, brand_hint)
    providers = provider_summaries(fixed)

    # Pull out Expedia (and friends) specifically for your “Expedia range/avg” columns
    expedia = providers.get("ota_expedia")

    debug = {}
    if primary:
        debug = {"provider_ctx": primary.get("provider_ctx"), "picked_from": primary.get("source")}

    return {
        "primary": {k: primary[k] for k in ("price","category","basis","source") } if primary else None,
        "ranges": ranges,
        "expedia": expedia,
        "debug": debug
    }
