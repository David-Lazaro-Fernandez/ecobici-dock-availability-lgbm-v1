"""The live service for the API and the dev viewer: recent captures from S3, the
predictions of the frozen models, and trip plans.

Use one instance per process. It is thread-safe: concurrent requests share one S3 fetch
and one prediction per capture.

AWS access uses the standard boto3 chain: the ``aws login`` session on a laptop
(``botocore[crt]``), or the instance role on AWS. No keys are stored.
"""

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from ecobici import config, live
from ecobici.collector.report import fetched_at
from ecobici.devtools import stations as gbfs
from ecobici.eval.model_report import trip_flow
from ecobici.ingest import captures as s3
from ecobici.ingest import trips as trip_ingest
from ecobici.recommender import plan as rp

S3_EVERY = timedelta(seconds=60)  # Captures arrive every 2 min.
S3_WINDOW = live.LOOKBACK + timedelta(minutes=5)
INFO_WINDOW = timedelta(days=2)  # station_information is captured once a day, at 06:00 UTC.
WEATHER_EVERY = timedelta(minutes=30)
RIDE_HISTORY = timedelta(days=365)
EMPTY_ARTIFACTS = Path("artifacts/empty")  # From: model_report --target empty --horizons 15


@dataclass(frozen=True)
class Live:
    """All stations at one capture, with their predictions (null if not predicted)."""

    captured_at: datetime
    stations: pl.DataFrame
    weather_missing: bool


