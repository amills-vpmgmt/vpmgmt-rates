import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -----------------------
# Date Picker with Friday Fix
# -----------------------
today = date.today()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()

# Handle Friday rollover logic
if weekday == 3:  # Thursday
    next_friday = today + timedelta(days=7 - weekday + 4)  # Next Friday
else:
    next_friday = today + timedelta((4 - weekday) % 7)

date_options = {
    "Today": today,
    "Tomorrow": tomorrow if weekday != 3 else today + timedelta(days=2),
    "Friday": next_friday
}

selected_label = st.selectbox("Select check-in date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -----------------------
# Hotels (your reference list)
# -----------------------
hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    "Comfort Inn Beckley"
]

# -----------------------
# Load rates from GitHub JSON
# -----------------------
json_url = "https://raw.githubusercontent.com/amills-vpmgmt/hotel-rate-scraper/main/data/beckley_rates.json"

try:
    response = requests.get(json_url)
    response.raise_for_status()
    live_rates = response.json()
    rates = live_rates.get("rates_by_day", {}).get(selected_label, {})
    your_rate = rates.get("Comfort Inn Beckley", 0)
    st.success("✅ Live rates loaded from GitHub.")
except Exception as e:
    st.error(f"⚠️ Failed to load live rates.\n\n{e}")
    rates = {}
    your_rate = 0

# -----------------------
# Display Header with Full Date
# -----------------------
st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

# -----------------------
# Build Comparison Table
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
st.dataframe(df, use_container_width=True)

# -----------------------
# Bar Chart (Optional)
# -----------------------
st.subheader("📊 Rate Comparison Chart")
chart_df = pd.DataFrame({
    "Hotel": hotels,
    "Rate": [rates.get(h, None) for h in hotels]
})
chart_df = chart_df.dropna()

if not chart_df.empty:
    st.bar_chart(chart_df.set_index("Hotel"))
else:
    st.warning("No rates available to display chart.")
