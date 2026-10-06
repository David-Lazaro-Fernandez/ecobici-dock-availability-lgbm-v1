from conftest import station

from ecobici.config import STALE_AFTER_SECONDS
from ecobici.labels import StationState, classify, is_recommendable

NOW = 1_000_000


def test_free_dock_is_available():
    assert classify(station("1", docks=3), NOW) is StationState.AVAILABLE


def test_zero_docks_is_full():
    assert classify(station("1", docks=0), NOW) is StationState.FULL


def test_not_returning_is_unavailable_even_with_zero_docks():
    assert classify(station("1", docks=0, returning=0), NOW) is StationState.UNAVAILABLE


def test_not_installed_is_unavailable():
    assert classify(station("1", installed=0), NOW) is StationState.UNAVAILABLE


def test_out_of_service_wins_over_stale():
    old = NOW - STALE_AFTER_SECONDS - 1
    s = station("1", returning=0, last_reported=old)
    assert classify(s, NOW) is StationState.UNAVAILABLE


def test_old_report_is_stale_even_if_full():
    old = NOW - STALE_AFTER_SECONDS - 1
    assert classify(station("1", docks=0, last_reported=old), NOW) is StationState.STALE


def test_report_exactly_at_threshold_is_not_stale():
    edge = NOW - STALE_AFTER_SECONDS
    assert classify(station("1", last_reported=edge), NOW) is StationState.AVAILABLE


def test_missing_last_reported_is_stale():
    s = station("1")
    del s["last_reported"]
    assert classify(s, NOW) is StationState.STALE


def test_quiet_station_within_threshold_is_not_stale():
    # Stations report only on change: 45 min of silence is a quiet station, not a dead one.
    assert classify(station("1", docks=0, last_reported=NOW - 45 * 60), NOW) is StationState.FULL


def test_only_current_in_service_readings_are_recommendable():
    assert is_recommendable(StationState.AVAILABLE)
    assert is_recommendable(StationState.FULL)
    assert not is_recommendable(StationState.STALE)
    assert not is_recommendable(StationState.UNAVAILABLE)
