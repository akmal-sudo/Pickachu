"""
Central config. Override any of these with environment variables so you
never have to hardcode secrets or hackathon-day values into the code.
"""

import os

# Keep this a SMALL real area (a neighborhood/district) — not a whole city.
# Large areas make the OSM download slow and the demo laggy.
PLACE_NAME = os.environ.get("PLACE_NAME", "Fort Kochi, Kerala, India")

# "drive" = road network for vehicles. Other options: "walk", "bike", "all".
NETWORK_TYPE = os.environ.get("NETWORK_TYPE", "drive")

# Radius in meters around PLACE_NAME to pull the road network for.
# Smaller = faster download + snappier demo. 1500-3000 is a good hackathon range.
DIST_METERS = int(os.environ.get("DIST_METERS", "2000"))

# ---------------------------------------------------------------------------
# Phase 4 — Safe zones (shelters/schools). Hardcoded per the phase plan —
# a real deployment would source this from a municipal shelter registry,
# but that data isn't uniformly published as an open API anywhere in India
# yet, so this is the "pluggable" stand-in: swap this list per city and
# nothing else in safezone.py needs to change.
#
# These are real, well-known landmark locations around Fort Kochi that make
# plausible shelter/muster points (schools, grounds, a community hall) —
# update to match whatever PLACE_NAME you set above.
# ---------------------------------------------------------------------------
SAFE_ZONES = [
    {"name": "Fort Kochi Government LP School", "lat": 9.9658, "lon": 76.2422},
    {"name": "St. Francis Church Grounds", "lat": 9.9670, "lon": 76.2400},
    {"name": "Fort Kochi Beach Community Hall", "lat": 9.9639, "lon": 76.2385},
    {"name": "Vasco da Gama Square Shelter", "lat": 9.9625, "lon": 76.2417},
]

# ---------------------------------------------------------------------------
# Phase 5 — Continuous live conditions. Interval in seconds between
# automatic flood/recede ticks when live mode is running.
# ---------------------------------------------------------------------------
LIVE_FLOOD_INTERVAL_SECONDS = float(os.environ.get("LIVE_FLOOD_INTERVAL_SECONDS", "0.2"))