"""
data/processors/stats_processor.py

Takes raw flight/registration data and computes aggregate statistics
that the frontend charts and tables will display.

Also handles saving new flight records to the database and
optionally resolves which WA county a lat/lon point falls in.
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func

from models.models import db, FlightRecord, DroneRegistration, IncidentReport

logger = logging.getLogger(__name__)


# County resolution


def resolve_county(lat, lon):
    """
    Given a latitude and longitude, returns the Washington State county name.

    Using geopandas to load a WA counties shapefile and do a spatial join.
    If geopandas isn't available or the point is outside WA, returns "Unknown".

    The shapefile can be downloaded from:
    https://geo.wa.gov/datasets/wadnr::washington-state-county-boundaries

    """
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        import os

        shp_path = os.path.join("data", "shapefiles", "wa_counties.shp")
        if not os.path.exists(shp_path):
            return "Unknown"

        # Load the shapefile
        counties = gpd.read_file(shp_path)

        # Create a Point geometry and make sure it uses the same CRS (coordinate
        # reference system) as the shapefile (typically EPSG:4326 = standard lat/lon)
        point = gpd.GeoDataFrame([{"geometry": Point(lon, lat)}], crs="EPSG:4326")
        if counties.crs != point.crs:
            counties = counties.to_crs("EPSG:4326")

        # Spatial join: find which county polygon contains our point
        result = gpd.sjoin(point, counties, how="left", predicate="within")
        if not result.empty and "COUNTY_NM" in result.columns:
            return result.iloc[0]["COUNTY_NM"]
        return "Unknown"

    except Exception as e:
        logger.debug(f"County resolution failed: {e}")
        return "Unknown"


# Saving new flight data


def save_flights(flights):
    """
    Takes a list of flight dicts (from opensky_fetcher) and saves them
    to the FlightRecord table. Resolves county for each flight.

    Called by the background scheduler every REFRESH_INTERVAL_SECONDS.
    """
    saved = 0
    for f in flights:
        county = resolve_county(f["latitude"], f["longitude"])
        record = FlightRecord(
            icao24=f.get("icao24"),
            callsign=f.get("callsign"),
            latitude=f.get("latitude"),
            longitude=f.get("longitude"),
            altitude=f.get("altitude"),
            velocity=f.get("velocity"),
            heading=f.get("heading"),
            on_ground=f.get("on_ground", False),
            county=county,
            recorded_at=f.get("fetched_at", datetime.utcnow()),
        )
        db.session.add(record)
        saved += 1

    db.session.commit()
    logger.info(f"Saved {saved} flight records to database")


# Statistics queries


def get_overview_stats():
    """
    Returns high-level KPI numbers for the dashboard overview cards:
    - Total flight records in the DB
    - Active flights in the last hour
    - Total drone registrations
    - Total incidents
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    total_flights = FlightRecord.query.count()
    active_flights = FlightRecord.query.filter(FlightRecord.recorded_at >= one_hour_ago).count()
    total_registrations = DroneRegistration.query.filter_by(owner_state="WA").count()
    total_incidents = IncidentReport.query.count()

    return {
        "total_flights": total_flights,
        "active_flights": active_flights,
        "total_registrations": total_registrations,
        "total_incidents": total_incidents,
    }


def get_flights_by_county():
    """
    Returns a list of {county, count} dicts sorted by count descending.
    Used to populate the bar chart on the dashboard.

    """
    results = (
        db.session.query(FlightRecord.county, func.count(FlightRecord.id).label("count"))
        .group_by(FlightRecord.county)
        .order_by(func.count(FlightRecord.id).desc())
        .all()
    )
    return [{"county": r.county, "count": r.count} for r in results]


def get_recent_flights(limit=200):
    """
    Returns the most recent N flight records as a list of dicts.
    Used to populate the Leaflet map markers.
    Limit to 200 to keep the map from getting too cluttered.
    """
    records = FlightRecord.query.order_by(FlightRecord.recorded_at.desc()).limit(limit).all()
    return [r.to_dict() for r in records]


def get_registrations_by_purpose():
    """
    Returns counts of Commercial vs Recreational drone registrations in WA.
    Used for the pie chart visualization.
    """
    results = (
        db.session.query(DroneRegistration.purpose, func.count(DroneRegistration.id).label("count"))
        .filter_by(owner_state="WA")
        .group_by(DroneRegistration.purpose)
        .all()
    )
    return [{"purpose": r.purpose, "count": r.count} for r in results]


def get_altitude_distribution():
    """
    Buckets flight records by altitude range (0-25m, 25-50m, etc.)
    for a histogram chart showing typical drone flight altitudes.
    """
    # Load altitudes into a pandas DataFrame for easy binning
    records = (
        db.session.query(FlightRecord.altitude).filter(FlightRecord.altitude.isnot(None)).all()
    )

    if not records:
        return []

    df = pd.DataFrame(records, columns=["altitude"])

    # pd.cut divides values into bins. right=False means each bin is [low, high)
    bins = [0, 25, 50, 75, 100, 122]
    labels = ["0–25m", "25–50m", "50–75m", "75–100m", "100–122m"]
    df["bucket"] = pd.cut(df["altitude"], bins=bins, labels=labels, right=False)

    counts = df["bucket"].value_counts().sort_index()
    return [{"range": str(k), "count": int(v)} for k, v in counts.items()]
