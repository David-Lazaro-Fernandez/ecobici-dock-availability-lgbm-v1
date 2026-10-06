import gzip
import json
from datetime import UTC, datetime, timedelta

from conftest import station, status_payload

from ecobici.collector.capture import object_key
from ecobici.collector.report import build_report, format_report

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def write(root, ts, last_updated, stations):
    path = root / object_key("station_status", ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = status_payload(stations, last_updated=last_updated)
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))


def test_report_counts_coverage_gaps_duplicates_and_labels(tmp_path):
    lu = int(T0.timestamp())
    stations = [station("1", last_reported=lu), station("2", docks=0, last_reported=lu)]
    # 0, 2, 4 min, then a 10-min hole, then 14 min (same snapshot as 12 would be).
    for minute in (0, 2, 4):
        write(tmp_path, T0 + timedelta(minutes=minute), lu + minute * 60, stations)
    write(tmp_path, T0 + timedelta(minutes=14), lu + 4 * 60, stations)

    rep = build_report(tmp_path)

    assert rep.n_files == 4
    assert rep.expected == 8
    assert len(rep.gaps) == 1
    assert rep.duplicate_snapshots == 1
    assert rep.labels == {"available": 4, "full": 4}
    assert "50.0%" in format_report(rep)


def test_report_skips_unreadable_files(tmp_path):
    path = tmp_path / object_key("station_status", T0)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not gzip")
    assert build_report(tmp_path).unreadable == 1


def test_empty_report(tmp_path):
    assert format_report(build_report(tmp_path)) == "No captures found."


def test_report_buckets_silence_of_in_service_stations(tmp_path):
    lu = int(T0.timestamp())
    stations = [
        station("1", last_reported=lu),
        station("2", last_reported=lu - 45 * 60),
        station("3", last_reported=lu - 5 * 3600),
        station("4", returning=0, last_reported=lu - 99 * 86400),
    ]
    write(tmp_path, T0, lu, stations)

    rep = build_report(tmp_path)

    assert rep.silence == {"< 30 min": 1, "30-60 min": 1, "3-24 h": 1}
    assert rep.labels == {"available": 2, "stale": 1, "unavailable": 1}
    assert "30-60 min" in format_report(rep)
