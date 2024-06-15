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