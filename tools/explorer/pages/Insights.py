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
import logging

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
baseline_days= st.sidebar.slider("Days to Load", 1, 180, 60, 1)
PERIOD_START,PERIOD_END = pd.to_datetime(st.sidebar.date_input("Select Period", (today - timedelta(baseline_days), today), today - timedelta(baseline_days),today,format="MM.DD.YYYY"))

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
# using "end" since sleep cycles can start on the same day they end
def preprocessing():
    rec, sleep, workout = load_metrics(baseline_days, today)
    filtered_sleep = sleep.copy()
    filtered_sleep["day_of_week"]=filtered_sleep["end"].dt.weekday
    filtered_sleep["day_type"]=filtered_sleep["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    st.write(filtered_sleep[0:10])
    rec_copy = rec.copy()
    rec_copy["day_of_week"]=rec_copy["created_at"].dt.weekday
    rec_copy["day_type"]=rec_copy["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    workout_copy = workout.copy()
    workout_copy["day_of_week"]=workout_copy["start"].dt.weekday
    workout_copy["day_type"]=workout_copy["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    return rec_copy, filtered_sleep, workout_copy

rec_copy, filtered_sleep, workout_copy = preprocessing()

st.header("Week VS Weekend")
st.subheader("Sleep", divider="blue")
col1, col2 = st.columns(2)
with col1:
    plot_type = st.selectbox("Select plot type", ["Histogram", "Box Plot", "Strip Plot"])

with col2:
    metric_type=st.selectbox("Select metric type", ["Sleep Efficiency", "Sleep Performance", "Time in Bed", "Sleep Consistency"])
    
metric_column_map = {
    "Sleep Efficiency": ("score.sleep_efficiency_percentage", "Sleep Efficiency measures the percentage of the time you spendin bed actually asleep."),
    "Sleep Performance": ("score.sleep_performance_percentage", "Sleep Performance compares your actual sleep duration to your sleep need."),
    "Sleep Consistency": ("score.sleep_consistency_percentage", "Sleep Consistency measures how similar your sleep patterns are over an X day period."),
}
# Get the selected metric column
selected_metric, metric_explanation = metric_column_map[metric_type]
st.info(metric_explanation, icon="ℹ️")
# st.separator()

# Plot based on selected type and metric
if plot_type == "Histogram":
    fig = px.histogram(filtered_sleep, x=selected_metric, color="day_type")
    fig.update_yaxes(range=[1, 50])
    st.plotly_chart(fig, use_container_width=True)
elif plot_type == "Box Plot":
    fig = px.box(filtered_sleep, y=selected_metric, x="day_type")
    st.plotly_chart(fig, use_container_width=True)
elif plot_type == "Strip Plot":
    fig = px.strip(filtered_sleep, x='day_type', y=selected_metric, title=f'Weekday vs Weekend {metric_type} (Strip Plot)')
    st.plotly_chart(fig, use_container_width=True)
