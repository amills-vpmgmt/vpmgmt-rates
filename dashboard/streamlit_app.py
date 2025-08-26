# dashboard/streamlit_app.py
import streamlit as st
import pandas as pd
from datetime import timedelta, datetime
from pathlib import Path
import json
import pytz
import hashlib

# -----------------------
# App / Page config
# -----------------------
st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -----------------------
# Resolve repo root + data path robustly
# -----------------------
APP_DIR = Path(__file__).resolve().parent         # .../dashboard
REPO_ROOT = APP_DIR.parent                        # repo root
DATA_PATH = (REPO_ROOT / "data" / "beckley_rates.json").resolve()
YOUR_HOTEL = "Comfort Inn Beckley"

# -----------------------
# Timezone-aware dates
# -----------------------
eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern).date()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()

if weekday == 3:  # Thursday -> skip to next week's Friday
    next_friday = today + timedelta(days=8)
else:
    days_until_friday = (4 - weekday) % 7
    next_friday = today + timedelta(days=days_until_friday)

date_options = {"Today": today, "Tomorrow": tomorrow, "Friday": next_friday}
labels = list(date_options.keys())

# -----------------------
# Refresh control (clears cache)
# -----------------------
col1, col2 = st.columns([3,1])
with col1:
    selected_label = st.selectbox("Select check-in date:", labels)
with col2:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.toast("Cache cleared. Reloading…", icon="✅")

checkin_date = date_options[selected_label]
checkin_iso = checkin_date.isoformat()

# -----------------------
# Cached loader that invalidates on file mtime + size
# -----------------------
def _file_fingerprint(path: Path) -> str:
    if not path.exists():
        return "missing"
    stat = path.stat()
    return f"{stat.st_size}-{stat.st_mtime_ns}"

@st.cache_data(show_spinner=False)
def load_payload(path_str: str, fingerprint: str) -> dict:
    """
    Cache key includes the fingerprint, so cache busts whenever the file changes.
    """
    path = Path(path_str)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

fingerprint = _file_fingerprint(DATA_PATH)
payload = load_payload(str(DATA_PATH), fingerprint)
rates_by_day = payload.get("rates_by_day", {})
generated_at = payload.get("generated_at")

if rates_by_day:
    st.success(f"✅ Loaded local rates ({DATA_PATH.relative_to(REPO_ROOT)})")
else:
    st.warning("ℹ️ No local data found yet. Expecting data/beckley_rates.json with 'rates_by_day'.")

if generated_at:
    st.caption(f"Data generated at: {generated_at}")

# Try both label and ISO date keys
rates = rates_by_day.get(selected_label) or rates_by_day.get(checkin_iso) or {}

# -----------------------
# Hotels and table
# -----------------------
hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    YOUR_HOTEL,
]

st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

def to_int_or_none(v):
    try:
        return int(v)
    except:
        return None

your_rate_val = to_int_or_none(rates.get(YOUR_HOTEL))
rows = []
for hotel in hotels:
    r = rates.get(hotel, "N/A")
    r_val = to_int_or_none(r)
    delta = "—" if hotel == YOUR_HOTEL else (
        f"{(r_val - your_rate_val):+}" if (r_val is not None and your_rate_val is not None) else "N/A"
    )
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Rate": f"${r_val}" if r_val is not None else "N/A",
        "Δ vs You": delta
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

st.subheader("📊 Rate Comparison Chart")
chart_df = pd.DataFrame({
    "Hotel": [h for h in hotels if to_int_or_none(rates.get(h)) is not None],
    "Rate": [to_int_or_none(rates.get(h)) for h in hotels if to_int_or_none(rates.get(h)) is not None],
})
if not chart_df.empty:
    st.bar_chart(chart_df.set_index("Hotel"))
else:
    st.info("No numeric rates available to chart for this date.")

with st.expander("Data format expected (example)"):
    st.code("""
{
  "generated_at": "2025-08-26T12:34:56Z",
  "rates_by_day": {
    "Today": {
      "Comfort Inn Beckley": 129,
      "Courtyard Beckley": 139,
      "Hampton Inn Beckley": 149
    },
    "2025-08-29": {
      "Comfort Inn Beckley": 135,
      "Courtyard Beckley": 145,
      "Hampton Inn Beckley": 155
    }
  }
}
""".strip(), language="json")
