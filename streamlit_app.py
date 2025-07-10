import streamlit as st
import pandas as pd
from datetime import date, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Hotel Rate Tracker", page_icon="🏨")

# --- HEADER ---
st.title("🏨 Hotel Rate Comparison")
st.write("Tracking your hotel and competitors' nightly rates.")

# --- SETTINGS ---
your_hotel = "Comfort Inn Beckley"
competitors = ["Hampton Inn Beckley", "Microtel Beckley", "Tru by Hilton Beckley"]
checkin_date = date.today() + timedelta(days=3)

# --- FAKE DATA (replace later with real scraping/API) ---
rates = {
    your_hotel: 125,
    "Hampton Inn Beckley": 132,
    "Microtel Beckley": 121,
    "Tru by Hilton Beckley": 118,
}

# --- BUILD TABLE ---
data = []
your_rate = rates[your_hotel]

for hotel, rate in rates.items():
    delta = rate - your_rate
    direction = "+" if delta > 0 else ""
    data.append({
        "Hotel Name": hotel,
        "Check-in": checkin_date.strftime("%b %d"),
        "Rate ($)": rate,
        "Δ vs You": f"{direction}${delta}" if hotel != your_hotel else "—",
    })

df = pd.DataFrame(data)
st.dataframe(df, use_container_width=True)

# --- OPTIONAL NEXT: Add charts, alerts, or connect to real-time data

