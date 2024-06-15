import json
import logging
import os
from pathlib import Path
import streamlit as st
from datetime import datetime
from whoopy import WhoopClient
from Client import WhoopClientSingleton  # Import the WhoopClientSingleton class
from typing import Tuple, Dict
import webbrowser
from urllib.parse import urlparse, parse_qs

def extract_code_from_url(url: str) -> str:
    """Extracts the authorization code from the callback URL."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params.get('code', [None])[0]

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(page_title="Whoop", page_icon="🏃‍♂️", layout="wide")

# Define some paths
BASE_DIR = Path(os.path.dirname(__file__))
CONFIG_FILE = "../../config.json"  # Update the path to your config file
TOKEN_FILE = BASE_DIR / ".tokens" / "whoop_token.json"

# Check if config file exists
if not os.path.exists(CONFIG_FILE):
    st.error("No config.json found")
    st.stop()

# Load the config
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# Initialize the WhoopClientSingleton
whoop_client_singleton = WhoopClientSingleton(config)
client = whoop_client_singleton.get_client()
user = client.user.profile()
st.success(f"Logged in as {user.first_name} {user.last_name} ({user.user_id})")