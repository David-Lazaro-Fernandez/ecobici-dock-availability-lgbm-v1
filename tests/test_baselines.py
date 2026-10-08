from datetime import UTC, datetime, timedelta

import duckdb
import polars as pl
import pytest

from ecobici.eval import metrics
from ecobici.features import targets
from ecobici.models import baselines

# Tuesday 2025-03-04 15:00 UTC = 09:00 CDMX (a train month).
T0 = datetime(2025, 3, 4, 15, 0, tzinfo=UTC)


def snapshots(path, sequence, start=T0, step_min=15, ok=None):
    """One station 'A': ``sequence`` of full flags at 15-min snapshots."""
    ok = ok or [True] * len(sequence)
    rows = [
        {
            "station_id": "A",
            "committed_at_utc": start + timedelta(minutes=step_min * i),
            "is_installed": True,
            "is_returning": o,
            "num_docks_available": 0 if f else 5,
            "num_bikes_available": 20 if f else 15,
            "num_docks_disabled": 0,
            "capacity": 20,
            "latitude": 19.43,
            "longitude": -99.2,
        }
        for i, (f, o) in enumerate(zip(sequence, ok, strict=True))
    ]
    pl.DataFrame(rows).write_parquet(path)
    return path


def con_for(path, horizon=15):
    con = duckdb.connect()
    targets.load_snapshots(con, [path])
    targets.build_examples(con, horizon)
    return con


def test_examples_pair_each_snapshot_with_state_at_t_plus_h(tmp_path):
    con = con_for(snapshots(tmp_path / "s.parquet", [False, True, True, False]))
    rows = con.execute("SELECT full_now, y FROM ex_15 ORDER BY t").fetchall()
    # Last has no future.
    assert rows == [(False, True), (True, True), (True, False)]


def test_examples_skip_gaps_beyond_tolerance(tmp_path):
    # 30-min cadence: no snapshot within ±7.5 min of t + 15.
    con = con_for(snapshots(tmp_path / "s.parquet", [False, True, False], step_min=30))
    assert con.execute("SELECT count(*) FROM ex_15").fetchone()[0] == 0


def test_examples_drop_out_of_service_at_either_end(tmp_path):
    path = snapshots(tmp_path / "s.parquet", [True, True, True], ok=[True, False, True])
    con = con_for(path)
    assert con.execute("SELECT count(*) FROM ex_15").fetchone()[0] == 0


def test_examples_use_arrival_slot(tmp_path):
    con = con_for(snapshots(tmp_path / "s.parquet", [False, False]))
    slot, target_slot = con.execute("SELECT slot, target_slot FROM ex_15").fetchone()
    # 09:00 → arrival 09:15.
    assert (slot, target_slot) == (36, 37)


def test_baselines_fit_on_train_and_fall_back(tmp_path):
    # Alternating: persistence is always wrong.
    seq = [False, True] * 20
    con = con_for(snapshots(tmp_path / "s.parquet", seq))
    baselines.predict(con, 15)
    df = con.execute("SELECT * FROM pred_15").pl()
    assert df.filter(pl.col("full_now"))["p_persist"].unique().to_list() == [1.0]
    # Calibrated persistence learns that "full now" means "free next".
    assert df.filter(pl.col("full_now"))["p_persist_cal"].unique().to_list() == [0.0]
    assert df.filter(~pl.col("full_now"))["p_persist_cal"].unique().to_list() == [1.0]
    assert df["p_hist"].is_between(0, 1).all()


def test_metrics():
    df = pl.DataFrame(
        {"y": [True, False, False, False], "good": [0.9, 0.1, 0.1, 0.1], "flat": [0.25] * 4}
    )
    s = metrics.summarize(df, ["good", "flat"]).sort("model")
    flat, good = s.rows(named=True)
    assert flat["brier"] == pytest.approx(0.1875)
    assert good["brier"] == pytest.approx(0.01)
    assert metrics.skill(good["brier"], flat["brier"]) == pytest.approx(1 - 0.01 / 0.1875)
    rel = metrics.reliability(df, "good")
    assert rel["n"].sum() == 4 and rel["bin"].to_list() == [1, 9]


def test_baselines_refit_on_other_months(tmp_path):
    # March: alternating (full → free). April: persistent (full → full).
    march = snapshots(tmp_path / "m.parquet", [False, True] * 20)
    april = snapshots(
        tmp_path / "a.parquet", [True] * 40, start=datetime(2025, 4, 8, 15, 0, tzinfo=UTC)
    )
    con = duckdb.connect()
    targets.load_snapshots(con, [march, april])
    targets.build_examples(con, 15)
    baselines.predict(con, 15, refits={"_apr": ("2025-04",), "_both": ("2025-03", "2025-04")})
    full = con.execute("SELECT * FROM pred_15").pl().filter(pl.col("full_now"))
    assert full["p_persist_cal_apr"].unique().to_list() == [1.0]
    # TRAIN holds both months: 19 full→free in March vs 39 full→full in April.
    assert full["p_persist_cal"].unique().to_list() == full["p_persist_cal_both"].unique().to_list()
    assert full["p_persist_cal"].unique().item() == pytest.approx(39 / 58)
    assert {"p_hist", "p_hist_apr", "p_hist_both"} <= set(full.columns)
