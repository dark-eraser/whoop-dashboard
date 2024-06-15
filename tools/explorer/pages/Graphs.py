from datetime import datetime, timedelta
import logging
import json
import logging
import math
import os
from pathlib import Path
import numpy as np
from typing import Tuple, Dict
import webbrowser
import pandas as pd
import streamlit as st
import plotly.express as px
from whoopy import WhoopClient, SPORT_IDS
from streamlit_extras.chart_container import chart_container
from streamlit_extras.metric_cards import style_metric_cards
from Client import WhoopClientSingleton

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(page_title="Whoop", page_icon="🏃‍♂️", layout="wide")

BASE_DIR = Path(os.path.dirname(__file__))
TOKEN_FILE = BASE_DIR / ".tokens" / "whoop_token.json"

# Load the config again if needed (or pass it through)
with open("../../config.json", "r") as f:
    config = json.load(f)

# Access the same instance of WhoopClientSingleton
whoop_client_singleton = WhoopClientSingleton(config)
client = whoop_client_singleton.get_client()
# retrieve the config

now = datetime.now()

# Calculate minutes rounded to the nearest 10
rounded_minutes = math.floor(now.minute / 10) * 10

# Replace seconds and microseconds, and set minutes to the rounded value
today = now.replace(second=0, microsecond=0, minute=rounded_minutes)

# Sidebar
st.sidebar.header("Whoop API")
baseline_days= st.sidebar.slider("Days to load", 1, 180, 60, 1)
PERIOD_START,PERIOD_END = pd.to_datetime(st.sidebar.date_input("Select Period to Compare Current Week with", (today - timedelta(baseline_days), today), today - timedelta(baseline_days),today,format="MM.DD.YYYY"))

@st.cache_data()
def load_metrics(baseline_days: int, today) -> Dict:
    start = today - timedelta(days=baseline_days + 1)
    rec, _ = client.recovery.collection_df(start=start, end=today, get_all_pages=True)
    sleep, _ = client.sleep.collection_df(start=start, end=today, get_all_pages=True)  
    # cycle, _ = client.cycle.collection_df(start=start, end=today, get_all_pages=True)
    workout, _ = client.workout.collection_df(
        start=start, end=today, get_all_pages=True
    )
    return rec, sleep, workout

class CurrentPeriodData:
    sleep_efficiency: float
    recovery_score: float
    time_in_bed: float
    sleep_consistency: float
    period_start: datetime
    period_end: datetime
    
rec, sleep, workout = load_metrics(baseline_days, today)
current_period_data = CurrentPeriodData()


# display recovery score
st.subheader("Recovery Score", divider="green")
fig = px.line(rec[(pd.to_datetime(rec["created_at"]) >= PERIOD_START) & (pd.to_datetime(rec["created_at"]) <= PERIOD_END)], x="updated_at", y="score.recovery_score")
fig.update_yaxes(range=[1,100])
st.plotly_chart(fig,use_container_width=True)

# display sleep efficiency
st.subheader("Sleep Efficiency", divider="blue")
fig = px.line(sleep[(pd.to_datetime(sleep["start"]) >= PERIOD_START) & (pd.to_datetime(sleep["start"]) <= PERIOD_END)], x="start", y="score.sleep_efficiency_percentage")
fig.update_yaxes(range=[1,100])
st.plotly_chart(fig,use_container_width=True)


# display workout strain
st.subheader("Workout Strain", divider="orange")
fig = px.scatter(workout[(pd.to_datetime(workout["start"]) >= PERIOD_START) & (pd.to_datetime(workout["start"]) <= PERIOD_END)], x="start", y="score.strain", color = "score.strain", color_continuous_scale=px.colors.sequential.Viridis, hover_data=["score.strain"], size="score.average_heart_rate")
fig.update_yaxes(range=[0,20])
st.plotly_chart(fig,use_container_width=True)

workout["score.kilocalories"] = workout["score.kilojoule"] / 4.184
# display workout calories
st.subheader("Workout Calories", divider="orange")
fig = px.line(workout[(pd.to_datetime(workout["start"]) >= PERIOD_START) & (pd.to_datetime(workout["start"]) <= PERIOD_END)], x="start", y="score.kilocalories")
st.plotly_chart(fig,use_container_width=True)


# display workout HR
st.subheader("Workout HR", divider="orange")
fig = px.line(workout[(pd.to_datetime(workout["start"]) >= PERIOD_START) & (pd.to_datetime(workout["start"]) <= PERIOD_END)], x="start", y="score.average_heart_rate")
fig.update_yaxes(range=[0,200])
st.plotly_chart(fig,use_container_width=True)

# # display workout HRV
# st.subheader("Workout HRV")
# fig = px.line(workout, x="start", y="score.hrv_rmssd_milli")
# st.plotly_chart(fig)

# # display workout SPO2
# st.subheader("Workout SPO2")
# fig = px.line(workout, x="start", y="score.spo2_percentage")
# st.plotly_chart(fig)

# display workout Temp
# st.subheader("Workout Temp")
# fig = px.line(workout, x="start", y="score.skin_temp_celsius")
# st.plotly_chart(fig)
