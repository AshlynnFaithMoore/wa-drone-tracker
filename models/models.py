"""
models/models.py

Defines the database tables using SQLAlchemy's ORM (Object Relational Mapper).

Instead of writing raw SQL like:
    CREATE TABLE flights (id INTEGER PRIMARY KEY, callsign TEXT, ...)

We define Python classes. SQLAlchemy translates them into SQL automatically.
Each class = one database table. Each class attribute = one column.

db is a SQLAlchemy instance that gets initialized in app.py and passed around.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

# This db object is created here and imported by app.py.
# app.py calls db.init_app(app) to connect it to the Flask app.
db = SQLAlchemy()


class FlightRecord(db.Model):
    """
    Represents a single drone flight observation captured from the OpenSky API.
    Each time we poll OpenSky, we save every low-altitude aircraft in WA as a row.

    OpenSky returns a "state vector" for each aircraft — a snapshot of its
    position, speed, and altitude at a given moment.
    """

    __tablename__ = "flight_records"

    id = db.Column(db.Integer, primary_key=True)  # Auto-incrementing unique ID
    icao24 = db.Column(db.String(10))  # Unique aircraft transponder ID (hex string)
    callsign = db.Column(db.String(20))  # Flight callsign (may be empty for drones)
    latitude = db.Column(db.Float)  # Current latitude
    longitude = db.Column(db.Float)  # Current longitude
    altitude = db.Column(db.Float)  # Altitude in meters (baro or geo)
    velocity = db.Column(db.Float)  # Speed in m/s
    heading = db.Column(db.Float)  # Direction of travel in degrees (0–360)
    on_ground = db.Column(db.Boolean)  # True if the aircraft is on the ground
    county = db.Column(db.String(50))  # WA county (we compute this from lat/lon)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)  # When we captured this

    def to_dict(self):
        """
        Converts this record to a plain Python dictionary.
        Flask's jsonify() can then serialize it to JSON for the frontend.
        """
        return {
            "id": self.id,
            "icao24": self.icao24,
            "callsign": self.callsign,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "velocity": self.velocity,
            "heading": self.heading,
            "on_ground": self.on_ground,
            "county": self.county,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class DroneRegistration(db.Model):
    """
    Represents a registered drone (UAS) from FAA data.
    The FAA releases registration data as downloadable CSV files.
    We import those CSVs into this table.
    """

    __tablename__ = "drone_registrations"

    id = db.Column(db.Integer, primary_key=True)
    registration_no = db.Column(db.String(20), unique=True)  # FAA N-number
    owner_state = db.Column(db.String(5))  # State code, e.g. "WA"
    owner_county = db.Column(db.String(50))  # County name
    drone_type = db.Column(db.String(30))  # e.g. "Fixed Wing", "Rotorcraft"
    purpose = db.Column(db.String(20))  # "Commercial" or "Recreational"
    registered_date = db.Column(db.Date)  # Date of FAA registration

    def to_dict(self):
        return {
            "id": self.id,
            "registration_no": self.registration_no,
            "owner_state": self.owner_state,
            "owner_county": self.owner_county,
            "drone_type": self.drone_type,
            "purpose": self.purpose,
            "registered_date": str(self.registered_date) if self.registered_date else None,
        }


class IncidentReport(db.Model):
    """
    Represents a drone incident or accident in Washington State.
    Source: FAA Wildlife Strike Database or manually entered reports.
    """

    __tablename__ = "incident_reports"

    id = db.Column(db.Integer, primary_key=True)
    incident_date = db.Column(db.Date)
    location = db.Column(db.String(100))  # City or area description
    county = db.Column(db.String(50))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text)  # What happened
    severity = db.Column(db.String(20))  # "Minor", "Moderate", "Severe"
    reported_by = db.Column(db.String(50))  # Agency that filed the report

    def to_dict(self):
        return {
            "id": self.id,
            "incident_date": str(self.incident_date) if self.incident_date else None,
            "location": self.location,
            "county": self.county,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "description": self.description,
            "severity": self.severity,
            "reported_by": self.reported_by,
        }
