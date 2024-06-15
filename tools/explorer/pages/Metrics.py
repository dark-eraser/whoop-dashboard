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
from Helper import helper_milliseconds_to_hours, helper_delta_percentage

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

now = datetime.now()
rounded_minutes = math.floor(now.minute / 10) * 10
today = now.replace(second=0, microsecond=0, minute=rounded_minutes)

this_week_start = np.datetime64(datetime.now().date() - timedelta(days=6))
this_week_end = np.datetime64(datetime.now().date())

st.sidebar.header("Whoop API")
baseline_days= st.sidebar.slider("Days to load", 1, 180, 60, 1)
PERIOD_START,PERIOD_END = pd.to_datetime(st.sidebar.date_input("Select Period to Compare Current Week with", (today - timedelta(baseline_days), today), today - timedelta(baseline_days),today,format="MM.DD.YYYY"))


class CurrentPeriodData:
    sleep_efficiency: float
    recovery_score: float
    time_in_bed: float
    sleep_consistency: float
    period_start: datetime
    period_end: datetime
    

current_period_data = CurrentPeriodData()
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

with st.spinner(text="loading metrics..."):
    rec, sleep, workout = load_metrics(baseline_days, today)
    logging.debug(f"Workout Keys: {workout.keys()}")
    sleep_nonap = sleep[sleep["nap"] == False]

def get_workouts_per_week(workouts):
    today = pd.to_datetime(datetime.now().date())
    workouts["start"] = pd.to_datetime(workouts["start"])
    start_date = today - timedelta(days=7)
    end_date = today
    workouts_this_week = workouts[(workouts["start"] >= start_date) & (workouts["start"] <= end_date)]
    return workouts_this_week

def compute_average_sleep_efficiency(start, end):
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    avg_sleep_efficiency = sleep_copy["score.sleep_efficiency_percentage"].mean()
    return avg_sleep_efficiency

def compute_average_time_in_bed(start, end):
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    avg_time_in_bed = sleep_copy["score.stage_summary.total_in_bed_time_milli"].mean()
    return helper_milliseconds_to_hours(avg_time_in_bed)

def compute_average_sleep_consistency(start, end):
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    avg_sleep_consistency = sleep_copy["score.sleep_consistency_percentage"].mean()
    return avg_sleep_consistency

def compute_average_sleep_performance(start, end):
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    avg_sleep_performance = sleep_copy["score.sleep_performance_percentage"].mean()
    return avg_sleep_performance

def compute_average_respiratory_rate(start, end):
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    avg_respiratory_rate = sleep_copy["score.respiratory_rate"].mean()
    return avg_respiratory_rate

def compute_average_recovery_score(start, end):
    rec_copy = rec[(pd.to_datetime(rec["created_at"]) >= start) & (pd.to_datetime(rec["created_at"]) <= end)]
    avg_rec_score = rec_copy["score.recovery_score"].mean()
    return avg_rec_score

def compute_average_hrv_rmssd_milli(start, end):
    rec_copy = rec[(pd.to_datetime(rec["created_at"]) >= start) & (pd.to_datetime(rec["created_at"]) <= end)]
    avg_hrv_rmssd_milli = rec_copy["score.hrv_rmssd_milli"].mean()
    return avg_hrv_rmssd_milli

def compute_average_rhr(start, end):
    rec_copy = rec[(pd.to_datetime(rec["created_at"]) >= start) & (pd.to_datetime(rec["created_at"]) <= end)]
    avg_rhr = rec_copy["score.resting_heart_rate"].mean()
    return avg_rhr

def compute_average_spo2(start, end):
    rec_copy = rec[(pd.to_datetime(rec["created_at"]) >= start) & (pd.to_datetime(rec["created_at"]) <= end)]
    avg_spo2 = rec_copy["score.spo2_percentage"].mean()
    return avg_spo2

def compute_average_skin_temp(start, end):
    rec_copy = rec[(pd.to_datetime(rec["created_at"]) >= start) & (pd.to_datetime(rec["created_at"]) <= end)]
    avg_skin_temp = rec_copy["score.skin_temp_celsius"].mean()
    return avg_skin_temp


METRIC_FUNCTIONS = {
    "sleep_efficiency": compute_average_sleep_efficiency,
    "recovery_score": compute_average_recovery_score,
    "time_in_bed": compute_average_time_in_bed,
    "sleep_consistency": compute_average_sleep_consistency,
    "sleep_performance": compute_average_sleep_performance,
    "respiratory_rate": compute_average_respiratory_rate, # "respiratory_rate": "score.respiratory_rate",
    "hrv_rmssd_milli": compute_average_hrv_rmssd_milli,
    "rhr": compute_average_rhr,
    "spo2": compute_average_spo2,
    "skin_temp": compute_average_skin_temp,
}


