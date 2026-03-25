"""
routes/api.py

REST API endpoints that return JSON data to the frontend JavaScript.

These are the "backend" functions that the Chart.js and Leaflet.js code
in the browser calls via fetch() to get data to display.

All routes here are registered under the /api prefix (set in app.py),
so a route defined as @api_bp.route("/stats") is accessible at /api/stats.

"""

from flask import Blueprint, jsonify

from data.processors.stats_processor import (
    get_altitude_distribution,
    get_flights_by_county,
    get_overview_stats,
    get_recent_flights,
    get_registrations_by_purpose,
)
from models.models import DroneRegistration, IncidentReport

# Create the blueprint object.
api_bp = Blueprint("api", __name__)


@api_bp.route("/debug/clear-registrations")
def debug_clear_registrations():
    from models.models import DroneRegistration

    count = DroneRegistration.query.count()
    DroneRegistration.query.delete()
    from models.models import db

    db.session.commit()
    return jsonify({"deleted": count})


@api_bp.route("/stats")
def stats():
    """
    GET /api/stats
    Returns high-level KPI numbers.
    Example response:
        {
          "total_flights": 1240,
          "active_flights": 8,
          "total_registrations": 4502,
          "total_incidents": 17
        }
    """
    return jsonify(get_overview_stats())


@api_bp.route("/flights/by-county")
def flights_by_county():
    """
    GET /api/flights/by-county
    Returns flight counts grouped by WA county — used for the bar chart.
    Example response:
        [
          {"county": "King", "count": 312},
          {"county": "Pierce", "count": 198},
          ...
        ]
    """
    return jsonify(get_flights_by_county())


@api_bp.route("/flights/recent")
def recent_flights():
    """
    GET /api/flights/recent
    Returns the most recent 200 flight records with lat/lon — used
    to place markers on the Leaflet map.
    """
    return jsonify(get_recent_flights())


@api_bp.route("/registrations/by-purpose")
def registrations_by_purpose():
    """
    GET /api/registrations/by-purpose
    Returns commercial vs recreational counts — used for the pie chart.
    Example response:
        [
          {"purpose": "Commercial", "count": 1820},
          {"purpose": "Recreational", "count": 2682}
        ]
    """
    return jsonify(get_registrations_by_purpose())


@api_bp.route("/flights/altitude-distribution")
def altitude_distribution():
    """
    GET /api/flights/altitude-distribution
    Returns bucketed altitude counts — used for the histogram bar chart.
    Example response:
        [
          {"range": "0–25m", "count": 45},
          {"range": "25–50m", "count": 112},
          ...
        ]
    """
    return jsonify(get_altitude_distribution())


@api_bp.route("/incidents")
def incidents():
    rows = IncidentReport.query.order_by(IncidentReport.incident_date.desc()).all()
    return jsonify([r.to_dict() for r in rows])


@api_bp.route("/registrations")
def registrations():
    rows = (
        DroneRegistration.query.filter_by(owner_state="WA")
        .order_by(DroneRegistration.registered_date.desc())
        .all()
    )
    return jsonify([r.to_dict() for r in rows])
