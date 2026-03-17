"""
tests/test_fetchers.py

Unit tests for the OpenSky and FAA data fetchers.

Key technique: mocking external HTTP calls.


Using unittest.mock.patch to replace requests.get with a fake
    function that returns a controlled response. The code under test
    doesn't know it's talking to a mock.

    @patch("module.path.to.requests.get", ...) replaces requests.get
    inside the fetcher module for the duration of the test.
"""

import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile
import csv

from data.fetchers.opensky_fetcher import fetch_wa_flights

# Helpers


def make_mock_response(json_data, status_code=200):
    """
    Creates a MagicMock that mimics a requests.Response object.
    MagicMock lets you set any attribute or return value.
    """
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    # raise_for_status() should do nothing for success codes
    mock.raise_for_status.return_value = None
    return mock


# OpenSky fetcher tests


class TestFetchWaFlights:

    # A realistic OpenSky API response for testing.
    # Each inner list is a state vector. Field positions match the API docs.
    MOCK_OPENSKY_RESPONSE = {
        "time": 1717200000,
        "states": [
            # icao24, callsign, origin, time_pos, last_contact,
            # lon, lat, baro_alt, on_ground, velocity, true_track, ...
            [
                "abc123",
                "DRONE1  ",
                "WA",
                1717200000,
                1717200000,
                -122.33,
                47.61,
                45.0,
                False,
                5.5,
                90.0,
                0.0,
                None,
                None,
                False,
                0,
                "",
            ],
            [
                "def456",
                "DRONE2  ",
                "WA",
                1717200000,
                1717200000,
                -122.44,
                47.25,
                85.0,
                False,
                8.2,
                180.0,
                0.0,
                None,
                None,
                False,
                0,
                "",
            ],
            # This one is on the ground — should be filtered out
            [
                "ghi789",
                "GROUND  ",
                "WA",
                1717200000,
                1717200000,
                -122.20,
                47.98,
                0.0,
                True,
                0.0,
                0.0,
                0.0,
                None,
                None,
                False,
                0,
                "",
            ],
            # This one is too high (commercial aircraft) — should be filtered
            [
                "jkl012",
                "SEA123  ",
                "WA",
                1717200000,
                1717200000,
                -122.31,
                47.45,
                9000.0,
                False,
                250.0,
                45.0,
                0.0,
                None,
                None,
                False,
                0,
                "",
            ],
        ],
    }

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_returns_list_of_dicts(self, mock_get):
        """fetch_wa_flights() should return a list of flight dicts."""
        mock_get.return_value = make_mock_response(self.MOCK_OPENSKY_RESPONSE)
        result = fetch_wa_flights()
        assert isinstance(result, list)

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_filters_out_ground_flights(self, mock_get):
        """Flights with on_ground=True should be excluded."""
        mock_get.return_value = make_mock_response(self.MOCK_OPENSKY_RESPONSE)
        result = fetch_wa_flights()
        for flight in result:
            assert flight["on_ground"] is False

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_filters_out_high_altitude(self, mock_get):
        """Flights above DRONE_MAX_ALTITUDE_METERS (122m) should be excluded."""
        mock_get.return_value = make_mock_response(self.MOCK_OPENSKY_RESPONSE)
        result = fetch_wa_flights()
        for flight in result:
            assert flight["altitude"] <= 122

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_returns_correct_count(self, mock_get):
        """
        Mock has 4 states: 1 on ground, 1 too high, 2 valid drones.
        Should return exactly 2.
        """
        mock_get.return_value = make_mock_response(self.MOCK_OPENSKY_RESPONSE)
        result = fetch_wa_flights()
        assert len(result) == 2

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_maps_fields_correctly(self, mock_get):
        """Returned dicts should have the correct field names and values."""
        mock_get.return_value = make_mock_response(self.MOCK_OPENSKY_RESPONSE)
        result = fetch_wa_flights()

        first = result[0]
        assert first["icao24"] == "abc123"
        assert first["callsign"] == "DRONE1"  # stripped
        assert first["latitude"] == 47.61
        assert first["longitude"] == -122.33
        assert first["altitude"] == 45.0
        assert first["on_ground"] is False

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_handles_empty_states(self, mock_get):
        """If OpenSky returns no aircraft, should return an empty list."""
        mock_get.return_value = make_mock_response({"time": 0, "states": []})
        result = fetch_wa_flights()
        assert result == []

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_handles_null_states(self, mock_get):
        """Some API responses have 'states': null — should handle gracefully."""
        mock_get.return_value = make_mock_response({"time": 0, "states": None})
        result = fetch_wa_flights()
        assert result == []

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_returns_empty_on_timeout(self, mock_get):
        """If the request times out, should return [] without crashing."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()
        result = fetch_wa_flights()
        assert result == []

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_returns_empty_on_connection_error(self, mock_get):
        """If the server is unreachable, should return [] without crashing."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError()
        result = fetch_wa_flights()
        assert result == []

    @patch("data.fetchers.opensky_fetcher.requests.get")
    def test_passes_wa_bounds_to_api(self, mock_get):
        """The API call must include the Washington State bounding box params."""
        mock_get.return_value = make_mock_response({"states": []})
        fetch_wa_flights()

        # Verify the call was made with the correct bounding box params
        call_kwargs = mock_get.call_args
        params = call_kwargs[1]["params"]  # keyword arg named 'params'
        assert "lamin" in params
        assert "lamax" in params
        assert "lomin" in params
        assert "lomax" in params
        # WA southern border should be around 45.5
        assert params["lamin"] == pytest.approx(45.5, abs=0.5)


