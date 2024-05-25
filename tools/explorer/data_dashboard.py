"""Streamlit App to Explore Whoop Data

Copyright (c) 2022 Felix Geilert
"""

from datetime import datetime, timedelta
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
# Page wide Config
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
baseline_days_test = st.slider("Days to load test", 1, 180, 30, 1, key="test")
# baseline_days = int(baseline_days)
# get datetime rounded to 10 min
now = datetime.now()

# Calculate minutes rounded to the nearest 10
rounded_minutes = math.floor(now.minute / 10) * 10

# Replace seconds and microseconds, and set minutes to the rounded value
today = now.replace(second=0, microsecond=0, minute=rounded_minutes)

# display tabs
tab_trends, tab_plots = st.tabs(
    [ "Trends", "Plots"]
)


@st.cache_data()
def load_metrics(baseline_days: int, today) -> Dict:
    start = today - timedelta(days=baseline_days + 1)
    today = "2024-05-22"
    # start = "2024-04-01"
    rec, _ = client.recovery.collection_df(start=start, end=today, get_all_pages=True)
    sleep, _ = client.sleep.collection_df(start=start, end=today, get_all_pages=True)
    cycle, _ = client.cycle.collection_df(start=start, end=today, get_all_pages=True)
    workout, _ = client.workout.collection_df(
        start=start, end=today, get_all_pages=True
    )

    return rec, sleep, cycle, workout


with st.spinner(text="loading metrics..."):
    rec, sleep, cycle, workout = load_metrics(baseline_days, today)
    sleep_nonap = sleep[sleep["nap"] == False]

def compute_average_sleep_efficiency(start, end, sleep):
    """Computes the average sleep for a given time period."""
    # filter data
    sleep_copy = sleep[(pd.to_datetime(sleep["end"]) >= start) & (pd.to_datetime(sleep["end"]) <= end)]
    # sleep, _ = client.sleep.collection_df(start=start, end=end, get_all_pages=True)
    # compute average
    avg_sleep_efficiency = sleep_copy["score.sleep_efficiency_percentage"].mean()
    return avg_sleep_efficiency
def get_workouts_per_week(workouts):
    print(workouts["start"].head())  # Inspect the start dates
  

    # Ensure that the 'start' column is in datetime format
    today = pd.to_datetime(datetime.now().date())

    # Ensure the 'start' column is in datetime format
    workouts["start"] = pd.to_datetime(workouts["start"])

    # Define the date range
    start_date = today - timedelta(days=7)
    end_date = today
    print(start_date, end_date)  # Inspect the date range
    # Filter the data
    workouts_this_week = workouts[(workouts["start"] >= start_date) & (workouts["start"] <= end_date)]


    return workouts_this_week
def get_period_average(sleep, period_start, period_end):
    """Computes the average sleep efficiency for this week and an arbitrary period of time."""
    this_week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
    # compute average for this week
    this_week_avg = compute_average_sleep_efficiency(this_week_start, period_end, sleep)

    # compute average for the arbitrary period
    period_avg = compute_average_sleep_efficiency(period_start, period_end, sleep)

    return this_week_avg, period_avg

with tab_trends:
    # display metrics
    print(get_workouts_per_week(workout))
    count = get_workouts_per_week(workout).shape[0]
    print(count)
    sleep_this_week_avg, sleep_period_avg = get_period_average(sleep, today - timedelta(days=baseline_days_test), today)
    # recovery_this_week_avg, recovery_period_avg = get_period_average(rec, today - timedelta(days=baseline_days), today)
    # workout_this_week_avg, workout_period_avg = get_period_average(workout, today - timedelta(days=baseline_days), today)
    

    st.header("Current Metrics")
    st.text(f"Compared to {baseline_days} day baseline")
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(label="Sleep", value=f"{sleep_this_week_avg:.5f}", delta=f"{(abs(sleep_this_week_avg / sleep_period_avg)):.5f} %")
    # col2.metric(label="Recovery", value=f"{recovery_this_week_avg:.5f}", delta=f"{(abs(recovery_this_week_avg / recovery_period_avg)):.5f} %")
    # col3.metric(label="Workout", value=f"{workout_this_week_avg:.5f}", delta=f"{(abs(workout_this_week_avg / workout_period_avg)):.5f} %")
    col4.metric(label="No Change", value=5000, delta=0)
    col5.metric(label="No Change", value=5000, delta=0)

    style_metric_cards()
    # display comparison
    st.header("Comparison")
    # st.text(f"This Week: {this_week_avg:.5f}")
    # st.text(f"Period: {period_avg:.5f}")
    # st.text(f"Difference: {(abs(this_week_avg / period_avg))} %")
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
