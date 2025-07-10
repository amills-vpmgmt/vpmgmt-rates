import streamlit as st
import pandas as pd
from datetime import date, timedelta
import math

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📝")
st.title("📝 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# Date Picker Options
today = date.today()
tomorrow = today + timedelta(days=1)
weekday = today.weekday()

# Special Friday logic
if weekday == 3:  # Thursday
    next_friday = today + timedelta(days=7 - weekday + 4)  # Skip to next Friday
else:
    next_friday = today + timedelta((4 - weekday) % 7) #current friday if it isnt thursday

date_options = {
    "Today": today,
    "Tomorrow": tomorrow if not (weekday == 3) else today + timedelta(days=2),
    "Friday": next_friday
}

selected_label = st.selectbox("Select check-in date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# Competitor hotels (from your sheet)
hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    "Comfort Inn Beckley"  # Your hotel (for baseline)
]

# Example mock pricing (replace with real scraped/API data)
mock_rates = {
    "Today": {
        "Courtyard Beckley": 142,
        "Hampton Inn Beckley": 138,
        "Tru by Hilton Beckley": 124,
        "Fairfield Inn Beckley": 131,
        "Best Western Beckley": 122,
        "Country Inn Beckley": 127,
        "Comfort Inn Beckley": 129
    },
    "Tomorrow": {
        "Courtyard Beckley": 145,
        "Hampton Inn Beckley": 139,
        "Tru by Hilton Beckley": 127,
        "Fairfield Inn Beckley": 132,
        "Best Western Beckley": 125,
        "Country Inn Beckley": 130,
        "Comfort Inn Beckley": 130
    },
    "Friday": {
        "Courtyard Beckley": 149,
        "Hampton Inn Beckley": 140,
        "Tru by Hilton Beckley": 128,
        "Fairfield Inn Beckley": 133,
        "Best Western Beckley": 126,
        "Country Inn Beckley": 131,
        "Comfort Inn Beckley": 132
    }
}

rates = mock_rates.get(selected_label, {})
your_rate = rates.get("Comfort Inn Beckley", 0)

# Display Header with Date
st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%A, %b %d')})")

# Build comparison table
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

st.table(pd.DataFrame(rows))

# Optional bar chart
st.subheader("📊 Rate Comparison Chart")
chart_df = pd.DataFrame({
    "Hotel": hotels,
    "Rate": [rates.get(h, None) for h in hotels]
})
st.bar_chart(chart_df.set_index("Hotel"))
