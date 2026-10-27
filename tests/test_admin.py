import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient
from test_api import FakeService, answer, plan_query

from ecobici.admin import Admin, Source, sync
from ecobici.api import make_app
from ecobici.collector.sinks import LocalSink

OCTOBER = (date(2026, 10, 1), date(2026, 10, 31))
ALL_TIME = (date(2020, 1, 1), date(2030, 1, 1))


@pytest.fixture
def logs(tmp_path):
    """Two plans to a Photon place, one to an address, and two answers, from the real API."""
    app = make_app(
        FakeService(),
        feedback_sink=LocalSink(tmp_path / "feedback"),
        plan_sink=LocalSink(tmp_path / "plans"),
    )
    client = TestClient(app)
    first = plan_query()
    client.get("/v1/plan", params=first)
    client.get("/v1/plan", params=plan_query())
    client.get("/v1/plan", params=plan_query(to_kind="address", to_name="Calle 1"))
    client.post("/v1/feedback", json=answer(plan_id=first["plan_id"]))
    rating = answer(plan_id=first["plan_id"], kind="rating", useful=False, reason="far")
    client.post("/v1/feedback", json=rating | {"comment": "Lejos"})
    return tmp_path, first["plan_id"]


@pytest.fixture
def admin(logs):
    root, _ = logs
    return Admin(str(root / "plans"), str(root / "feedback"), cache=root / "cache")


def test_demand_counts_the_plans_and_the_ends(admin):
    d = admin.demand(*OCTOBER)
    assert d["per_day"] == [{"day": date(2026, 10, 7), "plans": 3}]
    # T0 is 15:00 UTC: 09:00 in Mexico City.
    assert d["per_hour"] == [{"hour": 9, "plans": 3}]
    ends = {(e["side"], e["kind"]): e["plans"] for e in d["ends"]}
    assert ends == {("from", "station"): 3, ("to", "photon"): 2, ("to", "address"): 1}
    assert d["pickups"] == [{"id": "O", "name": "O", "plans": 3}]
    assert admin.demand(date(2026, 11, 1), date(2026, 11, 30))["per_day"] == []


def test_places_lists_the_photon_picks(admin):
    [place] = admin.places(*OCTOBER)
    assert place["name"] == "Torre Reforma" and place["osm"] == "W123" and place["plans"] == 2


def test_answers_and_the_plan_list_join_on_the_plan_id(admin, logs):
    _, plan_id = logs
    a = admin.answers(*ALL_TIME)
    assert a["ratings"] == [{"useful": False, "reason": "far", "answers": 1}]
    assert a["comments"][0]["comment"] == "Lejos"
    rows = admin.plan_list(*OCTOBER, None, None, 10)
    assert len(rows) == 3
    [first] = [r for r in rows if r["plan_id"] == plan_id]
    assert first["found_dock"] == "yes" and first["useful"] is False
    assert len(admin.plan_list(*OCTOBER, "address", None, 10)) == 1
    assert admin.plan_list(*OCTOBER, None, "nope", 10) == []


def test_station_names_come_from_the_live_service(logs):
    root, _ = logs
    names = pl.DataFrame({"id": ["O"], "code": ["001"], "name": ["Origin"]})
    a = Admin(str(root / "plans"), str(root / "feedback"), cache=root / "c", stations=lambda: names)
    assert a.demand(*OCTOBER)["pickups"][0]["name"] == "Origin"


def test_empty_logs_give_empty_views(tmp_path):
    a = Admin(str(tmp_path / "plans"), str(tmp_path / "feedback"), cache=tmp_path / "cache")
    assert a.demand(*OCTOBER)["per_day"] == []
    assert a.places(*OCTOBER) == [] and a.plan_list(*OCTOBER, None, None, 5) == []
    assert a.sql("select count(*) from plans")["rows"] == [[0]]


def test_sql_reads_the_tables_only(admin):
    r = admin.sql("select count(*) as n from candidates")
    assert r == {"columns": ["n"], "rows": [[9]], "truncated": False}
    assert admin.sql("select * from range(1001)")["truncated"]
    for bad in ["drop table plans", "select 1; select 2", "insert into plans default values"]:
        with pytest.raises(ValueError):
            admin.sql(bad)
    with pytest.raises(Exception, match="disabled"):
        admin.sql(f"select * from read_text('{Path(__file__)}')")
    assert admin.sql("select count(*) from plans")["rows"] == [[3]]


class FakeS3:
    """list_objects_v2 and download_file over a dict of key -> (body, modified)."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, datetime]] = {}
        self.downloads = 0

    def get_paginator(self, name):
        s3 = self

        class Pages:
            def paginate(self, Bucket, Prefix):
                yield {
                    "Contents": [
                        {"Key": k, "Size": len(b), "LastModified": m}
                        for k, (b, m) in s3.objects.items()
                        if k.startswith(Prefix)
                    ]
                }

        return Pages()

    def download_file(self, bucket, key, path):
        self.downloads += 1
        Path(path).write_bytes(self.objects[key][0])


def body(**fields) -> bytes:
    return gzip.compress(json.dumps(fields).encode())


def test_sync_fetches_new_and_newer_files_and_drops_deleted_ones(tmp_path):
    s3 = FakeS3()
    src = Source(tmp_path / "copy", "bucket", "feedback")
    key = "feedback/2026/10/07/p_trip.json.gz"
    s3.objects[key] = (body(found_dock="yes"), datetime(2026, 10, 7, 15, tzinfo=UTC))
    s3.objects["raw/other.json.gz"] = (b"x", datetime(2026, 10, 7, tzinfo=UTC))
    assert sync(s3, src) == 1
    local = tmp_path / "copy/2026/10/07/p_trip.json.gz"
    assert local.exists() and not (tmp_path / "copy/other.json.gz").exists()
    assert sync(s3, src) == 0
    # A new answer with the same size replaces the old one.
    s3.objects[key] = (body(found_dock="no!"), datetime(2026, 10, 7, 16, tzinfo=UTC))
    assert sync(s3, src) == 1
    assert json.loads(gzip.decompress(local.read_bytes()))["found_dock"] == "no!"
    del s3.objects[key]
    sync(s3, src)
    assert not local.exists()


def test_admin_routes_exist_only_when_enabled(monkeypatch, tmp_path, admin):
    monkeypatch.delenv("ECOBICI_ADMIN", raising=False)
    off = TestClient(make_app(FakeService(), plan_sink=LocalSink(tmp_path)))
    assert off.get("/admin").status_code == 404
    assert off.get("/admin/api/demand").status_code == 404
    on = TestClient(make_app(FakeService(), plan_sink=LocalSink(tmp_path), admin=admin))
    page = on.get("/admin")
    assert page.status_code == 200 and "Ecobici admin" in page.text
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["cache-control"] == "no-store"
    demand = on.get("/admin/api/demand", params={"since": "2026-10-01", "until": "2026-10-31"})
    assert demand.json()["per_day"] == [{"day": "2026-10-07", "plans": 3}]
    assert on.get("/admin/api/status").json()["plans"] == 3
    assert on.post("/admin/api/sql", json={"sql": "drop table plans"}).status_code == 400
    ok = on.post("/admin/api/sql", json={"sql": "select 1 as one"})
    assert ok.json()["rows"] == [[1]]


def test_admin_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ECOBICI_ADMIN", raising=False)
    assert TestClient(make_app(FakeService())).get("/admin").status_code == 404
