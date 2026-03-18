"""
config.py

Central configuration file. All settings live here so you never
have to hunt through multiple files to change something.

python-dotenv lets us load sensitive values (like API keys) from a
.env file instead of hardcoding them.
"""

import os

from dotenv import load_dotenv

# Load values from a .env file in the project root (if it exists).
# If a key is already set in the environment, load_dotenv won't override it.
load_dotenv()

# Flask settings

FLASK_HOST = "127.0.0.1"  # Only accessible from this machine (localhost)
FLASK_PORT = 5050  # The port the Flask server listens on
FLASK_DEBUG = False  # Never True in production; disables auto-reloader

# Database

# SQLite stores everything in a single file

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(BASE_DIR, "drone_data.db")
)
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

# Washington State geographic bounding box

# These lat/lon bounds are passed to the OpenSky API so we only
# receive flights within Washington State, not the entire USA.
WA_BOUNDS = {
    "lamin": 45.5,  # Southern border latitude
    "lamax": 49.0,  # Northern border latitude (Canadian border)
    "lomin": -124.8,  # Western border longitude (Pacific coast)
    "lomax": -116.9,  # Eastern border longitude (Idaho border)
}

# OpenSky Network API


OPENSKY_BASE_URL = "https://opensky-network.org/api"
OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME", "")  # Optional
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD", "")  # Optional

# Drones typically fly below 400 feet (122 meters) — FAA rule for recreational drones.
# Will filter out commercial aircraft from the OpenSky data.
DRONE_MAX_ALTITUDE_METERS = 122

# Data refresh schedule
REFRESH_INTERVAL_SECONDS = 60

# FAA data
# Path to manually downloaded FAA registration CSV files.

FAA_DATA_DIR = os.path.join(BASE_DIR, "data", "faa_csv")
