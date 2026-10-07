"""Live predictions from our own GBFS captures, with the frozen M6 model.

A first cut of next_steps.md step 5, used by the dev viewer ``apps/predictions.py``.
Captures are turned into the same ``snap`` table as the MaxHalford history and go
through the same feature code (``model_matrix.build``), so serving cannot drift from
training:

- the station list, station profiles and saturated stations come from the MaxHalford
  months the model was trained on, exactly as in M6;
- lags read the captures of the last ~70 min;
- weather is Open-Meteo's live forecast, the serving side of the historical
  forecasts used in training.

Calibration: the global isotonic map, then the static VAL_FIT Platt on
saturated_peak rows. That is what the frozen ``p_lgbm_sub_roll`` does until the
captures hold enough labelled peaks for its weekly refit (~1.5 weeks).
"""

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import polars as pl
import requests

from ecobici import config
from ecobici.collector.report import fetched_at
from ecobici.devtools import stations as gbfs
from ecobici.eval.baseline_report import HORIZONS, is_saturated_peak, saturated_stations
from ecobici.eval.splits import TRAIN, VALIDATION
from ecobici.features import model_matrix, targets
from ecobici.ingest import maxhalford
from ecobici.models import lgbm

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
# Longest lag (60 min) plus its tolerance, with a little room.
LOOKBACK = timedelta(minutes=model_matrix.LAGS_MIN[-1] + model_matrix.LAG_TOLERANCE_MIN + 2)
MODEL_FILES = (*TRAIN, *VALIDATION)  # the months M6 was trained and calibrated on


