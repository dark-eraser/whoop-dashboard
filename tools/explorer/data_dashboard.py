"""Streamlit App to Explore Whoop Data

Copyright (c) 2022 Felix Geilert
"""

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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(page_title="Whoop", page_icon="🏃‍♂️", layout="wide")

# define some paths
BASE_DIR = Path(os.path.dirname(__file__))
CONFIG_FILE = "../../config.json"
TOKEN_FILE = BASE_DIR / ".tokens" / "whoop_token.json"

# check if files exist
if not os.path.exists(CONFIG_FILE):
    st.error("No config.json found")
    st.stop()

# retrieve modification dates (for caching)
config_mod_date = os.path.getmtime(CONFIG_FILE)


# read the config (make sure this is cached based on last modification date)
@st.cache_data()
def load_config(config_mod_date):
    # load config and return
    config = json.load(open(CONFIG_FILE, "r"))
    return config


# retrieve the config
config = load_config(config_mod_date)


# Sidebar
st.sidebar.header("Whoop API")
with open(BASE_DIR / "readme.md", "r") as f:
    st.sidebar.markdown(f.read())

# Main
st.title("Whoop API Explorer")

# generate the client
client: WhoopClient = None

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
# generate the url
@st.cache_data()
def login_url(config: Dict) -> Tuple[str, str]:
    """Generates the grant url for the whoop api."""
    # retrieve url
    url, state = WhoopClient.auth_url(
        config["client_id"], config["client_secret"], config["redirect_uri"]
    )
    webbrowser.open(url)

    return url, state


# run through login UI
login_container = st.empty()
with login_container.container():

    def login_verify(code: str) -> WhoopClient:
        """Runs through the login flow and returns the client."""
        # generate client
        client = None
        if code:
            try:
                with st.spinner(text="authorizing..."):
                    client = WhoopClient.authorize(
                        code,
                        config["client_id"],
                        config["client_secret"],
                        config["redirect_uri"],
                    )
            except Exception:
                st.error("Code could not be used to generate token")
                client = None
        return client

    # verify that config contains data
    if "client_id" not in config or "client_secret" not in config:
        st.error("No `client_id` or `client_secret` found in config.json")
        st.stop()
    if "redirect_uri" not in config:
        st.error("No `redirect_uri` found in config.json")
        st.stop()

    # verify if config file should be loaded
    if not os.path.exists(TOKEN_FILE):
        # wait for code
        url, state = login_url(config)
        if st.button("Reopen Login"):
            webbrowser.open(url)

        # wait for user to enter the code
        code = st.text_input("Enter Auth Code from Grant url:")
        client = login_verify(code)
    else:
        # try to load from file, otherwise update
        try:
            with st.spinner(text="loading token..."):
                client = WhoopClient.from_token(
                    TOKEN_FILE, config["client_id"], config["client_secret"]
                )
        except Exception as e:
            # provide warning to log
            logging.warning(f"Failed to load token: {e}")
            logging.warning("Delete token and retry")

            # delete token and re-execute login
            os.remove(TOKEN_FILE)

            # wait for code
            url, state = login_url(config)
            if st.button("Reopen Login"):
                webbrowser.open(url)

            # wait for user to enter the code
            code = st.text_input("Enter Auth Code from Grant url:")
            client = login_verify(code)

    # if client setup, store a new token
    if client:
        client.store_token(TOKEN_FILE)

    if not client:
        st.warning("Waiting for client")
        st.stop()

# retrieve client data
user = client.user.profile()
st.success(f"Logged in as {user.first_name} {user.last_name} ({user.user_id})")
login_container.empty()

# load the latest metrics
baseline_days = st.slider("Days to load", 1, 180, 30, 1)
# baseline_days = int(baseline_days)
# get datetime rounded to 10 min
now = datetime.now()

# Calculate minutes rounded to the nearest 10
rounded_minutes = math.floor(now.minute / 10) * 10

# Replace seconds and microseconds, and set minutes to the rounded value
today = now.replace(second=0, microsecond=0, minute=rounded_minutes)

this_week_start = np.datetime64(datetime.now().date() - timedelta(days=6))
this_week_end = np.datetime64(datetime.now().date())

# display tabs
tab_trends, tab_plots = st.tabs(
    [ "Trends", "Plots"]
)


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
    print(today)
    # today = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    # today = "2024-06-14T00:00:00.000"
    rec, _ = client.recovery.collection_df(start=start, end=today, get_all_pages=True)
    sleep, _ = client.sleep.collection_df(start=start, end=today, get_all_pages=True)  
    # cycle, _ = client.cycle.collection_df(start=start, end=today, get_all_pages=True)
    workout, _ = client.workout.collection_df(
        start=start, end=today, get_all_pages=True
    )
    return rec, sleep, workout

with st.spinner(text="loading metrics..."):
    rec, sleep, workout = load_metrics(baseline_days, today)
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

with tab_trends:
    PERIOD_START = pd.to_datetime(st.date_input("Select Period Start Date", value=today - timedelta(baseline_days), key="0"))
    PERIOD_END = pd.to_datetime(st.date_input("Select Period End Date", value=today, key="1fef"))
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
    

    st.header("Current Metrics")
    st.subheader("Sleep")
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
        recovery_col3.metric(label="RHR (bpm)", value=f"{rhr_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(rhr_period_avg, rhr_this_week_avg)):.5f} %")
        recovery_col4.metric(label="SPO2 (%)", value=f"{spo2_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(spo2_period_avg, spo2_this_week_avg)):.5f} %")
        recovery_col5.metric(label="Skin Temp (C)", value=f"{skin_temp_this_week_avg:.5f}", delta=f"{(helper_delta_percentage(skin_temp_period_avg, skin_temp_this_week_avg)):.5f} %")
        
    #TODO: not implemented yet since we ahve datetime problems when using the "cycles" enpoint which is needed for strain data    
    with st.container():
        # st.subheader("Strain")
        strain_col1, strain_col2, strain_col3, strain_col4, strain_col5 = st.columns(5)
        
        
    style_metric_cards()

with tab_plots:
    # display plots
    st.header("Plots")
    with chart_container(rec):

        # display recovery score
        st.subheader("Recovery Score")
        fig = px.line(rec, x="updated_at", y="score.recovery_score")
        st.plotly_chart(fig)
    
    # display sleep efficiency
    st.subheader("Sleep Efficiency")
    fig = px.line(sleep_nonap, x="end", y="score.sleep_efficiency_percentage")
    st.plotly_chart(fig)

    # display workout strain
    st.subheader("Workout Strain")
    fig = px.line(workout, x="start", y="score.strain")
    st.plotly_chart(fig)

    # display workout calories
    st.subheader("Workout Calories")
    fig = px.line(workout, x="start", y="score.kilojoule")
    st.plotly_chart(fig)

    # display workout HR
    st.subheader("Workout HR")
    fig = px.line(workout, x="start", y="score.average_heart_rate")
    st.plotly_chart(fig)

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
