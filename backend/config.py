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