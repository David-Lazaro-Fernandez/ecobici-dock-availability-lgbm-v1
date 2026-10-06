"""Project-wide constants agreed in docs/ENG_PLAN.md."""

from zoneinfo import ZoneInfo

GBFS_ROOT = "https://gbfs.mex.lyftbikes.com/gbfs/es"
STATION_STATUS_URL = f"{GBFS_ROOT}/station_status.json"
STATION_INFORMATION_URL = f"{GBFS_ROOT}/station_information.json"
SYSTEM_INFORMATION_URL = f"{GBFS_ROOT}/system_information.json"

# Storage is always UTC; features use local time (no DST in CDMX since 2022).
LOCAL_TZ = ZoneInfo("America/Mexico_City")

# Own capture cadence (ENG_PLAN finding 3).
CAPTURE_INTERVAL_SECONDS = 120

# A reading whose last_reported is older than this gets no label (finding 1).
STALE_AFTER_SECONDS = 30 * 60

# Horizons (minutes): MaxHalford supports the coarse ones, own capture all of them.
HORIZONS_MAXHALFORD_MIN = (15, 30, 45)
HORIZONS_OWN_CAPTURE_MIN = (10, 15, 20, 30, 45)

# Candidate stations and walking distance (RF2, finding 9).
WALK_RADIUS_M = 500
WALK_DETOUR_FACTOR = 1.3
