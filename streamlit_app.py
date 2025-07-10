import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Beckley Competitor Tracker", page_icon="📊")
st.title("📊 Beckley Competitor Hotel Rate Tracker")
st.write("Monitoring competitor prices to stay ahead in the Beckley market.")

# -- Check-in date dropdown --
date_options = {
    "Today": date.today(),
    "Tomorrow": date.today() + timedelta(days=1),
    "Friday": date.today() + timedelta((4 - date.today().weekday()) % 7)
}
selected_label = st.selectbox("Check-in Date:", list(date_options.keys()))
checkin_date = date_options[selected_label]

# -- Competitor hotels --
competitors = [
    "Comfort Inn Beckley",
    "Quality Inn Beckley",
    "Travelodge Beckley",
    "Super 8 Beckley",
    "Howard Johnson Beckley",
    "Baymont Inn Beckley"
]

# -- Mock rate data --
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

# -- Build DataFrame --
df = pd.DataFrame({
    "Hotel": list(rates.keys()),
    "Rate": list(rates.values())
})
df["Check-in"] = checkin_date.strftime("%A, %b %d")
df = df[["Hotel", "Check-in", "Rate"]]

# -- Show Table --
st.subheader(f"📍 Beckley — {selected_label} ({checkin_date.strftime('%b %d')})")
st.dataframe(df, use_container_width=True)

# -- Show Bar Chart --
st.subheader("📊 Rate Comparison Chart")
chart_df = df[["Hotel", "Rate"]].set_index("Hotel")
st.bar_chart(chart_df)

# -- Alert Summary (Avg vs Each Hotel) --
st.subheader("💬 Pricing Summary")
avg_rate = df["Rate"].mean()
for _, row in df.iterrows():
    delta = row["Rate"] - avg_rate
    direction = "above" if delta > 0 else "below" if delta < 0 else "equal to"
    st.write(f"• {row['Hotel']} is **${abs(delta):.0f} {direction}** the competitor average (${avg_rate:.0f}).")
