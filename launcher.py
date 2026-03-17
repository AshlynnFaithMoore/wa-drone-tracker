"""
launcher.py

The desktop entry point for the app. This is what the user runs.

It does three things:
1. Starts the Flask server in a background thread
2. Opens the dashboard in the user's default web browser
3. Shows a Tkinter control panel window with status info and controls

Why a background thread for Flask?
    Tkinter's mainloop() blocks the main thread — it runs an infinite loop
    waiting for GUI events. Flask's app.run() also blocks. To run both at the
    same time, we run Flask in a separate thread so neither blocks the other.

    We use daemon=True so the Flask thread automatically dies when the
    Tkinter window is closed (i.e., when the main thread exits).
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import time
import requests

from app import create_app
from config import FLASK_HOST, FLASK_PORT, REFRESH_INTERVAL_SECONDS

# Flask thread setup


flask_app = create_app()
BASE_URL = f"http://{FLASK_HOST}:{FLASK_PORT}"


def run_flask():
    """
    Runs the Flask development server.
    use_reloader=False is REQUIRED when running in a thread — the reloader
    spawns child processes, which breaks in a threaded context.
    """
    flask_app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)


# Start Flask in a background daemon thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()


# Tkinter GUI


class DroneTrackerApp(tk.Tk):
    """
    The main Tkinter window. Inherits from tk.Tk (the root window class).

    Layout:
    ┌─────────────────────────────────────┐
    │  Title bar                          │
    ├────────────────┬────────────────────┤
    │  Status panel  │  Quick stats       │
    │  (KPI cards)   │  (live counters)   │
    ├────────────────┴────────────────────┤
    │  Buttons: Open Dashboard, Open Map  │
    ├─────────────────────────────────────┤
    │  Log output (scrolled text)         │
    └─────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        self.title("WA Drone Tracker — Control Panel")
        self.geometry("600x500")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")  # Dark background

        # Track whether the Flask server is ready
        self.server_ready = False

        self._build_ui()

        # Wait for Flask to start, then begin auto-refreshing stats.
        # after() schedules a callback on the Tkinter event loop — safe for GUI updates.
        self.after(1500, self._check_server_ready)

    # UI construction

    def _build_ui(self):
        """Builds all the widgets in the window."""

        # --- Title ---
        title_lbl = tk.Label(
            self,
            text="🛸 Washington State Drone Tracker",
            font=("Helvetica", 16, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        title_lbl.pack(pady=(15, 5))

        #  Server status indicator
        self.status_var = tk.StringVar(value="⏳ Starting Flask server...")
        status_lbl = tk.Label(
            self, textvariable=self.status_var, font=("Helvetica", 10), fg="#fab387", bg="#1e1e2e"
        )
        status_lbl.pack()

        # KPI frame (live stat counters)
        kpi_frame = tk.Frame(self, bg="#313244", bd=1, relief="flat")
        kpi_frame.pack(fill="x", padx=20, pady=10)

        # Each KPI is a (label, variable) pair. StringVar lets us update
        # the label text from outside the widget.
        self.kpi_vars = {}
        kpis = [
            ("Total Flights", "total_flights"),
            ("Active (Last Hour)", "active_flights"),
            ("WA Registrations", "total_registrations"),
            ("Incidents", "total_incidents"),
        ]
        for i, (label, key) in enumerate(kpis):
            frame = tk.Frame(kpi_frame, bg="#313244")
            frame.grid(row=0, column=i, padx=15, pady=10, sticky="nsew")
            kpi_frame.columnconfigure(i, weight=1)

            val_var = tk.StringVar(value="—")
            self.kpi_vars[key] = val_var

            tk.Label(
                frame,
                textvariable=val_var,
                font=("Helvetica", 22, "bold"),
                fg="#89b4fa",
                bg="#313244",
            ).pack()
            tk.Label(frame, text=label, font=("Helvetica", 8), fg="#a6adc8", bg="#313244").pack()

        # Buttons
        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.pack(pady=5)

        btn_style = {
            "font": ("Helvetica", 10, "bold"),
            "relief": "flat",
            "padx": 15,
            "pady": 8,
            "cursor": "hand2",
        }

        tk.Button(
            btn_frame,
            text="Open Dashboard",
            bg="#89b4fa",
            fg="#1e1e2e",
            command=lambda: webbrowser.open(BASE_URL),
            **btn_style,
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            btn_frame,
            text="Open Map",
            bg="#a6e3a1",
            fg="#1e1e2e",
            command=lambda: webbrowser.open(f"{BASE_URL}/map"),
            **btn_style,
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            btn_frame,
            text="Refresh Now",
            bg="#fab387",
            fg="#1e1e2e",
            command=self._manual_refresh,
            **btn_style,
        ).grid(row=0, column=2, padx=5)

        # --- Refresh interval display ---
        interval_lbl = tk.Label(
            self,
            text=f"Auto-refresh every {REFRESH_INTERVAL_SECONDS}s",
            font=("Helvetica", 8),
            fg="#6c7086",
            bg="#1e1e2e",
        )
        interval_lbl.pack()

        # --- Log output ---
        log_frame = tk.Frame(self, bg="#1e1e2e")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        tk.Label(
            log_frame,
            text="Activity Log",
            font=("Helvetica", 9, "bold"),
            fg="#a6adc8",
            bg="#1e1e2e",
        ).pack(anchor="w")

        # ScrolledText is a Text widget with a built-in scrollbar
        self.log_box = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            state="disabled",
            bg="#11111b",
            fg="#cdd6f4",
            font=("Courier", 9),
            relief="flat",
        )
        self.log_box.pack(fill="both", expand=True)

        # Set up a logging handler that writes to the log_box widget
        self._setup_log_handler()

    # Logging bridge: Python logger → Tkinter text widget

    def _setup_log_handler(self):
        """
        Creates a custom logging.Handler that writes log messages into
        the Tkinter ScrolledText widget instead of just the console.
        """

        log_widget = self.log_box
        app_instance = self  # Reference for the after() call

        class TextHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record) + "\n"
                # Must schedule GUI updates on the main thread via after()
                app_instance.after(0, app_instance._append_log, msg)

        handler = TextHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)

    def _append_log(self, msg):
        """Appends a message to the log box. Must run on the main thread."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg)
        self.log_box.see("end")  # Auto-scroll to bottom
        self.log_box.configure(state="disabled")

    # Server readiness check

    def _check_server_ready(self):
        """
        Polls the Flask server until it responds. Once ready, updates
        the status label and starts the periodic KPI refresh.
        """
        try:
            requests.get(f"{BASE_URL}/api/stats", timeout=2)
            self.server_ready = True
            self.status_var.set("✅ Server running at " + BASE_URL)
            self._refresh_kpis()
            # Schedule KPI refresh every 30 seconds
            self.after(30_000, self._auto_refresh_kpis)
        except Exception:
            # Server not ready yet — try again in 1 second
            self.after(1000, self._check_server_ready)

    #
    # KPI refresh

    def _refresh_kpis(self):
        """Fetches /api/stats and updates the KPI counter labels."""
        try:
            r = requests.get(f"{BASE_URL}/api/stats", timeout=5)
            data = r.json()
            for key, var in self.kpi_vars.items():
                var.set(str(data.get(key, "—")))
        except Exception as e:
            logging.warning(f"KPI refresh failed: {e}")

    def _auto_refresh_kpis(self):
        """Called every 30 seconds to keep the KPI cards current."""
        self._refresh_kpis()
        self.after(30_000, self._auto_refresh_kpis)

    def _manual_refresh(self):
        """Called when the user clicks 'Refresh Now'."""
        logging.info("Manual refresh triggered")
        self._refresh_kpis()


# Entry point


if __name__ == "__main__":
    app = DroneTrackerApp()

    # Open the dashboard automatically on first launch
    # Small delay to let Flask finish starting
    app.after(2000, lambda: webbrowser.open(BASE_URL))

    # Start the Tkinter event loop — this blocks until the window is closed
    app.mainloop()
