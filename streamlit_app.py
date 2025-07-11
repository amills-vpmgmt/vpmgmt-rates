import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import json
import requests

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -----------------------
# Date Picker with Correct Friday Logic
# -----------------------
today = date.today()
weekday = today.weekday()  # Monday = 0 ... Sunday = 6

# Handle Friday date logic
if weekday == 3:  # Thursday
    tomorrow = today + timedelta(days=1)          # This Friday
    next_friday = today + timedelta(days=8)       # Next Friday
elif weekday < 4:  # Monday to Wednesday
    tomorrow = today + timedelta(days=1)
    next_friday = today + timedelta(days=(4 - weekday))
else:  # Friday to Sunday
    tomorrow = today + timedelta(days=1)
    next_friday = today + timedelta(days=(7 - weekday + 4))

date_options = {
    "Today": today,
    "Tomorrow": tomorrow,
    "Friday": next_friday
}

selected_label = st.selectbox("Select check-in date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -----------------------
# Hotels (your properties)
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
# Load Rates from GitHub JSON (live)
# -----------------------
json_url = "https://raw.githubusercontent.com/amills-vpmgmt/hotel-rate-scraper/main/data/beckley_rates.json"

try:
    response = requests.get(json_url)
    response.raise_for_status()
    data = response.json()

    rates = data["rates_by_day"].get(selected_label, {})
    your_rate = rates.get("Comfort Inn Beckley", 0)
    st.success("✅ Live rates loaded from GitHub.")

except Exception as e:
    st.error(f"⚠️ Failed to load live data. Showing blank rates.\n\n{e}")
    rates = {}
    your_rate = 0

# -----------------------
# Display Header
# -----------------------
st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

# -----------------------
# Build Rate Comparison Table
# -----------------------
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

# Show interactive table
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
