import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Hotel Rate Tracker", page_icon="🏨")
st.title("🏨 Hotel Rate Comparison Dashboard")
st.write("Tracking your hotel's nightly rates against nearby competitors.")

# Define check-in date logic
checkin_date = date.today() + timedelta(days=3)

# Define hotel groups per region
hotels_by_region = {
    "Beckley, WV": {
        "your_hotel": "Comfort Inn Beckley",
        "competitors": [
            "Hampton Inn Beckley",
            "Tru by Hilton Beckley",
            "Microtel Inn Beckley"
        ]
    },
    "Princeton, WV": {
        "your_hotel": "Quality Inn Princeton",
        "competitors": [
            "Microtel Inn Princeton",
            "Hampton Inn Princeton",
            "Sleep Inn & Suites Princeton"
        ]
    },
    "Bluefield, WV": {
        "your_hotel": "Quality Inn Bluefield",
        "competitors": [
            "Comfort Inn Bluefield",
            "Econo Lodge Near Bluefield College",
            "Budget Inn Bluefield"
        ]
    }
}

# Select region
region = st.selectbox("Select region:", list(hotels_by_region.keys()))
region_hotels = hotels_by_region[region]
your_hotel = region_hotels["your_hotel"]
competitors = region_hotels["competitors"]

# Placeholder: Fake rates for now
fake_rates = {
    "Comfort Inn Beckley": 125,
    "Hampton Inn Beckley": 132,
    "Tru by Hilton Beckley": 118,
    "Microtel Inn Beckley": 121,
    "Quality Inn Princeton": 109,
    "Microtel Inn Princeton": 115,
    "Hampton Inn Princeton": 124,
    "Sleep Inn & Suites Princeton": 113,
    "Quality Inn Bluefield": 105,
    "Comfort Inn Bluefield": 112,
    "Econo Lodge Near Bluefield College": 99,
    "Budget Inn Bluefield": 91,
}

# Build table
all_hotels = [your_hotel] + competitors
your_rate = fake_rates.get(your_hotel, 0)
table_data = []

for hotel in all_hotels:
    rate = fake_rates.get(hotel, 0)
    delta = rate - your_rate
    table_data.append({
        "Hotel Name": hotel,
        "Check-in": checkin_date.strftime("%b %d"),
        "Rate ($)": rate,
        "Δ vs You": "—" if hotel == your_hotel else f"{'+' if delta > 0 else ''}${delta}"
    })

st.subheader(f"📍 {region} - Check-in {checkin_date.strftime('%A, %B %d')}")
st.dataframe(pd.DataFrame(table_data), use_container_width=True)