class LiveService:
    def __init__(self, raw: Path = Path("raw"), use_s3: bool = True):
        self.raw = raw
        self.use_s3 = use_s3
        self.s3_error: str | None = None
        self._lock = threading.RLock()
        self._model: dict | None = None
        self._rides: pl.DataFrame | None = None
        self._fetched_at = datetime.min.replace(tzinfo=UTC)
        self._weather: tuple[datetime, pl.DataFrame] | None = None
        self._live: tuple[str, Live] | None = None

    # --- Loaded once -------------------------------------------------------------
    def model(self) -> dict:
        with self._lock:
            if self._model is None:
                files = live.model_files()
                self._model = {
                    "frozen": live.load_frozen(),
                    "files": files,
                    "saturated": live.saturated_by_horizon(files),
                    "flow": trip_flow(trip_ingest.DEFAULT_DIR, self.raw),
                }
                # Optional: the empty-station model exists only after its training run.
                h = (rp.EMPTY_HORIZON,)
                if (EMPTY_ARTIFACTS / f"lgbm_{h[0]}.txt").exists():
                    self._model["empty"] = {
                        "frozen": live.load_frozen(EMPTY_ARTIFACTS, h),
                        "saturated": live.saturated_by_horizon(files, h, target="empty"),
                    }
            return self._model

    def rides(self) -> pl.DataFrame:
        with self._lock:
            if self._rides is None:
                since = datetime.now(config.LOCAL_TZ) - RIDE_HISTORY
                codes = trip_ingest.station_code_map(self.information())
                self._rides = rp.ride_times(trip_ingest.DEFAULT_DIR, codes, since)
            return self._rides

    def information(self) -> dict:
        return gbfs.latest_information(self.raw) or gbfs.fetch_live(config.STATION_INFORMATION_URL)

    def weather(self) -> pl.DataFrame:
        with self._lock:
            now = datetime.now(UTC)
            if self._weather is None or now - self._weather[0] > WEATHER_EVERY:
                self._weather = (now, live.forecast_weather())
            return self._weather[1]

    @property
    def last_capture(self) -> datetime | None:
        """The capture time of the last computed prediction, or None. Does not block."""
        cached = self._live
        return cached[1].captured_at if cached else None

    # --- Refreshed ---------------------------------------------------------------
    def refresh(self, force: bool = False) -> None:
        """Get the recent captures from S3, at most once per S3_EVERY. If this fails,
        ``s3_error`` tells why and the service uses the captures in ``raw/``."""
        if not self.use_s3:
            return
        with self._lock:
            now = datetime.now(UTC)
            if not force and now - self._fetched_at < S3_EVERY:
                return
            self._fetched_at = now
            try:
                bucket = s3.bucket_from_env()
                s3.download_recent(bucket, "station_status", now - S3_WINDOW, self.raw)
                s3.download_recent(bucket, "station_information", now - INFO_WINDOW, self.raw)
                self.s3_error = None
            except SystemExit as e:  # From bucket_from_env.
                self.s3_error = str(e)
            except Exception as e:  # noqa: BLE001 - any AWS or network error
                self.s3_error = f"S3 fetch failed: {e}"

    def current(self) -> Live:
        """The predictions for the last capture. They are computed once per capture."""
        self.refresh()
        captures = gbfs.list_captures(self.raw)
        if not captures:
            raise LookupError("no captures yet")
        latest = captures[-1]
        with self._lock:
            if self._live and self._live[0] == latest.name:
                return self._live[1]
            at = fetched_at(latest)
            m, info, weather = self.model(), self.information(), self.weather()
            t0 = time.time()
            pred = live.predict(
                live.recent_captures(self.raw, at),
                info,
                m["files"],
                m["flow"],
                weather,
                m["saturated"],
                m["frozen"],
            )
            if "empty" in m:
                e = m["empty"]
                h = rp.EMPTY_HORIZON
                empty = live.predict(
                    live.recent_captures(self.raw, at),
                    info,
                    m["files"],
                    m["flow"],
                    weather,
                    e["saturated"],
                    e["frozen"],
                    target="empty",
                ).select("sid", pl.col(f"p_full_{h}").alias(f"p_empty_{h}"))
                pred = pred.join(empty, on="sid", how="left")
            snap = gbfs.snapshot_frame(info, gbfs.read_capture(latest)).stations
            stations = snap.join(
                pred.rename({"sid": "station_id"}).drop("t"), on="station_id", how="left"
            )
            hour = pl.lit(at).dt.truncate("1h")
            result = Live(at, stations, weather.filter(pl.col("time_utc") == hour).is_empty())
            self._live = (latest.name, result)
            self.predict_seconds = time.time() - t0
            return result

    def plan(
        self,
        start: tuple[float, float] | None,
        goal: tuple[float, float],
        start_station: str | None = None,
        radius_m: float = 500,
        failure_min: float = 7.5,
    ) -> dict:
        """Plan a trip from a point or a station to a point. Raise LookupError if there
        is no capture, if the station is unknown, or if no bike is near the start."""
        now = self.current()
        df = now.stations
        requested = None
        if start_station is not None:
            rows = df.filter(pl.col("station_id") == start_station)
            if rows.is_empty():
                raise LookupError(f"unknown station {start_station}")
            row = rows.row(0, named=True)
            if rp.has_bike(row):
                options = rows.with_columns(
                    walk_m=pl.lit(0.0), walk_min=pl.lit(0.0), p_empty=pl.lit(0.0)
                )
            else:
                requested = row
                options = rp.pickup_options(df, (row["lat"], row["lon"]))
        else:
            options = rp.pickup_options(df, start)
        if options.is_empty():
            raise LookupError("no station with a bike near the start")
        scored = []
        for opt in options.to_dicts():
            res = rp.plan(
                df,
                opt["station_id"],
                goal,
                self.rides(),
                radius_m,
                failure_min,
                depart_after_min=opt["walk_min"],
            )
            drop = res.filter(pl.col("rank") == 1)
            risk = (opt["p_empty"] or 0.0) * failure_min
            total = (
                opt["walk_min"] + risk + (drop["expected_min"][0] if drop.height else float("inf"))
            )
            scored.append(({**opt, "total_min": total}, res))
        scored.sort(key=lambda x: x[0]["total_min"])
        pickup, res = scored[0]
        return {
            "live": now,
            "pickup": pickup,
            "pickup_options": [o for o, _ in scored],
            "requested": requested,
            "candidates": res,
        }
