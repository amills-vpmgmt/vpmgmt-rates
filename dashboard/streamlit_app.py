import streamlit as st
import pandas as pd
from datetime import timedelta, datetime
from pathlib import Path
import json
import pytz

st.set_page_config(page_title="Beckley Hotel Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Primary = brand.com public refundable (your hotel). Details show category ranges; Expedia columns show OTA view.")

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
DATA_PATH = (REPO_ROOT / "data" / "beckley_rates.json").resolve()
YOUR_HOTEL = "Comfort Inn Beckley"

eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern).date()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()
next_friday = today + timedelta(days=8) if weekday == 3 else today + timedelta(days=(4 - weekday) % 7)
date_options = {"Today": today, "Tomorrow": tomorrow, "Friday": next_friday}
labels = list(date_options.keys())

col1, col2 = st.columns([3,1])
with col1:
    selected_label = st.selectbox("Select check-in date:", labels)
with col2:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.toast("Cache cleared. Reloading…", icon="✅")

checkin_date = date_options[selected_label]

def _file_fingerprint(path: Path) -> str:
    if not path.exists(): return "missing"
    stat = path.stat()
    return f"{stat.st_size}-{stat.st_mtime_ns}"

@st.cache_data(show_spinner=False)
def load_payload(path_str: str, fingerprint: str) -> dict:
    path = Path(path_str)
    if not path.exists(): return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"⚠️ Failed to parse {path.name}: {e}")
        return {}

payload = load_payload(str(DATA_PATH), _file_fingerprint(DATA_PATH))
rates_by_day = payload.get("rates_by_day", {})
generated_at = payload.get("generated_at")
if rates_by_day: st.success(f"✅ Loaded local rates ({DATA_PATH.relative_to(REPO_ROOT)})")
if generated_at: st.caption(f"Data generated at: {generated_at}")

data_for_day = rates_by_day.get(selected_label, {})

hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    YOUR_HOTEL,
]

def primary_price(entry):
    if isinstance(entry, dict) and entry.get("primary") and isinstance(entry["primary"].get("price"), int):
        return entry["primary"]["price"]
    try:
        return int(entry)  # backwards compat
    except:
        return None

def expedia_summary(entry):
    if not isinstance(entry, dict): return None
    return entry.get("expedia")

def ranges_text(entry):
    if not isinstance(entry, dict): return None
    rngs = entry.get("ranges") or {}
    order = ("public_refundable","public_nonrefundable","member_refundable","member_nonrefundable")
    parts = []
    for key in order:
        r = rngs.get(key)
        if r:
            low, high = r.get("low"), r.get("high")
            label = key.replace("_"," ")
            parts.append(f"{label}: ${low}" + ("" if low==high else f"–${high}"))
    # add expedia range to details too
    ex = entry.get("expedia")
    if ex and isinstance(ex.get("low"), int) and isinstance(ex.get("high"), int):
        ex_part = f"Expedia: ${ex['low']}" + ("" if ex['low']==ex['high'] else f"–${ex['high']}")
        parts.append(ex_part)
    return " | ".join(parts) if parts else None

def source_text(entry):
    if not isinstance(entry, dict): return ""
    dbg = entry.get("debug") or {}
    src = dbg.get("picked_from","")  # ads | properties
    prov = dbg.get("provider_ctx","")
    prov_short = prov.split("|")[0].strip() if prov else ""
    return f"{src} · {prov_short}" if (src or prov_short) else ""

def raw_file_text(entry):
    if not isinstance(entry, dict): return ""
    dbg = entry.get("debug") or {}
    return dbg.get("raw_file","")

your_primary = primary_price(data_for_day.get(YOUR_HOTEL))

st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

rows, chart_hotels, chart_vals = [], [], []
for hotel in hotels:
    entry = data_for_day.get(hotel)
    p = primary_price(entry)
    delta = "—" if hotel == YOUR_HOTEL else (f"{p - your_primary:+}" if (p is not None and your_primary is not None) else "N/A")
    detail = ranges_text(entry)
    ex = expedia_summary(entry) or {}
    ex_range = ""
    ex_avg = ""
    if isinstance(ex.get("low"), int) and isinstance(ex.get("high"), int):
        ex_range = f"${ex['low']}" + ("" if ex['low']==ex['high'] else f"–${ex['high']}")
    if isinstance(ex.get("avg"), int):
        ex_avg = f"${ex['avg']}"
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Primary": f"${p}" if isinstance(p, int) else "N/A",
        "Δ vs You": delta,
        "Expedia (range)": ex_range,
        "Expedia avg": ex_avg,
        "Details": detail or "",
        "Source": source_text(entry),
        "Raw": raw_file_text(entry)
    })
    if p is not None:
        chart_hotels.append(hotel)
        chart_vals.append(p)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

st.subheader("📊 Comparison (Primary rates)")
if chart_vals:
    chart_df = pd.DataFrame({"Hotel": chart_hotels, "Primary Rate": chart_vals})
    st.bar_chart(chart_df.set_index("Hotel"))
else:
    st.info("No numeric primary rates available to chart for this date.")
