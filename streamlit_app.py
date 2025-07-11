import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -----------------------
# Timezone-Aware Date (Eastern Time)
# -----------------------
eastern = pytz.timezone("US/Eastern")
today_dt = datetime.now(eastern)
today = today_dt.date()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()  # Monday = 0, Thursday = 3, Friday = 4, Sunday = 6

# Determine proper Friday
if weekday == 3:  # Thursday → Friday = tomorrow
    next_friday = today + timedelta(days=1)
elif weekday < 4:  # Mon–Wed → Friday = this week
    next_friday = today + timedelta(days=(4 - weekday))
else:  # Fri–Sun → Friday = next week
    next_friday = today + timedelta(days=(7 - weekday + 4))

date_options = {
    "Today": today,
    "Tomorrow": tomorrow,
    "Friday": next_friday
}

selected_label = st.selectbox("Select check-in date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -----------------------
# Hotels List
# -----------------------
hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    "Comfort Inn Beckley"  # your reference hotel
]

# -----------------------
# Load rates from GitHub
# -----------------------
DATA_URL = "https://raw.githubusercontent.com/amills-vpmgmt/hotel-rate-scraper/main/data/beckley_rates.json"

try:
    response = requests.get(DATA_URL)
    response.raise_for_status()
    data = response.json()
    rates = data["rates_by_day"].get(selected_label, {})
    st.success("✅ Live rates loaded from GitHub.")
except Exception as e:
    st.error("❌ Could not load live rate data.")
    rates = {}

# -----------------------
# Display Header
# -----------------------
st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

# -----------------------
# Build Table
# -----------------------
your_rate = rates.get("Comfort Inn Beckley", 0)
rows = []

for hotel in hotels:
    rate = rates.get(hotel, "N/A")
    delta = "—" if hotel == "Comfort Inn Beckley" else f"{rate - your_rate:+}" if isinstance(rate, int) else "N/A"
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Rate": f"${rate}" if isinstance(rate, int) else rate,
        "Δ vs You": delta
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

# -----------------------
# Bar Chart
# -----------------------
st.subheader("📊 Rate Comparison Chart")
chart_df = pd.DataFrame({
    "Hotel": hotels,
    "Rate": [rates.get(h, None) for h in hotels]
})
st.bar_chart(chart_df.set_index("Hotel"))
