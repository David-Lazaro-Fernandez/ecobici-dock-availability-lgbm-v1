from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest
from conftest import FakeResponse, FakeSession

from ecobici.ingest import maxhalford as mh
from ecobici.ingest import openmeteo as om


class JsonResponse(FakeResponse):
    def __init__(self, payload):
        super().__init__(b"")
        self.payload = payload

    def json(self):
        return self.payload


def test_remote_file_month_name():
    assert mh.RemoteFile("mexico-city/ecobici/2025/Mar.parquet", 1).month == "2025-03"


def test_list_remote_follows_pages_and_sorts():
    session = FakeSession(
        JsonResponse(
            {"items": [{"name": f"{mh.PREFIX}2025/Feb.parquet", "size": "2"}], "nextPageToken": "t"}
        ),
        JsonResponse({"items": [{"name": f"{mh.PREFIX}2024/Sep.parquet", "size": "1"}]}),
    )
    assert [f.month for f in mh.list_remote(session)] == ["2024-09", "2025-02"]


def write_month(root, start, gaps_min):
    """One parquet with a snapshot of two stations at each cumulative gap."""
    times, t = [start], start
    for g in gaps_min:
        t = t + timedelta(minutes=g)
        times.append(t)
    rows = [{"station_id": s, "committed_at_utc": ts} for ts in times for s in ("1", "2")]
    pl.DataFrame(rows).write_parquet(root / f"{start:%Y-%m}.parquet")


def test_month_diagnostics_counts_covered_time(tmp_path):
    start = datetime(2025, 2, 1, tzinfo=UTC)
    # 14 days at 15 min, then one 2-day hole, then 15-min snapshots to the end.
    steady = [15] * (14 * 96)
    write_month(tmp_path, start, steady + [2 * 24 * 60] + [15] * (12 * 96 - 1))

    (row,) = mh.month_diagnostics(tmp_path)

    assert row["month"] == "2025-02"
    assert row["median_gap_min"] == 15
    assert row["gaps_over_1h"] == 1
    assert row["covered_days"] == pytest.approx(26, abs=0.1)
    assert row["healthy"] is True
    assert "Healthy months" in mh.format_diagnostics([row])


def test_openmeteo_fetch_chunks_and_parses_utc():
    def hourly(day):
        return {
            "hourly": {
                "time": [f"{day}T00:00", f"{day}T01:00"],
                "temperature_2m": [15.0, 14.5],
                "precipitation": [0.0, 1.2],
            }
        }

    session = FakeSession(JsonResponse(hourly("2025-01-01")), JsonResponse(hourly("2025-01-03")))
    df = om.fetch(date(2025, 1, 1), date(2025, 1, 3), 19.4, -99.2, session, chunk_days=2)

    assert session.calls == 2
    assert len(df) == 4
    assert df.schema["time_utc"] == pl.Datetime("us", "UTC")
    assert df.columns == ["time_utc", "temperature_2m", "precipitation"]
