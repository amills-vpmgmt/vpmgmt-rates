import streamlit as st
import pandas as pd
from datetime import timedelta, datetime
from pathlib import Path
import json
import pytz

# -----------------------
# App / Page config
# -----------------------
st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -----------------------
# Constants / Paths
# -----------------------
DATA_PATH = Path("data/beckley_rates.json")   # local file in this repo
YOUR_HOTEL = "Comfort Inn Beckley"            # reference property

# -----------------------
# Timezone-aware "today"
# -----------------------
eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern).date()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()

# Friday logic (skip this Friday if it's Thursday)
if weekday == 3:  # Thursday
    next_friday = today + timedelta(days=8)  # next week's Friday
else:
    days_until_friday = (4 - weekday) % 7
    next_friday = today + timedelta(days=days_until_friday)

# Date Picker Options
date_options = {
    "Today": today,
    "Tomorrow": tomorrow,
    "Friday": next_friday
}
labels = list(date_options.keys())
selected_label = st.selectbox("Select check-in date:", labels)
checkin_date = date_options[selected_label]
checkin_iso = checkin_date.isoformat()

# -----------------------
# Load Local Data (from repo)
# Supports either:
#   data["rates_by_day"][<Label>] or data["rates_by_day"][<YYYY-MM-DD>]
# -----------------------
@st.cache_data(show_spinner=False)
def load_local_payload(path: Path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"⚠️ Failed to parse {path.name}: {e}")
        return {}

payload = load_local_payload(DATA_PATH)
rates_by_day = payload.get("rates_by_day", {})
generated_at = payload.get("generated_at")

if rates_by_day:
    st.success("✅ Loaded local rates from this repo.")
else:
    st.warning("ℹ️ No local data found yet. Place a JSON at data/beckley_rates.json with a 'rates_by_day' object.")

if generated_at:
    st.caption(f"Data generated at: {generated_at}")

# Try both label and ISO date keys
rates = rates_by_day.get(selected_label) or rates_by_day.get(checkin_iso) or {}

# Hotel list
hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    YOUR_HOTEL
]

# Section header
st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

# Build table helpers
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

# Bar chart
st.subheader("📊 Rate Comparison Chart")
chart_df = pd.DataFrame({
    "Hotel": [h for h in hotels if to_int_or_none(rates.get(h)) is not None],
    "Rate": [to_int_or_none(rates.get(h)) for h in hotels if to_int_or_none(rates.get(h)) is not None]
})
if not chart_df.empty:
    st.bar_chart(chart_df.set_index("Hotel"))
else:
    st.info("No numeric rates available to chart for this date.")

# Data format hint
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
