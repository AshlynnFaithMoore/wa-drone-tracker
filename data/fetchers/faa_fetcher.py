"""
data/fetchers/faa_fetcher.py

Imports FAA drone registration and incident data from CSV files
into the local SQLite database.

Why CSV instead of a live API?
    The FAA doesn't expose a public REST API for UAS registrations (womp womp).
    Instead, they publish downloadable data files periodically.
    We import those files once rather than
    fetching live data.

Where to download the files:
    Registrations:
        https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download
        → Download the full registry ZIP, extract MASTER.txt (it's a CSV)

    Incidents:
        https://asias.faa.gov/  (Aviation Safety Information Analysis and Sharing)
        Or manually curated CSV placed in data/faa_csv/incidents.csv

Expected CSV column names are defined in the COLUMN MAPS below.
This way if the FAA changes their format, only these dicts need updating.
"""

import os
import logging
import pandas as pd
from datetime import datetime

from models.models import db, DroneRegistration, IncidentReport
from config import FAA_DATA_DIR

logger = logging.getLogger(__name__)


# Column maps

# Maps our internal field names → FAA CSV column names.

REGISTRATION_COLS = {
    "registration_no": "N-NUMBER",  # e.g. "N12345A"
    "owner_state": "STATE",  # e.g. "WA"
    "owner_county": "COUNTY",
    "drone_type": "TYPE AIRCRAFT",  # Numeric code — see TYPE_MAP below
    "purpose": "TYPE REGISTRANT",  # 1=Individual(Rec), 2=Corp(Commercial)…
    "registered_date": "CERT ISSUE DATE",
}

# FAA aircraft type codes → human-readable strings
# Full list: https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/media/ardata.pdf
TYPE_MAP = {
    "1": "Glider",
    "2": "Balloon",
    "3": "Blimp",
    "4": "Fixed Wing Single Engine",
    "5": "Fixed Wing Multi Engine",
    "6": "Rotorcraft",
    "7": "Weight-Shift",
    "8": "Powered Parachute",
    "9": "Gyroplane",
    "H": "Hybrid Lift",
    "U": "UAS / Drone",
}

# FAA registrant type codes → Commercial vs Recreational
PURPOSE_MAP = {
    "1": "Recreational",  # Individual
    "2": "Commercial",  # Partnership
    "3": "Commercial",  # Corporation
    "4": "Commercial",  # Co-Owned
    "5": "Commercial",  # Government
    "8": "Recreational",  # Non-Citizen Corporation
    "9": "Commercial",  # Air Carrier
}

INCIDENT_COLS = {
    "incident_date": "DATE",
    "location": "LOCATION",
    "county": "COUNTY",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "description": "DESCRIPTION",
    "severity": "SEVERITY",
    "reported_by": "REPORTED_BY",
}


# Registration importer


