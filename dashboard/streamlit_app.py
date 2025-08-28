import streamlit as st
import pandas as pd
from datetime import timedelta, datetime
from pathlib import Path
import json
import pytz

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
DATA_PATH = (REPO_ROOT / "data" / "beckley_rates.json").resolve()
HISTORY_PATH = (REPO_ROOT / "data" / "history.json").resolve()
YOUR_HOTEL = "Comfort Inn Beckley"

eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern).date()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()

if weekday == 3:
    next_friday = today + timedelta(days=8)
else:
    next_friday = today + timedelta(days=(4 - weekday) % 7)

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
def load_json(path_str: str, fingerprint: str) -> dict:
    path = Path(path_str)
    if not path.exists(): return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"⚠️ Failed to parse {path.name}: {e}")
        return {}

payload = load_json(str(DATA_PATH), _file_fingerprint(DATA_PATH))
history = load_json(str(HISTORY_PATH), _file_fingerprint(HISTORY_PATH))

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
        return int(entry)  # backward compat
    except:
        return None

def ranges_text(entry):
    if not isinstance(entry, dict): return None
    rngs = entry.get("ranges") or {}
    parts = []
    for key in ("public_refundable", "public_nonrefundable", "member_refundable", "member_nonrefundable"):
        r = rngs.get(key)
        if r:
            low, high = r.get("low"), r.get("high")
            parts.append(f"{key.replace('_',' ')}: ${low}" + ("" if low==high else f"–${high}"))
    return " | ".join(parts) if parts else None

your_primary = primary_price(data_for_day.get(YOUR_HOTEL))

st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

rows = []
chart_hotels, chart_vals = [], []
for hotel in hotels:
    entry = data_for_day.get(hotel)
    p = primary_price(entry)
    delta = "—" if hotel == YOUR_HOTEL else (f"{p - your_primary:+}" if (p is not None and your_primary is not None) else "N/A")
    detail = ranges_text(entry)
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Primary": f"${p}" if isinstance(p, int) else "N/A",
        "Δ vs You": delta,
        "Details": detail or ""
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

# --------- NEW: 7-day sparkline ---------
st.subheader("📈 Last 7 runs (Primary price)")

label_history = history.get(selected_label, [])
if not label_history:
    st.info("No history yet. Once the nightly job runs a few days, you’ll see sparklines here.")
else:
    # Build a tidy DataFrame: rows = observed_at, columns = hotel names, values = price
    # Keep last 7 entries
    recent = label_history[-7:]

    # observed_at list
    times = [item["observed_at"] for item in recent]
    # hotel set from the most recent record (fallback to configured list)
    sample_rates = recent[-1].get("rates", {})
    hotel_cols = list(sample_rates.keys()) or hotels

    hist_rows = []
    for i, item in enumerate(recent):
        row = {"observed_at": times[i]}
        rmap = item.get("rates", {})
        for h in hotel_cols:
            v = rmap.get(h)
            try:
                row[h] = int(v) if v is not None else None
            except:
                row[h] = None
        hist_rows.append(row)

    hist_df = pd.DataFrame(hist_rows)
    hist_df["observed_at"] = pd.to_datetime(hist_df["observed_at"])

    # Draw small charts in a grid (4 columns)
    n_cols = 4
    cols = st.columns(n_cols)
    for idx, h in enumerate(hotels):
        c = cols[idx % n_cols]
        series = hist_df[["observed_at", h]].dropna()
        with c:
            st.caption(h)
            if series.empty or series[h].isna().all():
                st.line_chart(pd.DataFrame({"observed_at": hist_df["observed_at"], h: [None]*len(hist_df)}).set_index("observed_at"))
            else:
                st.line_chart(series.set_index("observed_at"))
