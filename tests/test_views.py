"""
tests/test_views.py

Integration tests for the HTML page routes in routes/views.py.

These tests verify that:
    - Each page route returns HTTP 200
    - The response is HTML (not JSON or a redirect)
    - Key content is present in the rendered HTML
      (e.g. chart canvas IDs, table headers, nav links)

We check for HTML content using simple string containment rather than
a full HTML parser — fast and sufficient for smoke-testing page rendering.

"Smoke tests" = quick sanity checks that the page doesn't crash.

"""
class TestDashboardPage:

    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        response = client.get("/")
        assert b"text/html" in response.content_type.encode()

    def test_index_contains_chart_canvases(self, client):
        """The dashboard must have the canvas IDs that dashboard.js targets."""
        response = client.get("/")
        html = response.data
        assert b"countyChart" in html
        assert b"purposeChart" in html
        assert b"altitudeChart" in html

    def test_index_contains_kpi_elements(self, client):
        """KPI card element IDs must be present for dashboard.js to update."""
        response = client.get("/")
        html = response.data
        assert b"kpi-total-flights" in html
        assert b"kpi-active-flights" in html
        assert b"kpi-registrations" in html
        assert b"kpi-incidents" in html

    def test_index_contains_nav_links(self, client):
        """Navigation bar should contain links to all pages."""
        response = client.get("/")
        html = response.data
        assert b'href="/map"' in html
        assert b'href="/incidents"' in html
        assert b'href="/registrations"' in html

    def test_index_shows_server_side_stats(
        self, client, sample_flights, sample_registrations, sample_incidents
    ):
        """
        The index route passes stats to the template for server-side rendering.
        With 3 flights inserted, the number '3' should appear in the HTML.
        """
        response = client.get("/")
        # The KPI value is rendered directly into the HTML by Jinja2
        assert b"3" in response.data


class TestMapPage:

    def test_map_returns_200(self, client):
        response = client.get("/map")
        assert response.status_code == 200

    def test_map_contains_leaflet(self, client):
        """Leaflet.js must be loaded on the map page."""
        response = client.get("/map")
        assert b"leaflet" in response.data.lower()

    def test_map_contains_map_div(self, client):
        """The #map div is required for Leaflet to render into."""
        response = client.get("/map")
        assert b'id="map"' in response.data

    def test_map_contains_filter_controls(self, client):
        """County filter and altitude slider must be present."""
        response = client.get("/map")
        assert b'id="county-filter"' in response.data
        assert b'id="alt-filter"' in response.data


class TestIncidentsPage:

    def test_incidents_returns_200(self, client):
        response = client.get("/incidents")
        assert response.status_code == 200

    def test_incidents_contains_table(self, client):
        """The incidents table and tbody must exist for incidents.js."""
        response = client.get("/incidents")
        assert b'id="incidents-table"' in response.data
        assert b'id="incidents-body"' in response.data

    def test_incidents_contains_filter_bar(self, client):
        response = client.get("/incidents")
        assert b'id="search-input"' in response.data
        assert b'id="severity-filter"' in response.data
        assert b'id="county-filter"' in response.data

    def test_incidents_contains_export_button(self, client):
        response = client.get("/incidents")
        assert b'id="export-btn"' in response.data

    def test_incidents_contains_modal(self, client):
        """The detail modal must exist in the DOM (hidden by default)."""
        response = client.get("/incidents")
        assert b'id="modal-overlay"' in response.data


class TestRegistrationsPage:

    def test_registrations_returns_200(self, client):
        response = client.get("/registrations")
        assert response.status_code == 200

    def test_registrations_contains_charts(self, client):
        response = client.get("/registrations")
        assert b"regsByCountyChart" in response.data
        assert b"trendChart" in response.data

    def test_registrations_contains_table(self, client):
        response = client.get("/registrations")
        assert b'id="reg-table"' in response.data


class TestErrorPages:

    def test_404_page_renders(self, client):
        response = client.get("/this-page-does-not-exist")
        assert response.status_code == 404
        # Should render HTML, not a raw Flask error
        assert b"text/html" in response.content_type.encode()

    def test_all_pages_share_nav(self, client):
        """
        Every page extends base.html, so every page should contain
        the brand name in the nav.
        """
        for url in ["/", "/map", "/incidents", "/registrations"]:
            response = client.get(url)
            assert b"WA Drone Tracker" in response.data, f"Nav brand not found on {url}"
