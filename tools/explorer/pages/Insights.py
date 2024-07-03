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
    # st.write(filtered_sleep[0:10])
    rec_copy = rec.copy()
    rec_copy["day_of_week"]=rec_copy["created_at"].dt.weekday
    rec_copy["day_type"]=rec_copy["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    workout_copy = workout.copy()
    workout_copy["day_of_week"]=workout_copy["start"].dt.weekday
    workout_copy["day_type"]=workout_copy["day_of_week"].apply(lambda x: "Weekend" if x>=5 else "Weekday")
    return rec_copy, filtered_sleep, workout_copy

with st.spinner(text="loading metrics..."):
    rec_copy, filtered_sleep, workout_copy = preprocessing()

show_info = True

st.header("Week VS Weekend")
st.subheader("Sleep", divider="blue")

metric_column_map = {
    "Sleep Efficiency": ("score.sleep_efficiency_percentage", "Sleep Efficiency measures the percentage of the time you spend in bed actually asleep.", True),
    "Sleep Performance": ("score.sleep_performance_percentage", "Sleep Performance compares your actual sleep duration to your sleep need.", True),
    "Sleep Consistency": ("score.sleep_consistency_percentage", "Sleep Consistency measures how similar your sleep patterns are over an X day period.", True),
    "Time in Bed": ("score.stage_summary.time_in_bed_hours", "", False),
    "Total Awake Time": ("score.stage_summary.total_awake_time_hours", "", False),
    "Total Light Sleep Time": ("score.stage_summary.total_light_sleep_time_minutes", "", False),
    "Total Slow Wave Sleep Time": ("score.stage_summary.total_slow_wave_sleep_time_minutes", "", False),
    "Total REM Sleep Time": ("score.stage_summary.total_rem_sleep_time_minutes", "", False),
    "Sleep Cycle Count": ("score.stage_summary.sleep_cycle_count", "", False),
    "Disturbance Count": ("score.stage_summary.disturbance_count", "", False),
    
}
inverse_metric_mapping = {v: k for k, v in metric_column_map.items()}

col1, col2 = st.columns(2)
with col1:
    plot_type = st.selectbox("Select plot type", ["Histogram", "Box Plot", "Strip Plot"])

with col2:
    metric_type=st.selectbox("Select metric type", metric_column_map.keys())
    

# Get the selected metric column
selected_metric, metric_explanation, show_info = metric_column_map[metric_type]
if show_info:
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
    
    
    
st.subheader("Time Series Analysis")
metric_time_series = st.selectbox("Select metric for Time Series", list(metric_column_map.keys()))
selected_time_series_metric = metric_column_map[metric_time_series][0]
fig_time_series = px.line(filtered_sleep, x='end', y=selected_time_series_metric, color='day_type', title=f'Time Series of {metric_time_series}')
st.plotly_chart(fig_time_series, use_container_width=True)


def find_strong_correlations(corr_matrix, threshold=0.5):
    strong_pairs = []
    # Iterate only over the upper triangle to avoid duplicates
    for col in range(len(corr_matrix.columns)):
        for row in range(col + 1, len(corr_matrix.columns)):  # start from col + 1 to avoid self-correlation
            corr_value = corr_matrix.iloc[row, col]
            if abs(corr_value) > threshold:
                strong_pairs.append((corr_matrix.columns[col], corr_matrix.index[row], corr_value))
    return strong_pairs


corr_matrix = filtered_sleep.drop(columns=["id", "nap", "start", "end", "created_at", "updated_at", "score.stage_summary.total_in_bed_time_milli","score.stage_summary.total_rem_sleep_time_milli","score.stage_summary.total_light_sleep_time_milli","score.stage_summary.total_awake_time_milli", "score.stage_summary.total_slow_wave_sleep_time_milli","score.stage_summary.total_no_data_time_milli"]).select_dtypes(include=[np.number]).corr()

# Allow user to set the correlation threshold

# Re-calculate strong correlations based on user input
st.header("Correlation Findings")
corr_threshold = st.number_input('Set Correlation Threshold', value=0.5, min_value=0.0, max_value=1.0, step=0.05)
strong_correlations = find_strong_correlations(corr_matrix, corr_threshold)
with st.expander("Show Correlation Matrix"):
    fig_corr = px.imshow(corr_matrix, text_auto=True, aspect="auto", 
                        labels=dict(color='Correlation coefficient'),
                        title='Correlation Matrix of Sleep Metrics', color_continuous_scale='Viridis')
    st.plotly_chart(fig_corr, use_container_width=True)
if strong_correlations:
    for col, row, value in strong_correlations:
        friendly_col = inverse_metric_mapping.get(col, col)
        friendly_row = inverse_metric_mapping.get(row, row)
    
        if value >=0.74 or value <= -0.75:
            if value >= 0:
                st.write(f"**A higher value of {friendly_col} is associated with a higher value of {friendly_row}**")
            else:
                st.write(f"**A higher value of {friendly_col} is associated with a lower value of {friendly_row}**")
            st.write(f"Strong correlation between {friendly_col} and {friendly_row} is {value:.2f} ")
            st.divider()
        else:
            if value >= 0:
                st.write(f"A higher value of {friendly_col} is associated with a higher value of {friendly_row}")
            else:
                st.write(f"A higher value of {friendly_col} is associated with a lower value of {friendly_row}")
            st.write(f"Correlation between {friendly_col} and {friendly_row} is {value:.2f} ")
            st.divider()
else:
    st.write("No strong correlations found with the current threshold.")