def import_registrations(csv_path=None):
    """
    Reads the FAA MASTER.txt registration CSV and inserts Washington State
    drone registrations into the DroneRegistration table.

    Skips rows that already exist (checks by registration_no) to avoid
    duplicates when you re-run the import.

    Parameters:
        csv_path: Optional path override. Defaults to FAA_DATA_DIR/MASTER.txt
    """
    path = csv_path or os.path.join(FAA_DATA_DIR, "MASTER.txt")
    if not os.path.exists(path):
        logger.error(f"Registration CSV not found: {path}")
        logger.info(
            "Download from: https://www.faa.gov/licenses_certificates/"
            "aircraft_certification/aircraft_registry/releasable_aircraft_download"
        )
        return 0

    logger.info(f"Reading registration CSV: {path}")

    # The FAA MASTER.txt uses comma separation and has a header row.
    # low_memory=False prevents pandas from guessing column types mid-file.
    try:
        df = pd.read_csv(path, low_memory=False, dtype=str)
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return 0

    # Strip whitespace from all column names
    df.columns = df.columns.str.strip()

    # Filter to Washington State only
    if "STATE" not in df.columns:
        logger.error("'STATE' column not found — check CSV format")
        return 0

    df = df[df["STATE"].str.strip() == "WA"].copy()
    logger.info(f"Found {len(df)} WA registrations in CSV")

    # Get existing registration numbers to skip duplicates
    existing = {
        r.registration_no
        for r in DroneRegistration.query.with_entities(DroneRegistration.registration_no).all()
    }

    inserted = 0
    for _, row in df.iterrows():
        reg_no = str(row.get("N-NUMBER", "")).strip()
        if not reg_no or reg_no in existing:
            continue

        # Parse registration date (FAA format: MM/DD/YYYY or YYYYMMDD)
        reg_date = None
        raw_date = str(row.get("CERT ISSUE DATE", "")).strip()
        for fmt in ("%m/%d/%Y", "%Y%m%d", "%Y-%m-%d"):
            try:
                reg_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue

        record = DroneRegistration(
            registration_no=reg_no,
            owner_state=str(row.get("STATE", "")).strip(),
            owner_county=str(row.get("COUNTY", "")).strip(),
            drone_type=TYPE_MAP.get(str(row.get("TYPE AIRCRAFT", "")).strip(), "Unknown"),
            purpose=PURPOSE_MAP.get(str(row.get("TYPE REGISTRANT", "")).strip(), "Unknown"),
            registered_date=reg_date,
        )
        db.session.add(record)
        existing.add(reg_no)
        inserted += 1

        # Commit in batches of 500 to avoid holding a huge transaction open
        if inserted % 500 == 0:
            db.session.commit()
            logger.info(f"  {inserted} records inserted so far…")

    db.session.commit()
    logger.info(f"Registration import complete: {inserted} new records added")
    return inserted


# Incident importer


def import_incidents(csv_path=None):
    """
    Reads a drone incident CSV and inserts new records into the
    IncidentReport table.

    The incident CSV format is more flexible — the column names are
    configured in INCIDENT_COLS above.

    Parameters:
        csv_path: Optional path override. Defaults to FAA_DATA_DIR/incidents.csv
    """
    path = csv_path or os.path.join(FAA_DATA_DIR, "incidents.csv")
    if not os.path.exists(path):
        logger.warning(f"Incident CSV not found: {path}")
        logger.info("Place your incident CSV at: " + path)
        return 0

    logger.info(f"Reading incident CSV: {path}")

    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as e:
        logger.error(f"Failed to read incident CSV: {e}")
        return 0

    df.columns = df.columns.str.strip()

    inserted = 0
    for _, row in df.iterrows():
        # Parse date
        raw_date = str(row.get(INCIDENT_COLS["incident_date"], "")).strip()
        inc_date = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d"):
            try:
                inc_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue

        # Safely parse lat/lon
        def safe_float(val):
            try:
                return float(val)
            except:
                return None

        record = IncidentReport(
            incident_date=inc_date,
            location=str(row.get(INCIDENT_COLS["location"], "")).strip() or None,
            county=str(row.get(INCIDENT_COLS["county"], "")).strip() or None,
            latitude=safe_float(row.get(INCIDENT_COLS["latitude"])),
            longitude=safe_float(row.get(INCIDENT_COLS["longitude"])),
            description=str(row.get(INCIDENT_COLS["description"], "")).strip() or None,
            severity=str(row.get(INCIDENT_COLS["severity"], "")).strip() or None,
            reported_by=str(row.get(INCIDENT_COLS["reported_by"], "")).strip() or None,
        )
        db.session.add(record)
        inserted += 1

    db.session.commit()
    logger.info(f"Incident import complete: {inserted} records added")
    return inserted


# Combined runner


def run_all_imports():
    """
    Convenience function to run all FAA imports in sequence.
    Can be called from app.py startup or a CLI script.
    """
    logger.info("=== Starting FAA data import ===")
    regs = import_registrations()
    incidents = import_incidents()
    logger.info(f"=== Import complete: {regs} registrations, {incidents} incidents ===")
