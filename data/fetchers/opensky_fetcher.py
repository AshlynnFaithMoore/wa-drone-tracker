"""
data/fetchers/opensky_fetcher.py

Fetches live flight data from the OpenSky Network REST API.

OpenSky tracks aircraft via ADS-B transponders and makes the data
available publicly. We filter by Washington State's bounding box
and by low altitude to approximate drone activity.

API docs: https://opensky-network.org/apidoc/rest.html
"""

import requests
import logging
from datetime import datetime

from config import (
    OPENSKY_BASE_URL,
    OPENSKY_USERNAME,
    OPENSKY_PASSWORD,
    WA_BOUNDS,
    DRONE_MAX_ALTITUDE_METERS
)

# Set up a logger for this module. Messages will appear in the console
# with the module name as a prefix
logger = logging.getLogger(__name__)


def fetch_wa_flights():
    """
    Calls the OpenSky /states/all endpoint with Washington State bounds.

    Returns a list of dicts, one per low-altitude aircraft detected.
    Returns an empty list if the request fails or times out.

    OpenSky returns each aircraft as a "state vector" — a list of values
    in a fixed order. Map those positions to named fields below.
    """

    # Build the API URL with query parameters for the WA bounding box.
    
    url = f"{OPENSKY_BASE_URL}/states/all"
    params = {
        "lamin": WA_BOUNDS["lamin"],
        "lamax": WA_BOUNDS["lamax"],
        "lomin": WA_BOUNDS["lomin"],
        "lomax": WA_BOUNDS["lomax"]
    }

    # Use HTTP Basic Auth if credentials are configured, otherwise anonymous.
    auth = None
    if OPENSKY_USERNAME and OPENSKY_PASSWORD:
        auth = (OPENSKY_USERNAME, OPENSKY_PASSWORD)

    try:
        # timeout=10 means: give up if the server doesn't respond in 10 seconds.
        response = requests.get(url, params=params, auth=auth, timeout=10)

        # raise_for_status() throws an exception if the HTTP status code
        # indicates an error 
        response.raise_for_status()

        data = response.json()

        # The API returns {"time": ..., "states": [[...], [...], ...]}
        # Each inner list is a state vector for one aircraft.
        states = data.get("states") or []

        flights = []
        for state in states:
            # OpenSky state vector field positions (0-indexed):
            # 0:  icao24       — unique transponder ID
            # 1:  callsign     — flight identifier (often empty for smaller drones)
            # 5:  longitude
            # 6:  latitude
            # 7:  baro_altitude — barometric altitude in meters (can be None)
            # 8:  on_ground    — True if aircraft is on the ground
            # 9:  velocity     — ground speed in m/s
            # 10: true_track   — heading/direction in degrees

            baro_alt = state[7]  # Can be None if transponder isn't reporting altitude

            # Skip aircraft that are on the ground or above the drone altitude threshold.
            
            if state[8]:  # on_ground is True
                continue
            if baro_alt is None or baro_alt > DRONE_MAX_ALTITUDE_METERS:
                continue

            flights.append({
                "icao24":    state[0],
                "callsign":  (state[1] or "").strip(),
                "longitude": state[5],
                "latitude":  state[6],
                "altitude":  baro_alt,
                "on_ground": state[8],
                "velocity":  state[9],
                "heading":   state[10],
                "fetched_at": datetime.utcnow()
            })

        logger.info(f"Fetched {len(flights)} low-altitude flights in WA")
        return flights

    except requests.exceptions.Timeout:
        logger.warning("OpenSky API request timed out")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenSky API error: {e}")
        return []