import streamlit as st
import pandas as pd
from datetime import date, timedelta

# Setup
st.set_page_config(page_title="Beckley Hotel Rate Tracker", page_icon="🏨")
st.title("🏨 Beckley Hotel Rate Comparison")
st.write("Comparing your hotel with local competition for upcoming dates.")

# Date logic: show check-in date for "This Friday"
today = date.today()
days_until_friday = (4 - today.weekday()) % 7  # 0 = Monday, 4 = Friday
checkin_date = today + timedelta(days=days_until_friday)

# Hotel list (your hotel + competitors)
your_hotel = "Comfort Inn Beckley"
competitors = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley"
]

# Fake sample rates (replace with real data later)
fake_rates = {
    "Comfort Inn Beckley": 125,
    "Courtyard Beckley": 139,
    "Hampton Inn Beckley": 134,
    "Tru by Hilton Beckley": 121,
    "Fairfield Inn Beckley": 129,
    "Best Western Beckley": 119,
    "Country Inn Beckley": 124,
}

# Generate comparison table
all_hotels = [your_hotel] + competitors
your_rate = fake_rates[your_hotel]

rows = []
for hotel in all_hotels:
    rate = fake_rates.get(hotel, 0)
    delta = rate - your_rate
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Rate": f"${rate}",
        "Δ vs You": "—" if hotel == your_hotel else f"{'+' if delta > 0 else ''}${delta}"
    })

df = pd.DataFrame(rows)
st.subheader(f"📍 Beckley, WV — {checkin_date.strftime('%A (%b %d)')}")
st.dataframe(df, use_container_width=True)
