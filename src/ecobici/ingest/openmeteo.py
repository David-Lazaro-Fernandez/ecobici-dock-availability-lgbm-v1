"""Open-Meteo historical forecasts for CDMX (M2; ENG_PLAN decision 2).

The same forecast product is used for training and serving, so there is no skew
between the two. One point at the system's centroid: the model grid (9–25 km) is
about the size of the Ecobici service area, so more points add little.

Data: CC BY 4.0, attribution required; the free tier is non-commercial only.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

API = "https://historical-forecast-api.open-meteo.com/v1/forecast"
VARIABLES = ("temperature_2m", "precipitation")
DEFAULT_PATH = Path("data/external/openmeteo/cdmx_hourly.parquet")
DEFAULT_START = date(2024, 4, 1)  # first MaxHalford month for CDMX


def fetch(
    start: date,
    end: date,
    latitude: float,
    longitude: float,
    session: requests.Session | None = None,
    chunk_days: int = 180,
) -> pd.DataFrame:
    """Hourly forecasts in UTC between ``start`` and ``end`` inclusive."""
    session = session or requests.Session()
    frames = []
    lo = start
    while lo <= end:
        hi = min(lo + timedelta(days=chunk_days - 1), end)
        resp = session.get(
            API,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": lo.isoformat(),
                "end_date": hi.isoformat(),
                "hourly": ",".join(VARIABLES),
                "timezone": "GMT",
            },
            timeout=60,
        )
        resp.raise_for_status()
        hourly = resp.json()["hourly"]
        frames.append(pd.DataFrame(hourly))
        lo = hi + timedelta(days=1)
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.rename(columns={"time": "time_utc"}).drop_duplicates("time_utc")


def main(argv: list[str] | None = None) -> int:
    from ecobici import config

    parser = argparse.ArgumentParser(description="Download Open-Meteo hourly history for CDMX")
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--out", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)

    lat, lon = config.WEATHER_POINT
    df = fetch(args.start, args.end, lat, lon)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    missing = df[list(VARIABLES)].isna().sum().to_dict()
    print(
        f"{len(df)} hours, {df['time_utc'].min():%Y-%m-%d} → {df['time_utc'].max():%Y-%m-%d}, "
        f"missing {missing} → {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
