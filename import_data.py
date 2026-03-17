"""
import_data.py

Command-line script to seed the database with FAA data.

Run before launching the app for the first time, and again
whenever the FAA publishes updated CSV files.

Usage:
    python import_data.py                  # Import both registrations and incidents
    python import_data.py --regs-only      # Only import registrations
    python import_data.py --incidents-only # Only import incidents
    python import_data.py --regs-path /path/to/MASTER.txt
    python import_data.py --incidents-path /path/to/incidents.csv
    python import_data.py --wipe           #  Clear existing data before importing


    SQLAlchemy needs a Flask application context to know which database
    to connect to.
"""

import argparse
import logging
import os
import sys

# Configure logging to show clean output in the terminal
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger("import_data")


# Argument parsing

# argparse is Python's built-in CLI argument library.

parser = argparse.ArgumentParser(
    description="Import FAA drone data into the WA Drone Tracker database."
)
parser.add_argument(
    "--regs-only", action="store_true", help="Only import registration data (skip incidents)"
)
parser.add_argument(
    "--incidents-only", action="store_true", help="Only import incident data (skip registrations)"
)
parser.add_argument(
    "--regs-path", type=str, default=None, help="Custom path to FAA MASTER.txt registration CSV"
)
parser.add_argument(
    "--incidents-path", type=str, default=None, help="Custom path to incidents CSV file"
)
parser.add_argument(
    "--wipe",
    action="store_true",
    help="⚠ Delete ALL existing registration and incident records before importing",
)
parser.add_argument(
    "--check", action="store_true", help="Just print current database counts and exit (no import)"
)

args = parser.parse_args()


# Bootstrap Flask app context

# import create_app here (not at the top) because importing app.py
# starts the APScheduler — don't want that in a CLI script.
# We only need the Flask app for its database config.

from app import create_app
from models.models import DroneRegistration, IncidentReport, db

app = create_app()


# --check: just show current counts and exit


if args.check:
    with app.app_context():
        reg_count = DroneRegistration.query.filter_by(owner_state="WA").count()
        inc_count = IncidentReport.query.count()
        flight_count = db.session.execute(db.text("SELECT COUNT(*) FROM flight_records")).scalar()
        print("\n── Database Status ─────────────────────────")
        print(f"  WA Registrations : {reg_count:,}")
        print(f"  Incidents        : {inc_count:,}")
        print(f"  Flight Records   : {flight_count:,}")
        print("────────────────────────────────────────────\n")
    sys.exit(0)


# Main import


with app.app_context():

    #  Optional wipe
    if args.wipe:
        confirm = input(
            "⚠  This will DELETE all registration and incident records. " "Type 'yes' to confirm: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

        logger.warning("Wiping existing registration and incident records…")
        DroneRegistration.query.delete()
        IncidentReport.query.delete()
        db.session.commit()
        logger.info("Wipe complete.")

    # Registrations
    if not args.incidents_only:
        logger.info("── Importing FAA registrations ──────────────")

        # Check that the source file exists before starting
        from config import FAA_DATA_DIR

        regs_path = args.regs_path or os.path.join(FAA_DATA_DIR, "MASTER.txt")

        if not os.path.exists(regs_path):
            logger.error(f"File not found: {regs_path}")
            logger.info(
                "\nTo get this file:\n"
                "  1. Go to https://www.faa.gov/licenses_certificates/"
                "aircraft_certification/aircraft_registry/"
                "releasable_aircraft_download\n"
                "  2. Download the ReleasableAircraft.zip\n"
                "  3. Extract MASTER.txt into: data/faa_csv/\n"
            )
        else:
            from data.fetchers.faa_fetcher import import_registrations

            count = import_registrations(csv_path=regs_path)
            logger.info(f"Registrations imported: {count:,} new records")

    # Incidents
    if not args.regs_only:
        logger.info("── Importing incidents ───────────────────────")

        incidents_path = args.incidents_path or os.path.join(FAA_DATA_DIR, "incidents.csv")

        if not os.path.exists(incidents_path):
            logger.warning(f"Incident file not found: {incidents_path}")
            logger.info(
                "\nTo add incident data:\n"
                "  Option A: Download from https://asias.faa.gov\n"
                "  Option B: Create data/faa_csv/incidents.csv manually\n"
                "  Required columns: DATE, LOCATION, COUNTY, LATITUDE,\n"
                "                    LONGITUDE, DESCRIPTION, SEVERITY, REPORTED_BY\n"
            )
        else:
            from data.fetchers.faa_fetcher import import_incidents

            count = import_incidents(csv_path=incidents_path)
            logger.info(f"Incidents imported: {count:,} new records")

    # Final summary
    logger.info("── Import complete ───────────────────────────")
    reg_total = DroneRegistration.query.filter_by(owner_state="WA").count()
    inc_total = IncidentReport.query.count()
    logger.info(f"  WA registrations in DB : {reg_total:,}")
    logger.info(f"  Incidents in DB        : {inc_total:,}")
    logger.info("─────────────────────────────────────────────")
