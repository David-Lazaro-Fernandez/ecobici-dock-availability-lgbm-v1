from ecobici import config


def test_capture_interval_resolves_shortest_horizon():
    shortest = min(config.HORIZONS_OWN_CAPTURE_MIN) * 60
    assert config.CAPTURE_INTERVAL_SECONDS * 2 <= shortest


def test_maxhalford_horizons_are_subset_of_own_capture():
    assert set(config.HORIZONS_MAXHALFORD_MIN) <= set(config.HORIZONS_OWN_CAPTURE_MIN)


def test_feed_urls_use_spanish_locale():
    assert config.STATION_STATUS_URL.endswith("/es/station_status.json")
