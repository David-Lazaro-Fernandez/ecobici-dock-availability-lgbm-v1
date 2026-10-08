from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest
import requests
from conftest import FakeResponse, FakeSession

from ecobici.ingest import trips

CDMX = ZoneInfo("America/Mexico_City")


class HtmlResponse(FakeResponse):
    def __init__(self, html):
        super().__init__(html.encode())
        self.text = html


@pytest.mark.parametrize(
    ("name", "month"),
    [
        ("2024-09.csv", "2024-09"),
        ("2025-10-1.csv", "2025-10"),
        ("ecobici_2022_10.csv", "2022-10"),
        ("datos_abiertos_2024_03-1-1.csv", "2024-03"),
        ("datosabiertos_2023_octubre.csv", "2023-10"),
        ("ecobici_2024_enero.csv", "2024-01"),
        ("public_data_web_2026-08_2.csv", "2026-08"),
        ("2010-02-feb.csv", "2010-02"),
        ("readme.csv", None),
    ],
)
def test_month_from_name(name, month):
    assert trips.month_from_name(name) == month


def test_discover_merges_pages_keeps_latest_upload_and_skips_old_system():
    en = (
        '<a href="/wp-content/uploads/2023/10/2022-08.csv">a</a>'
        '<a href="/wp-content/uploads/2022/06/2021-05.csv">old</a>'
        '<a href="/wp-content/uploads/2025/10/2025-10.csv">first upload</a>'
        '<a href="/wp-content/uploads/2025/11/2025-10-1.csv">re-upload</a>'
    )
    es = '<a href="/wp-content/uploads/2025/03/2025-02.csv">only on the Spanish page</a>'
    files = trips.discover(FakeSession(HtmlResponse(en), HtmlResponse(es)))
    assert [f.month for f in files] == ["2022-08", "2025-02", "2025-10"]
    assert files[-1].url.endswith("/2025/11/2025-10-1.csv")


def test_normalise_handles_both_header_styles_and_drops_personal_data(tmp_path):
    unquoted = tmp_path / "a.csv"
    unquoted.write_text(
        "Genero_Usuario,Edad_Usuario,Bici,Ciclo_Estacion_Retiro,Fecha_Retiro,Hora_Retiro,"
        'Ciclo_EstacionArribo,"Fecha Arribo",Hora_Arribo\n'
        "M,24,8015364,112,30/09/2022,23:22:32,64,01/10/2022,00:01:58\n"
    )
    quoted = tmp_path / "b.csv"
    quoted.write_text(
        '"Genero_Usuario","Edad_Usuario","Bici","Ciclo_Estacion_Retiro","Fecha_Retiro",'
        '"Hora_Retiro","Ciclo_EstacionArribo","Fecha_Arribo","Hora_Arribo"\n'
        '"F","30.0",5254487,"390-391","31/08/2024","23:55:44","064","01/09/2024","00:00:00"\n'
    )
    a, b = trips.normalise(unquoted), trips.normalise(quoted)

    for df in (a, b):
        assert df.columns == [
            "bike_id",
            "origin_code",
            "destination_code",
            "departed_at",
            "arrived_at",
            "duration_min",
        ]
    assert a["destination_code"][0] == b["destination_code"][0] == "064"
    assert b["origin_code"][0] == "390-391"
    assert a["departed_at"][0] == datetime(2022, 9, 30, 23, 22, 32, tzinfo=CDMX)
    assert a["duration_min"][0] == pytest.approx(39 + 26 / 60)


def test_normalise_short_header_two_digit_year_and_unpadded_hour(tmp_path):
    f = tmp_path / "c.csv"
    f.write_text(
        "\ufeffGenero_usuario,Edad_usuario,Bici,CE_retiro,Fecha_retiro,Hora_retiro,"
        "CE_arribo,Fecha_arribo,Hora_arribo\n"
        "F,24,14112,136,31/08/22,23:55:30,135,01/09/22,0:00:27\n",
        encoding="utf-8",
    )
    df = trips.normalise(f)
    assert df["origin_code"][0] == "136"
    assert df["departed_at"][0] == datetime(2022, 8, 31, 23, 55, 30, tzinfo=CDMX)
    assert df["arrived_at"][0] == datetime(2022, 9, 1, 0, 0, 27, tzinfo=CDMX)
    assert df["duration_min"][0] == pytest.approx(4 + 57 / 60)


def test_normalise_rejects_unknown_schema(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="missing columns"):
        trips.normalise(bad)


def test_station_code_map_covers_paired_stations():
    info = {
        "data": {
            "stations": [
                {"station_id": "1", "short_name": "064"},
                {"station_id": "2", "short_name": "390-391"},
            ]
        }
    }
    m = trips.station_code_map(info)
    assert m == {"064": "1", "390-391": "2", "390": "2", "391": "2"}


def test_quality_reports_mapping_and_plausible_durations(tmp_path):
    t = datetime(2025, 3, 4, 9, tzinfo=CDMX)
    pl.DataFrame(
        {
            "origin_code": ["064", "064", "1000"],
            "destination_code": ["390", "999", "064"],
            "departed_at": [t, t, t],
            "arrived_at": [t, t, None],
            "duration_min": [12.0, 0.5, None],
        }
    ).write_parquet(tmp_path / "2025-03.parquet")
    q = trips.quality(tmp_path, {"064": "1", "390": "2"}).row(0, named=True)
    assert q["month"] == "2025-03" and q["trips"] == 3
    assert q["destination_mapped"] == pytest.approx(2 / 3)
    assert q["plausible"] == pytest.approx(1 / 3)
    assert q["bad_time"] == pytest.approx(1 / 3)


class StreamResponse:
    """Streams ``body``; if ``cut_after`` is set, raises mid-stream like a stalled server."""

    def __init__(self, body: bytes, status=200, headers=None, cut_after=None):
        self.body, self.status_code = body, status
        self.headers = headers or {}
        self.cut_after = cut_after

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        if self.cut_after is None:
            yield self.body
            return
        yield self.body[: self.cut_after]
        raise requests.ConnectionError("Read timed out.")


def test_fetch_resumable_continues_from_bytes_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(trips.time, "sleep", lambda s: None)
    body = b"0123456789"
    session = FakeSession(
        StreamResponse(body, headers={"Content-Length": "10"}, cut_after=4),
        StreamResponse(body[4:], status=206, headers={"Content-Range": "bytes 4-9/10"}),
    )
    out = tmp_path / "f.csv"
    trips.fetch_resumable("http://x", out, session)
    assert out.read_bytes() == body
    assert session.last_kwargs["headers"] == {"Range": "bytes=4-"}


def test_fetch_resumable_restarts_if_server_ignores_range(tmp_path, monkeypatch):
    monkeypatch.setattr(trips.time, "sleep", lambda s: None)
    out = tmp_path / "f.csv"
    out.write_bytes(b"stale")
    session = FakeSession(StreamResponse(b"fresh-body", headers={"Content-Length": "10"}))
    trips.fetch_resumable("http://x", out, session)
    assert out.read_bytes() == b"fresh-body"


def test_fetch_resumable_retries_short_reads_then_gives_up(tmp_path, monkeypatch):
    monkeypatch.setattr(trips.time, "sleep", lambda s: None)
    short = [StreamResponse(b"abc", headers={"Content-Length": "10"}) for _ in range(2)]
    with pytest.raises(requests.ConnectionError, match="short read"):
        trips.fetch_resumable("http://x", tmp_path / "f.csv", FakeSession(*short), attempts=2)
