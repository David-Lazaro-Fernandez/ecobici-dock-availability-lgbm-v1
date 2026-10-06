"""Dev-only station viewer.

    uv run streamlit run apps/station_viewer.py

Shows the live GBFS feed or any local capture (default ``raw/``, e.g. after
``aws s3 sync s3://BUCKET/raw raw``): a map coloured by label, a filterable table,
and, for local captures, one station's docks and bikes over time.
"""

from datetime import datetime
from pathlib import Path

import altair as alt
import polars as pl
import pydeck as pdk
import streamlit as st

from ecobici import config
from ecobici.collector.report import fetched_at
from ecobici.devtools import stations as data

# Status palette: labels are states, not series. Each also carries its name in the
# legend, tooltip and table, so colour never carries meaning alone.
LABEL_STYLE = {
    "available": ("Available", "#0ca30c"),
    "full": ("Full", "#d03b3b"),
    "unavailable": ("Unavailable", "#ec835a"),
    "stale": ("Stale", "#8a8a85"),
}
SERIES = {"docks_available": ("Free docks", "#2a78d6"), "bikes_available": ("Bikes", "#eb6834")}

st.set_page_config(page_title="Ecobici station viewer", layout="wide")


@st.cache_data(ttl=30, show_spinner="Fetching live feed…")
def live_snapshot() -> data.Snapshot:
    return data.snapshot_frame(
        data.fetch_live(config.STATION_INFORMATION_URL),
        data.fetch_live(config.STATION_STATUS_URL),
    )


@st.cache_data(show_spinner=False)
def local_snapshot(root: str, capture: str) -> data.Snapshot:
    info = data.latest_information(Path(root)) or data.fetch_live(config.STATION_INFORMATION_URL)
    return data.snapshot_frame(info, data.read_capture(Path(capture)))


@st.cache_data(show_spinner="Reading captures…")
def history(captures: tuple[str, ...], station_id: str) -> pl.DataFrame:
    return data.station_history([Path(c) for c in captures], station_id)


def hex_to_rgb(h: str) -> list[int]:
    return [int(h[i : i + 2], 16) for i in (1, 3, 5)]


def legend() -> str:
    dot = "<span style='color:{c};font-size:1.1em'>●</span> {n}"
    return " &nbsp; ".join(dot.format(c=c, n=n) for n, c in LABEL_STYLE.values())


# --- Source -----------------------------------------------------------------
st.sidebar.header("Source")
source = st.sidebar.radio("Data", ["Live feed", "Local captures"], label_visibility="collapsed")
captures: list[Path] = []

if source == "Live feed":
    if st.sidebar.button("Refresh"):
        live_snapshot.clear()
    snap = live_snapshot()
else:
    root = st.sidebar.text_input("Captures directory", "raw")
    captures = data.list_captures(Path(root))
    if not captures:
        st.info(f"No `station_status` captures under `{root}/station_status/`.")
        st.stop()
    times = [fetched_at(p).astimezone(config.LOCAL_TZ) for p in captures]
    idx = st.sidebar.select_slider(
        "Capture",
        options=range(len(captures)),
        value=len(captures) - 1,
        format_func=lambda i: f"{times[i]:%Y-%m-%d %H:%M}",
    )
    snap = local_snapshot(root, str(captures[idx]))
    st.sidebar.caption(
        f"{len(captures)} captures, {times[0]:%m-%d %H:%M} → {times[-1]:%m-%d %H:%M}"
    )

df = snap.stations
label_name = pl.col("label").replace_strict({k: n for k, (n, _) in LABEL_STYLE.items()})

# --- Filters (one row, above the views) -------------------------------------
f1, f2 = st.columns([2, 3])
labels = f1.multiselect(
    "Labels",
    list(LABEL_STYLE),
    default=list(LABEL_STYLE),
    format_func=lambda k: LABEL_STYLE[k][0],
)
query = f2.text_input("Search station (name or code)")
view = df.filter(pl.col("label").is_in(labels))
if query:
    q = query.lower()
    view = view.filter(
        pl.col("name").str.to_lowercase().str.contains(q, literal=True)
        | pl.col("short_name").str.contains(q, literal=True)
    )

