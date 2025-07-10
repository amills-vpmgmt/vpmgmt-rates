import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Beckley Competitor Rate Tracker", page_icon="📊")
st.title("📊 Beckley Competitor Hotel Rate Tracker")
st.write("Monitoring competitor prices to stay ahead in the Beckley market.")

# -- Date Picker (Today, Tomorrow, Friday) --
date_options = {
    "Today": date.today(),
    "Tomorrow": date.today() + timedelta(days=1),
    "Friday": date.today() + timedelta((4 - date.today().weekday()) % 7)
}
selected_label = st.selectbox("Check-in Date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -- Competitor Hotels in Beckley (not owned by VPMGMT) --
competitors = [
    "Comfort Inn Beckley",
    "Quality Inn Beckley",
    "Travelodge Beckley",
    "Super 8 Beckley",
    "Howard Johnson Beckley",
    "Baymont Inn Beckley"
]

# -- Mock Rates by Date (replace with real scraped data later) --
mock_rates = {
    "Today": {
        "Comfort Inn Beckley": 122,
        "Quality Inn Beckley": 118,
        "Travelodge Beckley": 109,
        "Super 8 Beckley": 101,
        "Howard Johnson Beckley": 105,
        "Baymont Inn Beckley": 111,
    },
    "Tomorrow": {
        "Comfort Inn Beckley": 124,
        "Quality Inn Beckley": 119,
        "Travelodge Beckley": 110,
        "Super 8 Beckley": 102,
        "Howard Johnson Beckley": 106,
        "Baymont Inn Beckley": 112,
    },
    "Friday": {
        "Comfort Inn Beckley": 127,
        "Quality Inn Beckley": 123,
        "Travelodge Beckley": 114,
        "Super 8 Beckley": 105,
        "Howard Johnson Beckley": 109,
        "Baymont Inn Beckley": 116,
    }
}

rates = mock_rates[selected_label]

# -- Display Table --
rows = []
for hotel in competitors:
    rows.append({
        "Hotel": hotel,
        "Check-in": checkin_date.strftime("%A, %b %d"),
        "Rate": f"${rates[hotel]}"
    })

st.subheader(f"📍 Competitor Prices in Beckley — {selected_label}")
st.dataframe(pd.DataFrame(rows), use_container_width=True)
