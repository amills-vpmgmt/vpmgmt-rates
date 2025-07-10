import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Beckley Hotel Tracker", page_icon="📋")
st.title("📋 Beckley Hotel Rate Tracker")
st.write("Monitoring rates for selected Beckley properties.")

# -- Date Picker --
date_options = {
    "Today": date.today(),
    "Tomorrow": date.today() + timedelta(days=1),
    "Friday": date.today() + timedelta((4 - date.today().weekday()) % 7)
}
selected_label = st.selectbox("Select check-in date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -- Hotels from the PDF list --
hotels = [
    "Courtyard Beckley",
    "Hampton Inn Beckley",
    "Tru by Hilton Beckley",
    "Fairfield Inn Beckley",
    "Best Western Beckley",
    "Country Inn Beckley",
    "Comfort Inn Beckley"
]

# -- Mock Rates --
mock_rates = {
    "Today": {
        "Courtyard Beckley": 139,
        "Hampton Inn Beckley": 134,
        "Tru by Hilton Beckley": 121,
        "Fairfield Inn Beckley": 129,
        "Best Western Beckley": 119,
        "Country Inn Beckley": 124,
        "Comfort Inn Beckley": 125,
    },
    "Tomorrow": {
        "Courtyard Beckley": 141,
        "Hampton Inn Beckley": 135,
        "Tru by Hilton Beckley": 122,
        "Fairfield Inn Beckley": 130,
        "Best Western Beckley": 120,
        "Country Inn Beckley": 126,
        "Comfort Inn Beckley": 126,
    },
    "Friday": {
        "Courtyard Beckley": 142,
        "Hampton Inn Beckley": 138,
        "Tru by Hilton Beckley": 124,
        "Fairfield Inn Beckley": 131,
        "Best Western Beckley": 122,
        "Country Inn Beckley": 127,
        "Comfort Inn Beckley": 129,
    }
}

rates = mock_rates[selected_label]
df = pd.DataFrame({
    "Hotel": hotels,
    "Check-in": checkin_date.strftime("%A, %b %d"),
    "Rate": [rates[hotel] for hotel in hotels]
})

st.subheader(f"📍 Beckley, WV — {selected_label} ({checkin_date.strftime('%b %d')})")
st.dataframe(df, use_container_width=True)

st.subheader("📊 Rate Comparison Chart")
chart_df = df[["Hotel", "Rate"]].set_index("Hotel")
st.bar_chart(chart_df)
