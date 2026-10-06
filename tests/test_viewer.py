import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import station, status_payload

from ecobici.collector.capture import object_key
from ecobici.devtools import stations as data

T0 = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
APP = Path(__file__).parents[1] / "apps" / "station_viewer.py"


def info_payload():
    return {
        "last_updated": 1,
        "data": {
            "stations": [
                {
                    "station_id": "1",
                    "short_name": "710",
                    "name": "CE-710 Molino del Rey",
                    "lat": 19.41,
                    "lon": -99.19,
                    "capacity": 39,
                },
                {
                    "station_id": "2",
                    "short_name": "438",
                    "name": "CE-438 Adolfo Prieto",
                    "lat": 19.36,
                    "lon": -99.17,
                    "capacity": 23,
                },
            ]
        },
    }


def write(root, feed, ts, payload):
    path = root / object_key(feed, ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))


@pytest.fixture
def raw(tmp_path):
    write(tmp_path, "station_information", T0, info_payload())
    for i, docks in enumerate([3, 1, 0]):
        ts = T0 + timedelta(minutes=2 * i)
        lu = int(ts.timestamp())
        write(
            tmp_path,
            "station_status",
            ts,
            status_payload(
                [
                    station("1", docks=docks, last_reported=lu),
                    station("2", returning=0, last_reported=lu),
                ],
                last_updated=lu,
            ),
        )
    return tmp_path


def test_snapshot_frame_merges_and_labels(raw):
    status = data.read_capture(data.list_captures(raw)[-1])
    df = data.snapshot_frame(data.latest_information(raw), status)
    assert list(df["label"]) == ["full", "unavailable"]
    assert df.loc[0, "capacity"] == 39
    assert df.loc[0, "minutes_since_report"] == 0


def test_station_history_follows_one_station(raw):
    hist = data.station_history(data.list_captures(raw), "1")
    assert list(hist["docks_available"]) == [3, 1, 0]
    assert list(hist["label"]) == ["available", "available", "full"]
    assert str(hist["time"].iloc[0].tzinfo) == "America/Mexico_City"


def test_latest_information_missing(tmp_path):
    assert data.latest_information(tmp_path) is None


def test_app_renders_local_captures(raw):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()  # first run uses the live feed; switch to local before asserting
    at.sidebar.radio[0].set_value("Local captures").run()
    at.sidebar.text_input[0].set_value(str(raw)).run()
    assert not at.exception
    assert [m.value for m in at.metric] == ["0", "1", "1", "0"]
    assert at.dataframe[0].value.shape[0] == 2