@dataclass(frozen=True)
class Frozen:
    """One horizon's frozen artifacts (written by model_report)."""

    booster: lgb.Booster
    iso_x: np.ndarray
    iso_y: np.ndarray
    platt: lgbm.Platt

    def predict(self, X: np.ndarray, subgroup: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(p_lgbm, frozen model with the static subgroup map)."""
        # Same as IsotonicRegression(out_of_bounds="clip").predict.
        p = np.interp(self.booster.predict(X), self.iso_x, self.iso_y)
        q = p.copy()
        q[subgroup] = self.platt.predict(p[subgroup])
        return p, q


def load_frozen(artifacts: Path = Path("artifacts"), horizons=HORIZONS) -> dict[int, Frozen]:
    out = {}
    for h in horizons:
        iso = json.loads((artifacts / f"isotonic_{h}.json").read_text())
        platt = json.loads((artifacts / f"platt_sub_{h}.json").read_text())
        out[h] = Frozen(
            lgb.Booster(model_file=str(artifacts / f"lgbm_{h}.txt")),
            np.asarray(iso["x"]),
            np.asarray(iso["y"]),
            lgbm.Platt(**platt),
        )
    return out


def model_files(root: Path = maxhalford.DEFAULT_DIR) -> list[Path]:
    return [f for m in MODEL_FILES if (f := root / f"{m}.parquet").exists()]


def saturated_by_horizon(
    files: list[Path], horizons=HORIZONS, target: str = "full"
) -> dict[int, list[str]]:
    """M6's saturated stations per horizon (for ``empty``: often drained at the peak),
    recomputed from the TRAIN months (same SQL)."""
    con = duckdb.connect()
    targets.load_snapshots(con, [f for f in files if f.stem in TRAIN], target=target)
    out = {}
    for h in horizons:
        targets.build_examples(con, h)
        con.execute(
            f"CREATE OR REPLACE TEMP TABLE train_{h} AS SELECT * FROM ex_{h} "
            "WHERE month IN (SELECT unnest(?))",
            [list(TRAIN)],
        )
        out[h] = sorted(saturated_stations(con, h))
    return out


def recent_captures(root: Path, at: datetime | None = None) -> list[Path]:
    """station_status captures in (at − LOOKBACK, at]; ``at`` defaults to the latest."""
    files = gbfs.list_captures(root)
    if not files:
        return []
    at = at or fetched_at(files[-1])
    return [f for f in files if at - LOOKBACK < fetched_at(f) <= at]


def capture_rows(paths: list[Path], information: dict) -> pl.DataFrame:
    """Captures in the MaxHalford snapshot schema, so ``targets.load_snapshots`` reads
    them unchanged. Capacity and coordinates come from station_information."""
    info = pl.DataFrame(
        [
            {"station_id": s["station_id"], **{k: s.get(k) for k in ("capacity", "lat", "lon")}}
            for s in information["data"]["stations"]
        ],
        schema={
            "station_id": pl.String,
            "capacity": pl.Int64,
            "lat": pl.Float64,
            "lon": pl.Float64,
        },
    )
    frames = []
    for path in paths:
        status = gbfs.read_capture(path)
        frames.append(
            gbfs.frame(status["data"]["stations"], gbfs.STATUS_SCHEMA).with_columns(
                committed_at_utc=pl.lit(fetched_at(path)).cast(pl.Datetime("us", "UTC"))
            )
        )
    return (
        pl.concat(frames)
        .join(info, on="station_id", how="inner")
        .select(
            "station_id",
            "committed_at_utc",
            pl.col("is_installed").cast(pl.Boolean),
            pl.col("is_returning").cast(pl.Boolean),
            "num_docks_available",
            "num_bikes_available",
            "num_docks_disabled",
            "capacity",
            pl.col("lat").alias("latitude"),
            pl.col("lon").alias("longitude"),
        )
    )


def forecast_weather(
    point: tuple[float, float] = config.WEATHER_POINT, session: requests.Session | None = None
) -> pl.DataFrame:
    """Hourly temperature and precipitation for yesterday → tomorrow, in UTC."""
    lat, lon = point
    resp = (session or requests).get(
        FORECAST_API,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation",
            "timezone": "GMT",
            "past_days": 1,
            "forecast_days": 2,
        },
        timeout=20,
    )
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    # JSON numbers may mix ints and floats (or be null) within a column.
    return pl.DataFrame(
        {k: hourly[k] for k in ("time", "temperature_2m", "precipitation")},
        schema={"time": pl.String, "temperature_2m": pl.Float64, "precipitation": pl.Float64},
        strict=False,
    ).select(
        "temperature_2m",
        "precipitation",
        time_utc=pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M", time_zone="UTC"),
    )


def predict(
    captures: list[Path],
    information: dict,
    history_files: list[Path],
    flow: pl.DataFrame,
    weather: pl.DataFrame,
    saturated: dict[int, list[str]],
    frozen: dict[int, Frozen],
    duckdb_memory: str = "6GB",
    target: str = "full",
) -> pl.DataFrame:
    """P(full at t + h) for every in-service station at the latest capture t.

    One row per station: ``sid``, ``t``, and per horizon ``p_full_{h}`` (frozen model),
    ``p_lgbm_{h}`` (without the subgroup map) and ``subgroup_{h}`` (saturated_peak).
    """
    if not captures:
        raise ValueError("no captures")
    at = fetched_at(captures[-1])
    con = duckdb.connect(config={"memory_limit": duckdb_memory})
    with tempfile.TemporaryDirectory() as tmp:
        # The name keeps it out of MODEL_FILES, so it never feeds the station list.
        live = Path(tmp) / f"live_{at:%Y-%m}.parquet"
        capture_rows(captures, information).write_parquet(live)
        targets.load_snapshots(con, [*history_files, live], target=target)
    model_matrix.prepare_shared(con, flow, weather, station_files=MODEL_FILES)
    month = at.astimezone(config.LOCAL_TZ).strftime("%Y-%m")

    out = None
    for h, model in frozen.items():
        now = targets.build_now(con, h, at)
        feat = model_matrix.build(con, h, source=now)
        X, _, meta = lgbm.matrix(con, feat, (month,), extra=["t"])
        sub = meta.select(is_saturated_peak(saturated[h])).to_series().to_numpy()
        p, q = model.predict(X, sub)
        part = meta.select("sid", "t").with_columns(
            **{
                f"p_full_{h}": pl.Series(q),
                f"p_lgbm_{h}": pl.Series(p),
                f"subgroup_{h}": pl.Series(sub),
            }
        )
        out = part if out is None else out.join(part, on=["sid", "t"], how="full", coalesce=True)
    return out