def get_period_average(metric):
    logging.debug(f"Metric: {metric}")
    logging.debug(f"This week start: {this_week_start}")
    logging.debug(f"Period end: {PERIOD_END}")
    logging.debug(f"Period start: {PERIOD_START}")
    compute_average_function = METRIC_FUNCTIONS.get(metric)
    if compute_average_function is None:
        raise ValueError(f"Unknown metric: {metric}")
    this_week_avg = compute_average_function(this_week_start, this_week_end)
    period_avg = compute_average_function(PERIOD_START, PERIOD_END)
    logging.debug(f"This week avg {metric}: {this_week_avg}")
    logging.debug(f"Period avg {metric}: {period_avg}")
    return this_week_avg, period_avg


def get_sleep_duration(sleep, start,end):
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    avg_sleep_duration = sleep_copy["score.total_sleep_duration"].mean()
    return avg_sleep_duration


# with tab_trends:
st.header("Current Metrics")
st.subheader("Sleep")
current_period_data.period_start = PERIOD_START
current_period_data.period_end = PERIOD_END

# sleep metric computation
sleep_this_week_avg, sleep_period_avg = get_period_average("sleep_efficiency")
total_time_in_bed_this_week_avg, total_time_in_bed_period_avg = get_period_average("time_in_bed")
sleep_consistency_this_week_avg, sleep_consistency_period_avg = get_period_average("sleep_consistency")
sleep_performance_this_week_avg, sleep_performance_period_avg = get_period_average("sleep_performance")
respiratory_rate_this_week_avg, respiratory_rate_period_avg = get_period_average("respiratory_rate")

# recovery metric computation
recovery_this_week_avg, recovery_period_avg = get_period_average("recovery_score")
hrv_this_week_avg, hrv_period_avg = get_period_average("hrv_rmssd_milli")
rhr_this_week_avg, rhr_period_avg = get_period_average("rhr")
spo2_this_week_avg, spo2_period_avg = get_period_average("spo2")
skin_temp_this_week_avg, skin_temp_period_avg = get_period_average("skin_temp")



with st.container():
    sleep_col1, sleep_col2, sleep_col3, sleep_col4, sleep_col5 = st.columns(5)
    sleep_col1.metric(label="Sleep Efficiency (%)", value=f"{sleep_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(sleep_period_avg, sleep_this_week_avg)):.5f} %")
    sleep_col2.metric(label="Time in Bed (hours)", value=f"{total_time_in_bed_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(total_time_in_bed_this_week_avg, total_time_in_bed_period_avg)):.5f} %")
    sleep_col3.metric(label="Sleep Consistency (%)", value=f"{sleep_consistency_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(sleep_consistency_period_avg, sleep_consistency_this_week_avg)):.5f} %")
    sleep_col4.metric(label="Sleep Performance (%)", value=f"{sleep_performance_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(sleep_performance_period_avg, sleep_performance_this_week_avg)):.5f} %")
    sleep_col5.metric(label="Respiratory Rate", value=f"{respiratory_rate_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(respiratory_rate_period_avg, respiratory_rate_this_week_avg)):.5f} %")
    
with st.container():
    st.subheader("Recovery")

    recovery_col1, recovery_col2, recovery_col3, recovery_col4, recovery_col5 = st.columns(5)

    recovery_col1.metric(label="Recovery Score (%)", value=f"{recovery_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(recovery_period_avg,recovery_this_week_avg)):.5f} %")
    recovery_col2.metric(label="HRV (ms)", value=f"{hrv_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(hrv_period_avg, hrv_this_week_avg)):.5f} %")
    recovery_col3.metric(label="RHR (bpm)", value=f"{rhr_this_week_avg:.0f}", delta=f"{(helper_delta_percentage(rhr_period_avg, rhr_this_week_avg)):.5f} %", delta_color="inverse")
    recovery_col4.metric(label="SPO2 (%)", value=f"{spo2_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(spo2_period_avg, spo2_this_week_avg)):.5f} %")
    recovery_col5.metric(label="Skin Temp (C)", value=f"{skin_temp_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(skin_temp_period_avg, skin_temp_this_week_avg)):.5f} %", delta_color="inverse")
    
#TODO: not implemented yet since we ahve datetime problems when using the "cycles" enpoint which is needed for strain data    
with st.container():
    # st.subheader("Strain")
    strain_col1, strain_col2, strain_col3, strain_col4, strain_col5 = st.columns(5)
    
    
style_metric_cards(border_radius_px=15, border_color="#9AD8E1")

