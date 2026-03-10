
# Overview 

WA Drone Tracker is a locally-hosted desktop application that aggregates drone data from two sources — the OpenSky Network (live flight telemetry) and the FAA (registration and incident records) — and presents it through an interactive browser-based dashboard controlled by a native Tkinter window.
The app is designed to run entirely on your local machine with no cloud dependencies. All data is stored in a local SQLite database. The Tkinter window acts as a control panel and status monitor, while the rich data visualizations (charts, maps, tables) are rendered in your default web browser via a locally-served Flask application.

# Features
Live flight map — Leaflet.js map of Washington State showing real-time low-altitude aircraft from the OpenSky Network API, color-coded by altitude with heatmap toggle
Overview dashboard — KPI cards, flights-by-county bar chart, commercial vs recreational pie chart, altitude histogram
Registrations page — Searchable/sortable/paginated table of all FAA-registered WA drones, with county bar chart and year-over-year trend line
Incidents table — Sortable, filterable incident report table with detail modal and CSV export
Tkinter control panel — Native desktop window with live KPI cards, navigation buttons, manual refresh, and a real-time activity log
Automatic data refresh — Background scheduler fetches new OpenSky data every 60 seconds
FAA data import — CLI tool to seed the database from FAA CSV files
Full test suite — Unit, integration, and view tests with pytest and coverage reporting
Docker support — Containerized deployment with Docker Compose

# Tech Stack

# Installation
Prerequisites

Python 3.11 or higher
pip
Git
(Optional) Docker Desktop for containerized deployment

Step 1. Clone the repository
Step 2. Create and activate a virtual environment
Step 3. Install Python dependencies
Step 4. Copy the environment variable template
Step 5. # 5. Create required directories

# Configuration
All settings are defined in config.py and loaded from a .env file via python-dotenv.
Create your .env file by copying .env.example

# Data Sources
OpenSky Network (Live Flight Data)
The OpenSky Network is a community-driven ADS-B receiver network that tracks aircraft in real time. The app calls the /api/states/all endpoint with Washington State's bounding box every 60 seconds and filters results to aircraft below 122 meters (the FAA's 400ft recreational drone ceiling).

No API key required for anonymous access (limited to ~10 requests/minute)
Register for free at opensky-network.org to increase rate limits
Set OPENSKY_USERNAME and OPENSKY_PASSWORD in your .env file

FAA Aircraft Registry (Registrations)
The FAA publishes the full US aircraft registry as a downloadable ZIP file updated monthly.
To download:

Visit FAA Releasable Aircraft Download
Download ReleasableAircraft.zip
Extract MASTER.txt to data/faa_csv/MASTER.txt
Run python import_data.py --regs-only

FAA Incident Data
Drone incident data can be sourced from ASIAS (Aviation Safety Information Analysis and Sharing) or compiled manually.
Expected CSV format (data/faa_csv/incidents.csv):
DATE,LOCATION,COUNTY,LATITUDE,LONGITUDE,DESCRIPTION,SEVERITY,REPORTED_BY
2024-01-10,Seattle,King,47.6062,-122.3321,Near miss with aircraft,Moderate,FAA
WA County Shapefiles (for geo resolution)
Used to resolve which county a lat/lon point falls in. Download from the WA State Geospatial Open Data Portal:

Search for "Washington State County Boundaries"
Download as Shapefile
Extract all files (.shp, .dbf, .prj, .shx) to data/shapefiles/


Note: County resolution is optional. If the shapefile is missing, flights will be stored with county = "Unknown" and the app will still work.