# --- Headline numbers --------------------------------------------------------
updated = datetime.fromtimestamp(snap.feed_updated, config.LOCAL_TZ)
st.caption(f"Feed updated {updated:%Y-%m-%d %H:%M:%S} (CDMX) · {len(df)} stations")
cols = st.columns(len(LABEL_STYLE))
for col, (key, (name, _)) in zip(cols, LABEL_STYLE.items(), strict=True):
    n = df.filter(pl.col("label") == key).height
    col.metric(name, n, f"{n / len(df):.1%} of stations", delta_color="off")

# --- Map ---------------------------------------------------------------------
colors = {k: hex_to_rgb(c) for k, (_, c) in LABEL_STYLE.items()}
map_rows = [
    {**row, "color": colors[row["label"]]}
    for row in view.drop_nulls(["lat", "lon"])
    .with_columns(label_name=label_name, since=pl.col("minutes_since_report").round(0))
    .to_dicts()
]
st.markdown(legend(), unsafe_allow_html=True)
st.pydeck_chart(
    pdk.Deck(
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                map_rows,
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_radius=35,
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
            "html": "<b>{name}</b><br/>{label_name}<br/>Free docks {num_docks_available}"
            " · Bikes {num_bikes_available} · Capacity {capacity}"
            "<br/>Last report {since} min ago",
        },
        map_style=None,
    ),
    height=520,
)

# --- Table -------------------------------------------------------------------
st.subheader(f"Stations ({len(view)})")
table = (
    view.with_columns(label=label_name)
    .select(
        "short_name",
        "name",
        "label",
        "num_docks_available",
        "num_bikes_available",
        "capacity",
        "num_docks_disabled",
        "minutes_since_report",
    )
    .sort("num_docks_available")
)
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    column_config={
        "short_name": "Code",
        "name": "Name",
        "label": "Label",
        "num_docks_available": "Free docks",
        "num_bikes_available": "Bikes",
        "capacity": "Capacity",
        "num_docks_disabled": "Disabled docks",
        "minutes_since_report": st.column_config.NumberColumn("Min since report", format="%.0f"),
    },
)

# --- Station history (local captures only) -----------------------------------
st.subheader("Station history")
if not captures:
    st.caption("Switch the source to **Local captures** to see a station over time.")
    st.stop()

station_names = {
    r["station_id"]: f"{r['short_name']} · {r['name']}"
    for r in df.sort("short_name").select("station_id", "short_name", "name").to_dicts()
}
pick = st.selectbox("Station", list(station_names), format_func=station_names.get)
hist = history(tuple(str(c) for c in captures), pick)
if hist.is_empty():
    st.caption("This station does not appear in the captures.")
    st.stop()

long = hist.unpivot(
    on=list(SERIES), index=["time", "label"], variable_name="series", value_name="count"
).with_columns(pl.col("series").replace_strict({k: n for k, (n, _) in SERIES.items()}))
hover = alt.selection_point(fields=["time"], nearest=True, on="pointerover", empty=False)
base = alt.Chart(long).encode(
    x=alt.X("time:T", title=None),
    y=alt.Y("count:Q", title="Count"),
    color=alt.Color(
        "series:N",
        scale=alt.Scale(
            domain=[n for n, _ in SERIES.values()], range=[c for _, c in SERIES.values()]
        ),
        legend=alt.Legend(title=None, orient="top"),
    ),
)
lines = base.mark_line(strokeWidth=2)
points = (
    base.mark_point(size=64, filled=True)
    .encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[
            alt.Tooltip("time:T", title="Time", format="%Y-%m-%d %H:%M"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("count:Q", title="Count"),
            alt.Tooltip("label:N", title="Label"),
        ],
    )
    .add_params(hover)
)
rule = alt.Chart(long).mark_rule(color="#8a8a85").encode(x="time:T").transform_filter(hover)
st.altair_chart(alt.layer(lines, points, rule).properties(height=280), width="stretch")
