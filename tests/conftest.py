"""
tests/conftest.py

pytest configuration and shared fixtures.


    A fixture is a function decorated with @pytest.fixture that sets up
    (and optionally tears down) something a test needs — like a database,
    a test client, or sample data. pytest automatically injects fixtures
    into test functions that list them as parameters.


    pytest automatically loads conftest.py before running tests. Any fixtures
    defined here are available to ALL test files in the same directory and
    subdirectories — no import needed.

Fixture scopes:
    "function" (default) — set up and torn down for EACH test function
    "module"             — set up once per test file
    "session"            — set up once for the entire test run


"""

import pytest
import os
from datetime import date, datetime

from app import create_app
from models.models import db as _db, FlightRecord, DroneRegistration, IncidentReport

# App + database fixtures


@pytest.fixture(scope="session")
def app():
    """
    Creates a Flask app configured for testing.

    scope="session" means this app instance is shared across all tests.
    Override config values to use an in-memory SQLite database so
    tests never touch the real drone_data.db file.

    TESTING=True tells Flask to propagate exceptions instead of returning
    500 responses — this gives better error messages in tests.
    """
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_PATH"] = ":memory:"

    test_app = create_app()
    test_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })
    return test_app


@pytest.fixture(scope="function")
def db(app):
    """
    Creates all database tables, yields the db object for use in tests,
    then drops all tables after the test completes.

    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app, db):
    """
    A Flask test client that can make HTTP requests to the app
    without starting a real server.

    Injecting 'db' here ensures the database is set up before
    any HTTP requests are made.
    """
    with app.test_client() as c:
        yield c


# Sample data fixtures
# These fixtures insert realistic sample records into the test database.
# Tests that need data can request these fixtures by name.


@pytest.fixture
def sample_flights(db, app):
    """Inserts 3 flight records covering different counties and altitudes."""
    with app.app_context():
        flights = [
            FlightRecord(
                icao24="abc123",
                callsign="DRONE1",
                latitude=47.6062,
                longitude=-122.3321,  # Seattle (King County)
                altitude=45.0,
                velocity=5.5,
                heading=90.0,
                on_ground=False,
                county="King",
                recorded_at=datetime(2024, 6, 1, 12, 0, 0),
            ),
            FlightRecord(
                icao24="def456",
                callsign="DRONE2",
                latitude=47.2529,
                longitude=-122.4443,  # Tacoma (Pierce County)
                altitude=85.0,
                velocity=8.2,
                heading=180.0,
                on_ground=False,
                county="Pierce",
                recorded_at=datetime(2024, 6, 1, 12, 5, 0),
            ),
            FlightRecord(
                icao24="ghi789",
                callsign="",
                latitude=47.9790,
                longitude=-122.2021,  # Everett (Snohomish County)
                altitude=110.0,
                velocity=3.1,
                heading=270.0,
                on_ground=False,
                county="Snohomish",
                recorded_at=datetime(2024, 6, 1, 12, 10, 0),
            ),
        ]
        _db.session.add_all(flights)
        _db.session.commit()
        return flights


@pytest.fixture
def sample_registrations(db, app):
    """Inserts 4 drone registrations with mixed purposes and counties."""
    with app.app_context():
        regs = [
            DroneRegistration(
                registration_no="N001WA",
                owner_state="WA",
                owner_county="King",
                drone_type="Rotorcraft",
                purpose="Commercial",
                registered_date=date(2022, 3, 15),
            ),
            DroneRegistration(
                registration_no="N002WA",
                owner_state="WA",
                owner_county="King",
                drone_type="Fixed Wing Single Engine",
                purpose="Recreational",
                registered_date=date(2022, 7, 4),
            ),
            DroneRegistration(
                registration_no="N003WA",
                owner_state="WA",
                owner_county="Pierce",
                drone_type="Rotorcraft",
                purpose="Commercial",
                registered_date=date(2023, 1, 20),
            ),
            DroneRegistration(
                registration_no="N004WA",
                owner_state="WA",
                owner_county="Spokane",
                drone_type="UAS / Drone",
                purpose="Recreational",
                registered_date=date(2023, 9, 1),
            ),
        ]
        _db.session.add_all(regs)
        _db.session.commit()
        return regs


@pytest.fixture
def sample_incidents(db, app):
    """Inserts 3 incident reports with different severities."""
    with app.app_context():
        incidents = [
            IncidentReport(
                incident_date=date(2024, 1, 10),
                location="Seattle",
                county="King",
                latitude=47.6062,
                longitude=-122.3321,
                description="Drone flew near SeaTac approach path.",
                severity="Moderate",
                reported_by="FAA",
            ),
            IncidentReport(
                incident_date=date(2024, 3, 22),
                location="Tacoma",
                county="Pierce",
                latitude=47.2529,
                longitude=-122.4443,
                description="Drone collided with power line.",
                severity="Severe",
                reported_by="Utility Company",
            ),
            IncidentReport(
                incident_date=date(2024, 5, 5),
                location="Bellingham",
                county="Whatcom",
                latitude=48.7519,
                longitude=-122.4787,
                description="Unauthorized flight near hospital.",
                severity="Minor",
                reported_by="Local PD",
            ),
        ]
        _db.session.add_all(incidents)
        _db.session.commit()
        return incidents
