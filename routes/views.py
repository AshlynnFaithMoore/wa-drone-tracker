"""
routes/views.py

Serves the HTML pages of the app.

These are the routes the browser navigates to directly (as opposed to
the /api/* routes in api.py, which return JSON consumed by JavaScript).

Flask's render_template() function:
    - Looks in the /templates folder for the named file
    - Processes any Jinja2 syntax ({{ }}, {% %}) in the file
    - Returns the final HTML string as the HTTP response

Blueprint registered in app.py with no url_prefix, so:
    @views_bp.route("/")         → http://localhost:5050/
    @views_bp.route("/map")      → http://localhost:5050/map
    @views_bp.route("/incidents")→ http://localhost:5050/incidents
"""

from flask import Blueprint, render_template
from models.models import DroneRegistration
from data.processors.stats_processor import get_overview_stats

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index():
    """
    Main dashboard page.

    We pass overview_stats into the template so the KPI cards can render
    their initial values server-side. This means the numbers are visible
    immediately on page load, before dashboard.js fires its own fetch().
    JavaScript will then keep refreshing them every 60 seconds.

    """
    stats = get_overview_stats()
    return render_template("index.html", stats=stats)


@views_bp.route("/map")
def map_view():
    """
    Flight map page.
    The map itself is built entirely by Leaflet in map.js
    """
    return render_template("map.html")


@views_bp.route("/incidents")
def incidents():
    """
    Incident reports table page.
    Like the map, the table is fully JS-driven — incidents.js fetches
    /api/incidents on load.
    """
    return render_template("incidents.html")


@views_bp.route("/registrations")
def registrations():
    """
    Registration breakdown page
    Passes summary counts to the template for server-side rendering.
    """
    total = DroneRegistration.query.filter_by(owner_state="WA").count()
    return render_template("registrations.html", total=total)


# Error handlers

# These catch HTTP errors and render a friendly page instead of Flask's
# default plain-text error response.


@views_bp.app_errorhandler(404)
def not_found(e):
    """
    Shown when the user navigates to a URL that doesn't exist.
    render_template returns the HTML; the second value (404) sets the
    HTTP status code.
    """
    return render_template("errors/404.html"), 404


@views_bp.app_errorhandler(500)
def server_error(e):
    """
    Shown when an unhandled exception occurs in a route handler.
    Useful during development to show a styled error page instead of
    a raw Python traceback being sent to the browser.
    """
    return render_template("errors/500.html"), 500
