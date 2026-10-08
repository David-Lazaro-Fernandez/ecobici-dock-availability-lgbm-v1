"""Dev-only page: live predictions of the frozen M6 model on the last S3 capture.

    uv run --extra api streamlit run apps/predictions.py   # Uses the `aws login` session.

On each load (at most once a minute), the page gets the last ~75 min of captures from S3
(``captures.download_recent``). Two tabs:

- **Plan a trip**: the stations near the destination, with P(free dock) at the arrival
  time of each one and the PRD expected-time score (``ecobici.recommender.plan``).
- **All stations**: P(full) of each station at one horizon.

The web app in ``web/`` replaces this page.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pydeck as pdk
import streamlit as st

from ecobici import config, live
from ecobici.collector.report import fetched_at
from ecobici.devtools import stations as gbfs
from ecobici.eval.baseline_report import HORIZONS
from ecobici.eval.model_report import trip_flow
from ecobici.ingest import captures as s3
from ecobici.ingest import trips as trip_ingest
from ecobici.recommender import geocode
from ecobici.recommender import plan as rp

RAW = Path("raw")
# One-hue ramp, light → dark. Each step has a contrast of 2:1 or more on the light map.
RAMP = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
FULL_BANDS = [(0.05, "< 5 %"), (0.20, "5–20 %"), (0.50, "20–50 %"), (1.01, "≥ 50 %")]
FREE_BANDS = [(0.50, "< 50 %"), (0.80, "50–80 %"), (0.95, "80–95 %"), (1.01, "≥ 95 %")]
NO_PREDICTION = ("No prediction (out of service or new)", "#c3c2b7")
ORIGIN, DESTINATION = "#eb6834", "#0b0b0b"
STATE = {"available": "Available", "full": "Full", "unavailable": "Unavailable", "stale": "Stale"}
# Warn if the last capture is older.
STALE_AFTER_MIN = 10
RIDE_HISTORY = timedelta(days=365)
S3_WINDOW = live.LOOKBACK + timedelta(minutes=5)
DEFAULT_START = "Paseo de la Reforma 222, Juárez"

st.set_page_config(page_title="Ecobici live predictions", layout="wide")


@st.cache_resource(show_spinner="Loading the frozen model…")
def model() -> dict:
    files = live.model_files()
    return {
        "frozen": live.load_frozen(),
        "files": files,
        "saturated": live.saturated_by_horizon(files),
        "flow": trip_flow(trip_ingest.DEFAULT_DIR, RAW),
    }


@st.cache_resource(show_spinner="Computing ride times from recent trips…")
def rides() -> pl.DataFrame:
    since = datetime.now(config.LOCAL_TZ) - RIDE_HISTORY
    return rp.ride_times(
        trip_ingest.DEFAULT_DIR, trip_ingest.station_code_map(information()), since
    )


@st.cache_data(ttl=1800, show_spinner="Fetching the weather forecast…")
def weather() -> pl.DataFrame:
    return live.forecast_weather()


@st.cache_data(ttl=600, show_spinner=False)
def information() -> dict:
    return gbfs.latest_information(RAW) or gbfs.fetch_live(config.STATION_INFORMATION_URL)


@st.cache_data(show_spinner="Predicting…", max_entries=4)
def predictions(latest: str) -> pl.DataFrame:
    """The cache key is the last capture name: a new capture gives a new prediction."""
    m = model()
    caps = live.recent_captures(RAW, fetched_at(Path(latest)))
    return live.predict(
        caps, information(), m["files"], m["flow"], weather(), m["saturated"], m["frozen"]
    )


@st.cache_data(ttl=60, show_spinner="Fetching the latest captures from S3…")
def fetch_recent() -> tuple[int, str | None]:
    """The number of new captures from S3, and an error message if S3 failed. If S3
    fails, the page uses the captures in ``raw/``."""
    now = datetime.now(UTC)
    try:
        bucket = s3.bucket_from_env()
        new, _ = s3.download_recent(bucket, "station_status", now - S3_WINDOW, RAW)
        # station_information is captured once a day, at 06:00 UTC.
        info_new, _ = s3.download_recent(
            bucket, "station_information", now - timedelta(days=2), RAW
        )
    # From bucket_from_env.
    except SystemExit as e:
        return 0, str(e)
    # Show any AWS error on the page.
    except Exception as e:  # noqa: BLE001
        return 0, (f"S3 fetch failed: {e}\n\nRun `aws login` again if the session expired.")
    if info_new:
        information.clear()
    return new, None


def band(p: float | None, bands: list[tuple[float, str]]) -> tuple[str, str]:
    if p is None:
        return NO_PREDICTION
    return next((name, color) for (top, name), color in zip(bands, RAMP, strict=True) if p < top)


def legend(title: str, bands: list[tuple[float, str]], extra=()) -> None:
    items = [*((n, c) for (_, n), c in zip(bands, RAMP, strict=True)), *extra, NO_PREDICTION]
    dots = " &nbsp; ".join(
        f"<span style='color:{c};font-size:1.2em'>●</span> {n}" for n, c in items
    )
    st.markdown(f"{title}: &nbsp; {dots}", unsafe_allow_html=True)


def rgb(h: str) -> list[int]:
    return [int(h[i : i + 2], 16) for i in (1, 3, 5)]


def fmt_pct(p: float | None) -> str:
    return "—" if p is None else f"{p:.0%}"


def station_label(r: dict) -> str:
    return f"{r['short_name']} · {r['name']}"


@st.cache_data(ttl=86400, show_spinner="Looking up the address…")
def find(query: str, box: str) -> list[geocode.Place]:
    return geocode.search(query, box)


def pick_point(col, role: str, key: str, box: str, ids: list[str], default_mode: str):
    """A station or a typed address: lat, lon, label and station_id (None for an
    address). None until the user picks something."""
    modes = ["Address", "Station"]
    mode = col.radio(
        role, modes, index=modes.index(default_mode), key=f"{key}_mode", horizontal=True
    )
    if mode == "Station":
        sid = col.selectbox(
            f"{role} station",
            ids,
            key=f"{key}_station",
            format_func=names.get,
            label_visibility="collapsed",
        )
        r = df.filter(pl.col("station_id") == sid).row(0, named=True)
        return {"lat": r["lat"], "lon": r["lon"], "label": names[sid], "station_id": sid}
    q = col.text_input(
        f"{role} address",
        key=f"{key}_q",
        placeholder="e.g. Paseo de la Reforma 222",
        label_visibility="collapsed",
    )
    if not q.strip():
        col.caption("Type an address, a place or a street corner.")
        return None
    try:
        places = find(q, box)
    # Show any lookup error on the page.
    except Exception as e:  # noqa: BLE001
        col.error(f"Address lookup failed: {e}")
        return None
    if not places:
        col.warning("No match inside the Ecobici area. Try adding the neighbourhood (colonia).")
        return None
    i = col.selectbox(
        f"{role} match",
        range(len(places)),
        key=f"{key}_match",
        format_func=lambda i: places[i].name,
        label_visibility="collapsed",
    )
    p = places[i]
    return {"lat": p.lat, "lon": p.lon, "label": p.name, "station_id": None}


# --- Source ------------------------------------------------------------------
st.sidebar.header("Data")
if st.sidebar.button("Refresh now", type="primary"):
    fetch_recent.clear()
new, s3_error = fetch_recent()
if s3_error:
    st.sidebar.error(s3_error)
else:
    st.sidebar.caption(f"S3: {new} new captures fetched (checked at most once a minute).")
captures = gbfs.list_captures(RAW)
if not captures:
    st.info("No captures under `raw/station_status/`, and S3 could not be reached.")
    st.stop()
latest = captures[-1]
at = fetched_at(latest)
age_min = (datetime.now(UTC) - at).total_seconds() / 60
st.sidebar.caption(f"{len(captures):,} captures in `raw/`")

# --- Predict -----------------------------------------------------------------
pred = predictions(str(latest))
snap = gbfs.snapshot_frame(information(), gbfs.read_capture(latest)).stations
df = snap.join(pred.rename({"sid": "station_id"}).drop("t"), on="station_id", how="left")
names = {r["station_id"]: station_label(r) for r in df.sort("short_name").to_dicts()}

st.title("Will there be a free dock when I arrive?")
local = at.astimezone(config.LOCAL_TZ)
st.caption(f"Latest capture {local:%Y-%m-%d %H:%M} CDMX ({age_min:.0f} min ago) · frozen M6 model")
if age_min > STALE_AFTER_MIN:
    st.warning(
        f"The latest capture is {age_min:.0f} min old, so predictions start at {local:%H:%M}, "
        "not now. Is the collector running?"
    )
if weather().filter(pl.col("time_utc") == pl.lit(at).dt.truncate("1h")).is_empty():
    st.warning("No weather forecast for this hour: the model runs without rain and temperature.")

trip_tab, all_tab = st.tabs(["Plan a trip", "All stations"])

# === Plan a trip ===============================================================
with trip_tab:
    ids = list(names)
    box = geocode.viewbox(df["lat"].to_list(), df["lon"].to_list())
    # Defaults: start at an address, end at the station most likely to be full now.
    if "dest_station" not in st.session_state:
        busiest = df.sort("p_full_15", descending=True, nulls_last=True).row(0, named=True)
        st.session_state.dest_station = busiest["station_id"]
        st.session_state.start_q = DEFAULT_START

    c1, c2 = st.columns(2)
    start = pick_point(c1, "Start", "start", box, ids, default_mode="Address")
    goal = pick_point(c2, "Destination", "dest", box, ids, default_mode="Station")
    with st.expander("Assumptions"):
        a1, a2 = st.columns(2)
        radius = a1.slider("Walking distance to the destination (m)", 200, 1000, 500, step=50)
        failure = a2.slider(
            "Failure cost: minutes lost if the station is full", 5.0, 10.0, 7.5, step=0.5
        )
        st.caption(
            f"Walking distance = straight line × {rp.DETOUR} at {rp.WALK_KMH} km/h. From an "
            "address, the bike comes from the nearest in-service station with one available. "
            f"Ride time = median of the last year's trips for that station pair (≥ "
            f"{rp.MIN_PAIR_TRIPS} trips), else straight line × {rp.DETOUR} at "
            f"{rp.BIKE_KMH:.0f} km/h. P(free dock) is interpolated between the 15 / 30 / 45 min "
            "models at each station's own arrival time. Expected time = ride + walk + P(full) × "
            "failure cost (PRD RF4). Addresses are looked up on OpenStreetMap (Nominatim)."
        )
    if start is None or goal is None:
        st.stop()

    if start["station_id"]:
        orig = df.filter(pl.col("station_id") == start["station_id"]).row(0, named=True)
        to_bike = None
    else:
        orig = rp.nearest_with_bike(df, (start["lat"], start["lon"]))
        if orig is None:
            st.warning("No in-service station with a bike near the start.")
            st.stop()
        to_bike = orig
    origin_id = orig["station_id"]
    if origin_id == goal["station_id"]:
        st.info("Pick a destination different from the start station.")
        st.stop()
    res = rp.plan(df, origin_id, (goal["lat"], goal["lon"]), rides(), radius, failure)
    ranked = res.filter(pl.col("rank").is_not_null()).sort("rank")
    first_walk = to_bike["walk_min"] if to_bike else 0.0

    # --- Recommendation --------------------------------------------------------
    if to_bike:
        st.markdown(
            f"**Take a bike at {station_label(orig)}**: {to_bike['walk_m']:.0f} m walk "
            f"(~{to_bike['walk_min']:.0f} min), {orig['num_bikes_available']} bikes now."
        )
    if ranked.is_empty():
        st.warning("No station near the destination can be recommended right now.")
    else:
        cols = st.columns(2)
        picks = [("Best", ranked.row(0, named=True))]
        if ranked.height > 1:
            picks.append(("Backup", ranked.row(1, named=True)))
        for col, (title, r) in zip(cols, picks, strict=False):
            arrive = local + timedelta(minutes=first_walk + r["ride_min"])
            col.metric(
                f"{title}: drop it at {station_label(r)}",
                f"{r['p_free']:.0%} chance of a free dock",
                f"~{first_walk + r['expected_min']:.0f} min expected, door to door",
                delta_color="off",
            )
            horizon_note = ""
            if r["outside_horizons"]:
                horizon_note = (
                    " Uses the 15-min model (shorter ride)."
                    if r["ride_min"] < HORIZONS[0]
                    else " Uses the 45-min model (longer ride)."
                )
            col.caption(
                f"Ride {r['ride_min']:.0f} min ({r['ride_source']}), arrive ~{arrive:%H:%M}, "
                f"then walk {r['walk_m']:.0f} m ({r['walk_min']:.0f} min). "
                f"Now: {r['num_docks_available']} free of {r['capacity']}.{horizon_note}"
            )

    # --- Map -------------------------------------------------------------------
    def tip(row: dict, role: str, **kw) -> dict:
        """All layers share one tooltip, so each point needs the same fields."""
        return {
            "role": role,
            "short_name": row.get("short_name", ""),
            "name": row.get("name", ""),
            "state": STATE.get(row.get("label"), "—"),
            "num_docks_available": row.get("num_docks_available", "—"),
            "capacity": row.get("capacity", "—"),
            "p_free_txt": "—",
            "ride_txt": "—",
            "walk_txt": "—",
            "lat": row["lat"],
            "lon": row["lon"],
            **kw,
        }

    cand = []
    for r in res.to_dicts():
        _, color = band(r["p_free"], FREE_BANDS)
        cand.append(
            tip(
                r,
                "Destination station · " if r["station_id"] == goal["station_id"] else "",
                color=rgb(color),
                p_free_txt=fmt_pct(r["p_free"]),
                ride_txt=f"{r['ride_min']:.0f} min",
                walk_txt=f"{r['walk_m']:.0f} m",
                tag={1: "1", 2: "2"}.get(r["rank"], ""),
            )
        )
    start_pt = tip(
        {**start, "name": start["label"], "short_name": "Start"}, "", color=rgb(ORIGIN), tag="S"
    )
    goal_pt = tip({**goal, "name": goal["label"], "short_name": "Destination"}, "")
    pickup = [tip(orig, "Bike pickup · ")] if to_bike else []
    best = ranked.row(0, named=True) if not ranked.is_empty() else None
    path = [[start["lon"], start["lat"]]]
    if to_bike:
        path.append([orig["lon"], orig["lat"]])
    if best:
        path.append([best["lon"], best["lat"]])

    def ring(points, color, px, width):
        return pdk.Layer(
            "ScatterplotLayer",
            points,
            get_position=["lon", "lat"],
            get_radius=40,
            radius_min_pixels=px,
            radius_max_pixels=px + 6,
            filled=False,
            stroked=True,
            get_line_color=rgb(color),
            line_width_min_pixels=width,
            pickable=True,
        )

    layers = [
        # The walking radius as a straight-line distance: radius / DETOUR.
        pdk.Layer(
            "ScatterplotLayer",
            [{"lon": goal["lon"], "lat": goal["lat"]}],
            get_position=["lon", "lat"],
            get_radius=radius / rp.DETOUR,
            filled=True,
            get_fill_color=[11, 11, 11, 18],
            stroked=True,
            get_line_color=[11, 11, 11, 120],
            line_width_min_pixels=1,
        ),
        pdk.Layer(
            "PathLayer",
            [{"path": path}],
            get_path="path",
            get_color=[82, 81, 78, 170],
            width_min_pixels=2,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            cand,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=30,
            radius_min_pixels=7,
            radius_max_pixels=14,
            stroked=True,
            get_line_color=[255, 255, 255],
            line_width_min_pixels=2,
            pickable=True,
        ),
        ring(pickup, ORIGIN, 11, 3),
        ring([goal_pt], DESTINATION, 12, 3),
        pdk.Layer(
            "ScatterplotLayer",
            [start_pt],
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=30,
            radius_min_pixels=8,
            radius_max_pixels=14,
            stroked=True,
            get_line_color=[255, 255, 255],
            line_width_min_pixels=2,
            pickable=True,
        ),
        pdk.Layer(
            "TextLayer",
            [*(c for c in cand if c["tag"]), start_pt],
            get_position=["lon", "lat"],
            get_text="tag",
            get_size=12,
            get_color=[255, 255, 255],
            font_weight=700,
        ),
    ]
    extra = [("Start", ORIGIN)]
    if to_bike:
        extra.append(("Bike pickup (orange ring)", ORIGIN))
    extra.append(("Destination (black ring)", DESTINATION))
    legend("P(free dock on arrival)", FREE_BANDS, extra=extra)
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(
                latitude=(start["lat"] + goal["lat"]) / 2,
                longitude=(start["lon"] + goal["lon"]) / 2,
                zoom=13,
            ),
            tooltip={
                "html": "<b>{short_name} · {name}</b><br/>{role}Now {state}: "
                "{num_docks_available} free of {capacity}<br/>P(free dock) {p_free_txt} · "
                "ride {ride_txt} · walk {walk_txt}",
            },
            map_style=None,
        ),
        height=480,
    )

    # --- Candidates table ------------------------------------------------------
    st.subheader(f"Stations within {radius} m of the destination ({res.height})")
    st.dataframe(
        res.with_columns(
            state=pl.col("label").replace_strict(STATE, default=pl.col("label")),
            pct_free=pl.col("p_free") * 100,
            arrive=pl.lit(local.replace(tzinfo=None))
            + pl.duration(seconds=((pl.col("ride_min") + first_walk) * 60).round(0).cast(pl.Int64)),
        ).select(
            "rank",
            "short_name",
            "name",
            "state",
            "num_docks_available",
            "capacity",
            "walk_m",
            "ride_min",
            "ride_source",
            "arrive",
            "pct_free",
            "expected_min",
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "rank": st.column_config.NumberColumn("Rank", help="Blank: not recommendable (RF7)"),
            "short_name": "Code",
            "name": "Name",
            "state": "Now",
            "num_docks_available": "Free docks now",
            "capacity": "Capacity",
            "walk_m": st.column_config.NumberColumn("Walk to destination (m)", format="%.0f"),
            "ride_min": st.column_config.NumberColumn("Ride (min)", format="%.0f"),
            "ride_source": "Ride time from",
            "arrive": st.column_config.DatetimeColumn("Arrive", format="HH:mm"),
            "pct_free": st.column_config.ProgressColumn(
                "P(free dock)", format="%.0f %%", min_value=0, max_value=100
            ),
            "expected_min": st.column_config.NumberColumn(
                "Expected (min)", format="%.1f", help="From the bike pickup: ride + walk + risk"
            ),
        },
    )

# === All stations ==============================================================
with all_tab:
    horizon = st.radio(
        "Arrival in", HORIZONS, index=0, format_func=lambda h: f"{h} min", horizontal=True
    )
    p = f"p_full_{horizon}"
    c = st.columns(4)
    c[0].metric(
        "Stations predicted", f"{df[p].is_not_null().sum():,}", f"of {len(df):,}", delta_color="off"
    )
    c[1].metric("Full now", f"{(df['label'] == 'full').sum():,}")
    c[2].metric(f"≥ 50 % full in {horizon} min", f"{(df[p] >= 0.5).sum():,}")
    c[3].metric(f"≥ 20 % full in {horizon} min", f"{(df[p] >= 0.2).sum():,}")

    f1, f2 = st.columns([2, 3])
    min_p = f1.slider(
        f"Only stations with P(full in {horizon} min) ≥", 0, 100, 0, step=5, format="%d %%"
    )
    query = f2.text_input("Search station (name or code)")
    view = df.filter(pl.col(p).fill_null(0) >= min_p / 100) if min_p else df
    if query:
        q = query.lower()
        view = view.filter(
            pl.col("name").str.to_lowercase().str.contains(q, literal=True)
            | pl.col("short_name").str.contains(q, literal=True)
        )

    rows = []
    for r in view.drop_nulls(["lat", "lon"]).to_dicts():
        _, color = band(r[p], FULL_BANDS)
        rows.append(
            {
                **r,
                "color": rgb(color),
                "state": STATE.get(r["label"], r["label"]),
                **{f"fmt_{h}": fmt_pct(r[f"p_full_{h}"]) for h in HORIZONS},
                # Draw the likeliest full on top.
                "order": -1.0 if r[p] is None else r[p],
            }
        )
    rows.sort(key=lambda r: r["order"])
    legend(f"P(full in {horizon} min)", FULL_BANDS)
    st.pydeck_chart(
        pdk.Deck(
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    rows,
                    get_position=["lon", "lat"],
                    get_fill_color="color",
                    get_radius=40,
                    radius_min_pixels=4,
                    radius_max_pixels=12,
                    stroked=True,
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=1,
                    pickable=True,
                )
            ],
            initial_view_state=pdk.ViewState(
                latitude=df["lat"].mean(), longitude=df["lon"].mean(), zoom=11.5
            ),
            tooltip={
                "html": "<b>{short_name} · {name}</b><br/>Now: {state}, {num_docks_available} "
                "free of {capacity}<br/>P(full) in 15 min {fmt_15} · 30 min {fmt_30} · "
                "45 min {fmt_45}",
            },
            map_style=None,
        ),
        height=540,
    )

    st.subheader(f"Stations ({len(view):,}), likeliest to be full first")
    st.dataframe(
        view.with_columns(
            state=pl.col("label").replace_strict(STATE, default=pl.col("label")),
            **{f"pct_{h}": pl.col(f"p_full_{h}") * 100 for h in HORIZONS},
        )
        .sort(p, descending=True, nulls_last=True)
        .select(
            "short_name",
            "name",
            "state",
            "num_docks_available",
            "capacity",
            *(f"pct_{h}" for h in HORIZONS),
            f"subgroup_{horizon}",
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "short_name": "Code",
            "name": "Name",
            "state": "Now",
            "num_docks_available": "Free docks",
            "capacity": "Capacity",
            **{
                f"pct_{h}": st.column_config.ProgressColumn(
                    f"P(full) {h} min", format="%.0f %%", min_value=0, max_value=100
                )
                for h in HORIZONS
            },
            f"subgroup_{horizon}": st.column_config.CheckboxColumn(
                "Saturated peak",
                help="Saturated station at weekday 08:30–10:30 arrival: subgroup calibration",
            ),
        },
    )

st.caption(
    "LightGBM per horizon with its VAL_FIT isotonic calibration; saturated stations at the "
    "weekday morning peak also get the static subgroup Platt (what the frozen model uses until "
    "~1.5 weeks of captured peaks exist). Out-of-service stations get no prediction. "
    "Stale stations are predicted but never recommended."
)
