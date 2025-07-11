import streamlit as st
import pandas as pd
from datetime import timedelta, datetime
import json
import requests
import pytz

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -----------------------
# Timezone-aware "today"
# -----------------------
eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern).date()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()

# -----------------------
# Friday logic (skips this Friday if today is Thursday)
# -----------------------
if weekday == 3:  # Thursday
    next_friday = today + timedelta(days=8)  # Skip to next week’s Friday
else:
    days_until_friday = (4 - weekday) % 7
    next_friday = today + timedelta(days=days_until_friday)

# -----------------------
# Date Picker Options
# -----------------------
date_options = {
    "Today": today,
    "Tomorrow": tomorrow,
    "Friday": next_friday
}
selected_label = st.selectbox("Select check-in date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -----------------------
# Load Live Data from GitHub
# -----------------------
DATA_URL = "https://raw.githubusercontent.com/amills-vpmgmt/hotel-rate-scraper/main/data/beckley_rates.json"
try:
    res = requests.get(DATA_URL)
    data = res.json()
    st.success("✅ Live rates loaded from GitHub.")
    rates_by_day = data["rates_by_day"]
except Exception as e:
    st.error("⚠️ Failed to load live data. Showing mock data.")
    rates_by_day = {}

# -----------------------
# Hotel List
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
# Get Rate Data
# -----------------------
rates = rates_by_day.get(selected_label, {})
your_rate = rates.get("Comfort Inn Beckley", 0)

# -----------------------
# Display Section Header
# -----------------------
st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

# -----------------------
# Build Comparison Table
# -----------------------
rows = []
for hotel in hotels:
    rate = rates.get(hotel, "N/A")
    delta = "—" if hotel == "Comfort Inn Beckley" else (
        f"{rate - your_rate:+}" if isinstance(rate, int) and isinstance(your_rate, int) else "N/A"
    )
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Rate": f"${rate}" if isinstance(rate, int) else rate,
        "Δ vs You": delta
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

# -----------------------
# Optional Bar Chart
# -----------------------
st.subheader("📊 Rate Comparison Chart")
chart_df = pd.DataFrame({
    "Hotel": hotels,
    "Rate": [rates.get(h, None) for h in hotels]
})
st.bar_chart(chart_df.set_index("Hotel"))
