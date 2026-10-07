"""Live service behind the API (ecobici.api) and the dev viewer: latest captures from
S3, the frozen model's predictions for them, and trip plans.

One instance per process. It is thread-safe: FastAPI runs sync endpoints in a thread
pool, so concurrent requests share one S3 fetch and one prediction per capture.

AWS access comes from the standard boto3 chain: the ``aws login`` session locally
(``botocore[crt]``), or an instance role when deployed. No keys are stored.
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

S3_EVERY = timedelta(seconds=60)  # captures arrive every 2 min
S3_WINDOW = live.LOOKBACK + timedelta(minutes=5)  # what the lags need, with margin
INFO_WINDOW = timedelta(days=2)  # station_information is captured daily at 06:00 UTC
WEATHER_EVERY = timedelta(minutes=30)
RIDE_HISTORY = timedelta(days=365)


@dataclass(frozen=True)
class Live:
    """Every station at one capture, with its predictions (null when not predicted)."""

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
        """Capture time of the latest prediction computed, if any (never blocks)."""
        cached = self._live
        return cached[1].captured_at if cached else None

    # --- Refreshed ---------------------------------------------------------------
    def refresh(self, force: bool = False) -> None:
        """Fetch the recent captures from S3, at most once per S3_EVERY. On failure
        ``s3_error`` says why and the service keeps using what ``raw/`` has."""
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
            except SystemExit as e:  # bucket_from_env
                self.s3_error = str(e)
            except Exception as e:  # noqa: BLE001 - any AWS or network error
                self.s3_error = f"S3 fetch failed: {e}"

    def current(self) -> Live:
        """Predictions for the latest capture, computed once per capture."""
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
        """A trip plan from a point (or a station) to a point. Raises LookupError when
        there is no capture, no start station or no bike near the start."""
        now = self.current()
        df = now.stations
        requested = None
        if start_station is not None:
            rows = df.filter(pl.col("station_id") == start_station)
            if rows.is_empty():
                raise LookupError(f"unknown station {start_station}")
            row = rows.row(0, named=True)
            if rp.has_bike(row):
                pickup = {**row, "walk_m": 0.0, "walk_min": 0.0}
            else:
                # No bike to take there right now: walk to the nearest station that has one.
                requested = row
                pickup = rp.nearest_with_bike(df, (row["lat"], row["lon"]))
        else:
            pickup = rp.nearest_with_bike(df, start)
        if pickup is None:
            raise LookupError("no station with a bike near the start")
        res = rp.plan(df, pickup["station_id"], goal, self.rides(), radius_m, failure_min)
        return {"live": now, "pickup": pickup, "requested": requested, "candidates": res}
