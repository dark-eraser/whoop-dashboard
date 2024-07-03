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
from whoopy import SPORT_IDS
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
    sleep_no_nap = sleep[sleep["nap"] == False]
    sleep_nap = sleep[sleep["nap"] == True]

    filtered_sleep = sleep_no_nap.copy()
    
    filtered_sleep["day_of_week"]=filtered_sleep["end"].dt.weekday
    filtered_sleep["day_type"]=filtered_sleep["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    filtered_sleep["score.stage_summary.time_in_bed_hours"]=filtered_sleep["score.stage_summary.total_in_bed_time_milli"].apply(lambda x: x/1000/60/60)
    filtered_sleep["score.stage_summary.total_awake_time_hours"]=filtered_sleep["score.stage_summary.total_awake_time_milli"].apply(lambda x: x/1000/60/60)
    filtered_sleep["score.stage_summary.total_light_sleep_time_minutes"]=filtered_sleep["score.stage_summary.total_light_sleep_time_milli"].apply(lambda x: x/1000/60)
    filtered_sleep["score.stage_summary.total_slow_wave_sleep_time_minutes"]=filtered_sleep["score.stage_summary.total_slow_wave_sleep_time_milli"].apply(lambda x: x/1000/60)
    filtered_sleep["score.stage_summary.total_rem_sleep_time_minutes"]=filtered_sleep["score.stage_summary.total_rem_sleep_time_milli"].apply(lambda x: x/1000/60)
    filtered_sleep["score.stage_summary.total_sleep_time_hours"]=filtered_sleep["score.stage_summary.time_in_bed_hours"] - filtered_sleep["score.stage_summary.total_awake_time_hours"]
    
    # st.write(filtered_sleep[0:10])
    rec_copy = rec.copy()
    rec_copy["day_of_week"]=rec_copy["created_at"].dt.weekday
    rec_copy["day_type"]=rec_copy["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    
    workout_copy = workout.copy()
    workout_copy["day_of_week"]=workout_copy["start"].dt.weekday
    workout_copy["day_type"]=workout_copy["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    workout_copy["score.kilocalories"]=workout_copy["score.kilojoule"]
    workout_copy["sport"] = workout_copy["sport_id"].map(SPORT_IDS)
    workout_copy["score.zone_duration.zone_zero_minutes"]=workout_copy["score.zone_duration.zone_zero_milli"].apply(lambda x: x/1000/60)
    workout_copy["score.zone_duration.zone_one_minutes"]=workout_copy["score.zone_duration.zone_one_milli"].apply(lambda x: x/1000/60)
    workout_copy["score.zone_duration.zone_two_minutes"]=workout_copy["score.zone_duration.zone_two_milli"].apply(lambda x: x/1000/60)
    workout_copy["score.zone_duration.zone_three_minutes"]=workout_copy["score.zone_duration.zone_three_milli"].apply(lambda x: x/1000/60)
    workout_copy["score.zone_duration.zone_four_minutes"]=workout_copy["score.zone_duration.zone_four_milli"].apply(lambda x: x/1000/60)
    workout_copy["score.zone_duration.zone_five_minutes"]=workout_copy["score.zone_duration.zone_five_milli"].apply(lambda x: x/1000/60)
    return rec_copy, filtered_sleep, workout_copy

sleep_metric_column_map = {
    "Sleep Efficiency": ("score.sleep_efficiency_percentage", "Sleep Efficiency measures the percentage of the time you spend in bed actually asleep.", True),
    "Sleep Performance": ("score.sleep_performance_percentage", "Sleep Performance compares your actual sleep duration to your sleep need.", True),
    "Sleep Consistency": ("score.sleep_consistency_percentage", "Sleep Consistency measures how similar your sleep patterns are over an X day period.", True),
    "Time in Bed": ("score.stage_summary.time_in_bed_hours", "", False),
    "Total Awake Time": ("score.stage_summary.total_awake_time_hours", "", False),
    "Total Light Sleep Time": ("score.stage_summary.total_light_sleep_time_minutes", "", False),
    "Total Slow Wave Sleep Time": ("score.stage_summary.total_slow_wave_sleep_time_minutes", "", False),
    "Total REM Sleep Time": ("score.stage_summary.total_rem_sleep_time_minutes", "", False),
    "Total Sleep Time": ("score.stage_summary.total_sleep_time_hours", "", False),
    "Sleep Cycle Count": ("score.stage_summary.sleep_cycle_count", "", False),
    "Disturbance Count": ("score.stage_summary.disturbance_count", "", False),
    
}
inverse_metric_mapping = {v: k for k, v in sleep_metric_column_map.items()}

recovery_metric_column_map = {
    "Recovery Score": ("score.recovery_score", "Recovery Score is a measure of how well you have recovered from previous day's strain.", True),
    "Resting Heart Rate": ("score.resting_heart_rate", "Resting Heart Rate is the number of times your heart beats per minute while at rest.", True),
    "HRV": ("score.hrv_rmssd_milli", "HRV is a measure of the variation in time between each heartbeat.", True),
    "SPO²": ("score.spo2_percentage", "SPO² is a measure of the amount of oxygen in your blood.", True),
    "Skin Temp": ("score.skin_temp_celsius", "Skin Temp is the temperature of your skin in degrees Celsius.", True),
}    

workout_metric_column_map = {
    "Strain": ("score.strain", "Strain is a measure of how much stress you put on your body during a workout.", True),
    "Kilocalories": ("score.kilocalories", "Kilocalories is a measure of how many calories you burned during a workout.", True),
    "Average Heart Rate": ("score.average_heart_rate", "Average Heart Rate is the average number of times your heart beats per minute during a workout.", True),
    "Max Heart Rate": ("score.max_heart_rate", "Max Heart Rate is the maximum number of times your heart beats per minute during a workout.", True),
    "Distance Meter" : ("score.distance_meter", "Distance Meter is the distance you covered during a workout in meters.", True),
    "Altitue Gain Meter" : ("score.altitude_gain_meter", "Altitue Gain Meter is the altitude you gained during a workout in meters.", True),
    "Altitude Change Meter" : ("score.altitude_change_meter", "Altitude Change Meter is the altitude you changed during a workout in meters.", True),
    "Zone Zero Duration" : ("score.zone_duration.zone_zero_minutes", "Zone Zero Duration is the time you spent in zone zero during a workout in minutes.", True),
    "Zone One Duration" : ("score.zone_duration.zone_one_minutes", "Zone One Duration is the time you spent in zone one during a workout in minutes.", True),
    "Zone Two Duration" : ("score.zone_duration.zone_two_minutes", "Zone Two Duration is the time you spent in zone two during a workout in minutes.", True),
    "Zone Three Duration" : ("score.zone_duration.zone_three_minutes", "Zone Three Duration is the time you spent in zone three during a workout in minutes.", True),
    "Zone Four Duration" : ("score.zone_duration.zone_four_minutes", "Zone Four Duration is the time you spent in zone four during a workout in minutes.", True),
    "Zone Five Duration" : ("score.zone_duration.zone_five_minutes", "Zone Five Duration is the time you spent in zone five during a workout in minutes.", True),
}
    
with st.spinner(text="loading metrics..."):
    rec_copy, filtered_sleep, workout_copy = preprocessing()

st.header("Sleep")

# Time Series Plot
st.subheader('Time Series Analysis')
# with st.container():
sleep_col1, sleep_col2 = st.columns([0.8,0.2], gap="large")

with sleep_col2:
    metric_time_series = st.selectbox("Select metric for Time Series", list(sleep_metric_column_map.keys()))

    st.metric(label=f"Lowest {metric_time_series}", value=f"{filtered_sleep[sleep_metric_column_map[metric_time_series][0]].min():.2f}")
    st.metric(label=f"Highest {metric_time_series}", value=f"{filtered_sleep[sleep_metric_column_map[metric_time_series][0]].max():.2f}")
    st.metric(label=f"Average {metric_time_series}", value=f"{filtered_sleep[sleep_metric_column_map[metric_time_series][0]].mean():.2f}")
with sleep_col1:
    selected_time_series_metric = sleep_metric_column_map[metric_time_series][0]
    fig_time_series = px.line(filtered_sleep, x='end', y=selected_time_series_metric, title=f'Time Series of {metric_time_series}')
    st.plotly_chart(fig_time_series, use_container_width=True)


st.header("Recovery")
recovery_col1, recovery_col2 = st.columns([0.8,0.2], gap="large")
with recovery_col2:
    metric_recovery = st.selectbox("Select metric for Time Series", list(recovery_metric_column_map.keys()))

    st.metric(label=f"Lowest {metric_recovery}", value=f"{rec_copy[recovery_metric_column_map[metric_recovery][0]].min():.2f}")
    st.metric(label=f"Highest {metric_recovery}", value=f"{rec_copy[recovery_metric_column_map[metric_recovery][0]].max():.2f}")
    st.metric(label=f"Average {metric_recovery}", value=f"{rec_copy[recovery_metric_column_map[metric_recovery][0]].mean():.2f}")
with recovery_col1:
    selected_recovery_metric = recovery_metric_column_map[metric_recovery][0]
    fig_recovery = px.line(rec_copy, x='created_at', y=selected_recovery_metric, title=f'Time Series of {metric_recovery}')
    st.plotly_chart(fig_recovery, use_container_width=True)

st.header("Workout")
workout_col1, workout_col2 = st.columns([0.8,0.2], gap="large")
with workout_col2:
    metric_workout = st.selectbox("Select metric for Time Series", list(workout_metric_column_map.keys()))

    st.metric(label=f"Lowest {metric_workout}", value=f"{workout_copy[workout_metric_column_map[metric_workout][0]].min():.2f}")
    st.metric(label=f"Highest {metric_workout}", value=f"{workout_copy[workout_metric_column_map[metric_workout][0]].max():.2f}")
    st.metric(label=f"Average {metric_workout}", value=f"{workout_copy[workout_metric_column_map[metric_workout][0]].mean():.2f}")
with workout_col1:
    selected_workout_metric = workout_metric_column_map[metric_workout][0]
    fig_workout = px.line(workout_copy, x='start', y=selected_workout_metric, title=f'Time Series of {metric_workout}')
    st.plotly_chart(fig_workout, use_container_width=True)

# style_metric_cards(border_radius_px=14, border_color="#9AD8E1")
