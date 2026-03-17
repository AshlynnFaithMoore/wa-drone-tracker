"""
tests/test_stats_processor.py

Unit tests for data/processors/stats_processor.py

Unit tests test a single function in isolation.


Naming conventions pytest uses for test discovery:
    - Files must be named test_*.py or *_test.py
    - Test functions must start with test_
    - Test classes must start with Test (and methods with test_)
"""


from datetime import datetime, timedelta
from models.models import FlightRecord, DroneRegistration
from models.models import db as _db
from data.processors.stats_processor import (
    get_overview_stats,
    get_flights_by_county,
    get_recent_flights,
    get_registrations_by_purpose,
    get_altitude_distribution,
    save_flights,
)

# get_overview_stats()


class TestGetOverviewStats:
    """
    Groups related tests for get_overview_stats().

    """

    def test_returns_zero_counts_on_empty_db(self, db, app):
        """With no data in the database, all stats should be 0."""
        with app.app_context():
            stats = get_overview_stats()

        assert stats["total_flights"] == 0
        assert stats["active_flights"] == 0
        assert stats["total_registrations"] == 0
        assert stats["total_incidents"] == 0

    def test_counts_all_flight_records(self, sample_flights, app):
        """total_flights should equal the number of FlightRecord rows."""
        with app.app_context():
            stats = get_overview_stats()
        assert stats["total_flights"] == 3

    def test_active_flights_only_counts_recent(self, db, app):
        """
        active_flights counts records from the last hour only.
        We insert one recent flight and one old flight and verify
        only the recent one is counted.
        """
        with app.app_context():
            old_flight = FlightRecord(
                icao24="old001",
                latitude=47.6,
                longitude=-122.3,
                altitude=50.0,
                on_ground=False,
                county="King",
                recorded_at=datetime.utcnow() - timedelta(hours=2),  # 2 hours ago
            )
            new_flight = FlightRecord(
                icao24="new001",
                latitude=47.6,
                longitude=-122.3,
                altitude=50.0,
                on_ground=False,
                county="King",
                recorded_at=datetime.utcnow() - timedelta(minutes=10),  # 10 min ago
            )
            _db.session.add_all([old_flight, new_flight])
            _db.session.commit()

            stats = get_overview_stats()

        assert stats["active_flights"] == 1
        assert stats["total_flights"] == 2

    def test_counts_only_wa_registrations(self, db, app):
        """
        total_registrations should only count WA state registrations,
        not registrations from other states.
        """
        with app.app_context():
            wa_reg = DroneRegistration(
                registration_no="N100WA",
                owner_state="WA",
                owner_county="King",
                purpose="Recreational",
            )
            or_reg = DroneRegistration(
                registration_no="N100OR",
                owner_state="OR",
                owner_county="Multnomah",
                purpose="Recreational",
            )
            _db.session.add_all([wa_reg, or_reg])
            _db.session.commit()

            stats = get_overview_stats()

        assert stats["total_registrations"] == 1

    def test_counts_all_incidents(self, sample_incidents, app):
        """total_incidents should equal the number of IncidentReport rows."""
        with app.app_context():
            stats = get_overview_stats()
        assert stats["total_incidents"] == 3

    def test_returns_dict_with_required_keys(self, db, app):
        """The returned dict must always contain all four expected keys."""
        with app.app_context():
            stats = get_overview_stats()
        expected_keys = {
            "total_flights",
            "active_flights",
            "total_registrations",
            "total_incidents",
        }
        assert expected_keys.issubset(stats.keys())


# get_flights_by_county()


class TestGetFlightsByCounty:

    def test_returns_empty_list_when_no_data(self, db, app):
        with app.app_context():
            result = get_flights_by_county()
        assert result == []

    def test_groups_correctly(self, sample_flights, app):
        """
        With King(1), Pierce(1), Snohomish(1) flights, should get
        3 rows each with count=1.
        """
        with app.app_context():
            result = get_flights_by_county()

        counties = {r["county"] for r in result}
        assert counties == {"King", "Pierce", "Snohomish"}
        for row in result:
            assert row["count"] == 1

    def test_sorted_descending_by_count(self, db, app):
        """Results should be sorted highest count first."""
        with app.app_context():
            # Add 3 King, 2 Pierce, 1 Snohomish
            for _ in range(3):
                _db.session.add(
                    FlightRecord(
                        icao24="k1",
                        latitude=47.6,
                        longitude=-122.3,
                        altitude=50.0,
                        on_ground=False,
                        county="King",
                    )
                )
            for _ in range(2):
                _db.session.add(
                    FlightRecord(
                        icao24="p1",
                        latitude=47.2,
                        longitude=-122.4,
                        altitude=50.0,
                        on_ground=False,
                        county="Pierce",
                    )
                )
            _db.session.add(
                FlightRecord(
                    icao24="s1",
                    latitude=48.0,
                    longitude=-122.2,
                    altitude=50.0,
                    on_ground=False,
                    county="Snohomish",
                )
            )
            _db.session.commit()

            result = get_flights_by_county()

        assert result[0]["county"] == "King"
        assert result[0]["count"] == 3
        assert result[1]["county"] == "Pierce"
        assert result[1]["count"] == 2


