
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
from Client import WhoopClientSingleton  # Import the WhoopClientSingleton class

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

# retrieve client data
if client:
    user = client.user.profile()
    st.success(f"Logged in as {user.first_name} {user.last_name} ({user.user_id})")
else:
    st.error("Client setup failed.")
    st.stop()

# Sidebar
st.sidebar.header("Whoop API")
st.sidebar.baseline_days = st.slider("Days to load", 1, 180, 30, 1)

def helper_milliseconds_to_hours(millis):
    return millis / 1000 / 60 / 60

def helper_milliseconds_to_hours_minutes(milliseconds):
    # Total seconds from milliseconds
    total_seconds = milliseconds / 1000
    
    # Calculate hours
    hours = int(total_seconds // 3600)
    
    # Calculate remaining minutes
    minutes = int((total_seconds % 3600) // 60)
    
    return hours, minutes

def helper_delta_percentage(old_value, new_value):
    percentage_change = ((new_value - old_value) / old_value) * 100
    return percentage_change

# Load the latest metrics
baseline_days = st.slider("Days to load", 1, 180, 30, 1)

@st.cache_data()
def load_metrics(baseline_days: int, today) -> Dict:
    start = today - timedelta(days=baseline_days + 1)
    rec, _ = client.recovery.collection_df(start=start, end=today, get_all_pages=True)
    sleep, _ = client.sleep.collection_df(start=start, end=today, get_all_pages=True)  
    workout, _ = client.workout.collection_df(start=start, end=today, get_all_pages=True)
    return rec, sleep, workout

with st.spinner(text="loading metrics..."):
    rec, sleep, workout = load_metrics(baseline_days, today)
    sleep_nonap = sleep[sleep["nap"] == False]

# Create a Plotly graph for HRV trends
def plot_hrv_trends(rec):
    fig = px.line(
        rec,
        x=rec['created_at'],
        y=rec['score.hrv_rmssd_milli'],
        title="HRV Trends Over Time",
        labels={"created_at": "Date", "score.hrv_rmssd_milli": "HRV (ms)"},
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="HRV (ms)",
        template="plotly_white"
    )
    return fig

# Display the HRV graph
st.header("HRV Trends")
hrv_fig = plot_hrv_trends(rec)
st.plotly_chart(hrv_fig)

# Other metrics and analysis
# ...