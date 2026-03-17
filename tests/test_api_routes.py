"""
tests/test_api_routes.py

Integration tests for the Flask API endpoints in routes/api.py.

Integration tests verify that multiple components work together correctly —
here, the Flask routing layer + SQLAlchemy + the stats processor.

use Flask's test client (from conftest.py) to make HTTP requests
without starting a real server. The test client handles the full
request/response cycle including routing and middleware.

For each endpoint we test:
    1. HTTP status code is 200
    2. Response Content-Type is application/json
    3. Response body has the correct structure/values
    4. Edge cases (empty DB, unexpected input, etc.)
"""

import json

# Helper


def get_json(client, url):
    """
    Makes a GET request and returns the parsed JSON response body.
    Asserts 200 status and JSON content type as a baseline check.
    """
    response = client.get(url)
    assert response.status_code == 200, f"Expected 200 from {url}, got {response.status_code}"
    assert "application/json" in response.content_type, f"Expected JSON content type from {url}"
    return json.loads(response.data)


# GET /api/stats


class TestApiStats:

    def test_returns_200_with_empty_db(self, client):
        """Endpoint should work even with no data in the database."""
        data = get_json(client, "/api/stats")
        assert data["total_flights"] == 0
        assert data["active_flights"] == 0
        assert data["total_registrations"] == 0
        assert data["total_incidents"] == 0

    def test_returns_correct_counts(
        self, client, sample_flights, sample_registrations, sample_incidents
    ):
        """After seeding data, counts should match what was inserted."""
        data = get_json(client, "/api/stats")
        assert data["total_flights"] == 3
        assert data["total_registrations"] == 4
        assert data["total_incidents"] == 3

    def test_response_has_all_required_keys(self, client):
        data = get_json(client, "/api/stats")
        for key in ["total_flights", "active_flights", "total_registrations", "total_incidents"]:
            assert key in data, f"Missing key: {key}"


# GET /api/flights/by-county


class TestApiFlightsByCounty:

    def test_returns_empty_list_when_no_data(self, client):
        data = get_json(client, "/api/flights/by-county")
        assert data == []

    def test_returns_list_of_county_count_dicts(self, client, sample_flights):
        data = get_json(client, "/api/flights/by-county")
        assert isinstance(data, list)
        assert len(data) == 3  # King, Pierce, Snohomish

        for item in data:
            assert "county" in item
            assert "count" in item
            assert isinstance(item["count"], int)

    def test_sorted_descending(self, client, sample_flights):
        """Results should come back sorted by count, highest first."""
        data = get_json(client, "/api/flights/by-county")
        counts = [item["count"] for item in data]
        assert counts == sorted(counts, reverse=True)


# GET /api/flights/recent


class TestApiFlightsRecent:

    def test_returns_empty_list_when_no_data(self, client):
        data = get_json(client, "/api/flights/recent")
        assert data == []

    def test_returns_flight_records(self, client, sample_flights):
        data = get_json(client, "/api/flights/recent")
        assert len(data) == 3

    def test_each_record_has_coordinates(self, client, sample_flights):
        """Every record must have lat/lon for the map to place markers."""
        data = get_json(client, "/api/flights/recent")
        for record in data:
            assert "latitude" in record
            assert "longitude" in record
            assert record["latitude"] is not None
            assert record["longitude"] is not None

    def test_records_have_all_expected_fields(self, client, sample_flights):
        data = get_json(client, "/api/flights/recent")
        required = {"id", "icao24", "latitude", "longitude", "altitude", "county", "recorded_at"}
        for record in data:
            assert required.issubset(record.keys())


# GET /api/registrations/by-purpose


class TestApiRegistrationsByPurpose:

    def test_returns_empty_list_when_no_data(self, client):
        data = get_json(client, "/api/registrations/by-purpose")
        assert data == []

    def test_returns_purpose_counts(self, client, sample_registrations):
        data = get_json(client, "/api/registrations/by-purpose")
        purposes = {item["purpose"]: item["count"] for item in data}
        assert purposes["Commercial"] == 2
        assert purposes["Recreational"] == 2

    def test_each_item_has_required_keys(self, client, sample_registrations):
        data = get_json(client, "/api/registrations/by-purpose")
        for item in data:
            assert "purpose" in item
            assert "count" in item


# GET /api/flights/altitude-distribution


class TestApiAltitudeDistribution:

    def test_returns_empty_list_when_no_data(self, client):
        data = get_json(client, "/api/flights/altitude-distribution")
        assert data == []

    def test_returns_bucketed_data(self, client, sample_flights):
        """sample_flights has altitudes 45, 85, 110 → different buckets."""
        data = get_json(client, "/api/flights/altitude-distribution")
        assert isinstance(data, list)
        for item in data:
            assert "range" in item
            assert "count" in item


# GET /api/incidents


class TestApiIncidents:

    def test_returns_empty_list_when_no_data(self, client):
        data = get_json(client, "/api/incidents")
        assert data == []

    def test_returns_all_incidents(self, client, sample_incidents):
        data = get_json(client, "/api/incidents")
        assert len(data) == 3

    def test_incidents_sorted_newest_first(self, client, sample_incidents):
        """Most recent incident should be first."""
        data = get_json(client, "/api/incidents")
        dates = [item["incident_date"] for item in data]
        assert dates == sorted(dates, reverse=True)

    def test_each_incident_has_required_fields(self, client, sample_incidents):
        data = get_json(client, "/api/incidents")
        required = {"id", "incident_date", "location", "county", "severity", "description"}
        for item in data:
            assert required.issubset(item.keys())

    def test_severity_values_are_valid(self, client, sample_incidents):
        """Severity must be one of the three expected values."""
        valid_severities = {"Minor", "Moderate", "Severe"}
        data = get_json(client, "/api/incidents")
        for item in data:
            assert item["severity"] in valid_severities


# 404 handling


class TestErrorHandling:

    def test_unknown_api_route_returns_404(self, client):
        response = client.get("/api/this-does-not-exist")
        assert response.status_code == 404

    def test_unknown_page_returns_404(self, client):
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
