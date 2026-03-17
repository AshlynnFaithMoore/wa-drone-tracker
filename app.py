"""
app.py

The Flask application factory and entry point.

Flask is a lightweight Python listens for HTTP requests
(from the browser or Tkinter) and responds with either HTML pages or JSON data.

"""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from config import (
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    REFRESH_INTERVAL_SECONDS,
    SQLALCHEMY_DATABASE_URI,
)
from models.models import db

# Configure logging so all modules write to the same console format
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


def create_app():
    """
    Builds and returns the configured Flask application.

    Steps:
    1. Create the Flask app object
    2. Configure the database URI
    3. Initialize SQLAlchemy with the app
    4. Create database tables if they don't exist
    5. Register route blueprints
    6. Start the background data scheduler
    """

    # Flask(__name__) tells Flask to look for templates/static files
    # relative to this file's location.
    app = Flask(__name__)

    # Tell SQLAlchemy where the database is
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI

    # Disable SQLAlchemy's modification tracking
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Connect SQLAlchemy to this Flask app instance
    db.init_app(app)

    # Create all tables defined in models.py if they don't already exist.
    with app.app_context():
        db.create_all()

    # Register Blueprints
    # Blueprints let us split routes across multiple files instead of
    # putting everything in app.py. Import them here and register them.

    from routes.api import api_bp
    from routes.views import views_bp

    app.register_blueprint(views_bp)  # HTML pages (/, /map, /incidents)
    app.register_blueprint(api_bp, url_prefix="/api")  # JSON endpoints (/api/stats, etc.)

    # Background Scheduler
    # APScheduler runs functions on a schedule in a background thread.
    # Use it to automatically fetch new OpenSky data every N seconds
    # without blocking the Flask server.

    scheduler = BackgroundScheduler()

    def scheduled_fetch():
        """
        This function runs every REFRESH_INTERVAL_SECONDS.
        It must push an app context because SQLAlchemy needs one to
        access the database outside of a normal request.
        """
        from data.fetchers.opensky_fetcher import fetch_wa_flights
        from data.processors.stats_processor import save_flights

        with app.app_context():
            flights = fetch_wa_flights()
            if flights:
                save_flights(flights)

    # 'interval' trigger: run every N seconds
    scheduler.add_job(
        scheduled_fetch,
        trigger="interval",
        seconds=REFRESH_INTERVAL_SECONDS,
        id="opensky_fetch",
        replace_existing=True,
    )

    if not os.environ.get("TESTING"):
        scheduler.start()
        scheduler.start()

    return app


# Run directly (python app.py)
# This block only runs if you start Flask standalone for testing.

if __name__ == "__main__":
    app = create_app()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