# FAA fetcher tests


class TestFaaFetcher:

    def _make_temp_csv(self, rows, fieldnames):
        """Helper: writes a CSV to a temp file and returns the path."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp.close()
        return tmp.name

    def test_import_registrations_skips_missing_file(self, app):
        """If the CSV doesn't exist, import should log a warning and return 0."""
        from data.fetchers.faa_fetcher import import_registrations

        with app.app_context():
            count = import_registrations(csv_path="/nonexistent/path/MASTER.txt")
        assert count == 0

    def test_import_registrations_filters_to_wa(self, db, app):
        """Only rows with STATE='WA' should be imported."""
        from data.fetchers.faa_fetcher import import_registrations

        rows = [
            {
                "N-NUMBER": "N001",
                "STATE": "WA",
                "COUNTY": "King",
                "TYPE AIRCRAFT": "6",
                "TYPE REGISTRANT": "1",
                "CERT ISSUE DATE": "01/15/2023",
            },
            {
                "N-NUMBER": "N002",
                "STATE": "OR",
                "COUNTY": "Multnomah",
                "TYPE AIRCRAFT": "6",
                "TYPE REGISTRANT": "1",
                "CERT ISSUE DATE": "02/20/2023",
            },
        ]
        fieldnames = [
            "N-NUMBER",
            "STATE",
            "COUNTY",
            "TYPE AIRCRAFT",
            "TYPE REGISTRANT",
            "CERT ISSUE DATE",
        ]
        path = self._make_temp_csv(rows, fieldnames)

        try:
            with app.app_context():
                count = import_registrations(csv_path=path)
            assert count == 1  # Only WA row imported
        finally:
            os.unlink(path)

    def test_import_registrations_skips_duplicates(self, db, app):
        """Re-importing the same CSV should not create duplicate records."""
        from data.fetchers.faa_fetcher import import_registrations

        rows = [
            {
                "N-NUMBER": "N999",
                "STATE": "WA",
                "COUNTY": "King",
                "TYPE AIRCRAFT": "U",
                "TYPE REGISTRANT": "3",
                "CERT ISSUE DATE": "03/01/2023",
            }
        ]
        fieldnames = list(rows[0].keys())
        path = self._make_temp_csv(rows, fieldnames)

        try:
            with app.app_context():
                first = import_registrations(csv_path=path)
                second = import_registrations(csv_path=path)
            assert first == 1
            assert second == 0  # Already exists, no duplicates
        finally:
            os.unlink(path)

    def test_import_incidents_skips_missing_file(self, app):
        """If incidents CSV doesn't exist, should return 0 without crashing."""
        from data.fetchers.faa_fetcher import import_incidents

        with app.app_context():
            count = import_incidents(csv_path="/nonexistent/incidents.csv")
        assert count == 0

    def test_import_incidents_inserts_correctly(self, db, app):
        """Valid incidents CSV rows should all be inserted."""
        from data.fetchers.faa_fetcher import import_incidents

        rows = [
            {
                "DATE": "2024-01-10",
                "LOCATION": "Seattle",
                "COUNTY": "King",
                "LATITUDE": "47.6062",
                "LONGITUDE": "-122.3321",
                "DESCRIPTION": "Near miss",
                "SEVERITY": "Moderate",
                "REPORTED_BY": "FAA",
            },
            {
                "DATE": "2024-03-15",
                "LOCATION": "Tacoma",
                "COUNTY": "Pierce",
                "LATITUDE": "47.2529",
                "LONGITUDE": "-122.4443",
                "DESCRIPTION": "Flyover hospital",
                "SEVERITY": "Severe",
                "REPORTED_BY": "Local PD",
            },
        ]
        fieldnames = list(rows[0].keys())
        path = self._make_temp_csv(rows, fieldnames)

        try:
            with app.app_context():
                count = import_incidents(csv_path=path)
            assert count == 2
        finally:
            os.unlink(path)