# get_recent_flights()


class TestGetRecentFlights:

    def test_returns_list_of_dicts(self, sample_flights, app):
        with app.app_context():
            result = get_recent_flights()
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_respects_limit(self, db, app):
        """Should never return more rows than the limit parameter."""
        with app.app_context():
            for i in range(10):
                _db.session.add(
                    FlightRecord(
                        icao24=f"x{i:03d}",
                        latitude=47.6,
                        longitude=-122.3,
                        altitude=50.0,
                        on_ground=False,
                        county="King",
                    )
                )
            _db.session.commit()

            result = get_recent_flights(limit=5)

        assert len(result) == 5

    def test_includes_expected_fields(self, sample_flights, app):
        """Each returned dict should have lat, lon, county, altitude, etc."""
        with app.app_context():
            result = get_recent_flights()
        required_fields = {"id", "latitude", "longitude", "altitude", "county", "icao24"}
        for record in result:
            assert required_fields.issubset(record.keys())


# get_registrations_by_purpose()


class TestGetRegistrationsByPurpose:

    def test_correct_purpose_split(self, sample_registrations, app):
        """
        sample_registrations has 2 Commercial and 2 Recreational.
        Verify both are returned with correct counts.
        """
        with app.app_context():
            result = get_registrations_by_purpose()

        purposes = {r["purpose"]: r["count"] for r in result}
        assert purposes.get("Commercial") == 2
        assert purposes.get("Recreational") == 2


# get_altitude_distribution()


class TestGetAltitudeDistribution:

    def test_returns_empty_when_no_data(self, db, app):
        with app.app_context():
            result = get_altitude_distribution()
        assert result == []

    def test_correct_bucket_assignment(self, db, app):
        """
        Insert one flight at 20m (→ 0–25m bucket) and one at 60m (→ 50–75m).
        Verify they land in the correct buckets.
        """
        with app.app_context():
            _db.session.add(
                FlightRecord(
                    icao24="low",
                    latitude=47.6,
                    longitude=-122.3,
                    altitude=20.0,
                    on_ground=False,
                    county="King",
                )
            )
            _db.session.add(
                FlightRecord(
                    icao24="mid",
                    latitude=47.6,
                    longitude=-122.3,
                    altitude=60.0,
                    on_ground=False,
                    county="King",
                )
            )
            _db.session.commit()

            result = get_altitude_distribution()

        buckets = {r["range"]: r["count"] for r in result}
        assert buckets.get("0–25m") == 1
        assert buckets.get("50–75m") == 1

    def test_ignores_null_altitudes(self, db, app):
        """Flights with NULL altitude should be excluded from the histogram."""
        with app.app_context():
            _db.session.add(
                FlightRecord(
                    icao24="nullalt",
                    latitude=47.6,
                    longitude=-122.3,
                    altitude=None,
                    on_ground=False,
                    county="King",
                )
            )
            _db.session.commit()

            result = get_altitude_distribution()

        # All buckets should have count 0 (or no rows returned)
        total = sum(r["count"] for r in result)
        assert total == 0


# save_flights()


class TestSaveFlights:

    def test_saves_all_flights(self, db, app):
        """save_flights() should create a FlightRecord row for each input dict."""
        flights = [
            {
                "icao24": "aaa",
                "callsign": "T1",
                "latitude": 47.6,
                "longitude": -122.3,
                "altitude": 50.0,
                "velocity": 5.0,
                "heading": 90.0,
                "on_ground": False,
                "fetched_at": datetime.utcnow(),
            },
            {
                "icao24": "bbb",
                "callsign": "T2",
                "latitude": 47.2,
                "longitude": -122.4,
                "altitude": 80.0,
                "velocity": 7.0,
                "heading": 180.0,
                "on_ground": False,
                "fetched_at": datetime.utcnow(),
            },
        ]
        with app.app_context():
            save_flights(flights)
            count = FlightRecord.query.count()

        assert count == 2

    def test_handles_empty_list_gracefully(self, db, app):
        """save_flights([]) should not raise an exception."""
        with app.app_context():
            save_flights([])  # Should not raise
            assert FlightRecord.query.count() == 0
