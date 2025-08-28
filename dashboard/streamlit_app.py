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

rates = rates_by_day.get(selected_label, {})

hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    YOUR_HOTEL,
]

def to_range(v):
    """Accepts either an int (old format) or {'low':..,'high':..} (new). Returns (low, high) or (None, None)."""
    if isinstance(v, dict) and "low" in v and "high" in v:
        return v["low"], v["high"]
    try:
        iv = int(v)
        return iv, iv
    except:
        return None, None

def midpoint(low, high):
    if low is None or high is None: return None
    return (int(low) + int(high)) // 2

your_low, your_high = to_range(rates.get(YOUR_HOTEL))
your_mid = midpoint(your_low, your_high)

st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

rows = []
chart_hotels, chart_vals = [], []
for hotel in hotels:
    low, high = to_range(rates.get(hotel))
    show_rate = "N/A"
    if low is not None and high is not None:
        show_rate = f"${low}" if low == high else f"${low}–${high}"
    delta = "—" if hotel == YOUR_HOTEL else (
        f"{(midpoint(low, high) - your_mid):+}" if (midpoint(low, high) is not None and your_mid is not None) else "N/A"
    )
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Rate": show_rate,
        "Δ vs You (midpoint)": delta
    })
    m = midpoint(low, high)
    if m is not None:
        chart_hotels.append(hotel)
        chart_vals.append(m)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

st.subheader("📊 Rate Comparison Chart (midpoints)")
if chart_vals:
    chart_df = pd.DataFrame({"Hotel": chart_hotels, "Rate (midpoint)": chart_vals})
    st.bar_chart(chart_df.set_index("Hotel"))
else:
    st.info("No numeric ranges available to chart for this date.")
