import polars as pl

from ecobici import bundle as bd


def test_bundle_round_trip_keeps_tables_and_int_horizons(tmp_path):
    b = bd.Bundle(
        stations=pl.DataFrame(
            {"sid": ["1", "2"], "lat": [19.4, 19.41], "lon": [-99.1, -99.2], "station": [0, 1]}
        ),
        flow=pl.DataFrame(
            {"station_id": ["1"], "slot": [36], "weekend": [False], "net_flow_mean": [1.5]}
        ),
        rides=pl.DataFrame(
            {"origin_id": ["1"], "destination_id": ["2"], "ride_min": [12.0], "trips": [40]}
        ),
        st_profile={
            "full": pl.DataFrame({"sid": ["1"], "st_full_rate": [0.1], "st_peak_full_rate": [0.2]}),
            "empty": pl.DataFrame(
                {"sid": ["1"], "st_full_rate": [0.3], "st_peak_full_rate": [0.4]}
            ),
        },
        saturated={"full": {15: ["1"], 30: []}, "empty": {15: ["2"]}},
    )
    b.save(tmp_path, {"built_at": "2026-10-07"})
    got = bd.load(tmp_path)
    assert got.stations.equals(b.stations) and got.rides.equals(b.rides) and got.flow.equals(b.flow)
    assert got.st_profile["empty"].equals(b.st_profile["empty"])
    assert got.saturated == {"full": {15: ["1"], 30: []}, "empty": {15: ["2"]}}
