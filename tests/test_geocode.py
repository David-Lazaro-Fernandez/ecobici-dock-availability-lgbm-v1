from ecobici.recommender import geocode


class Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Session:
    def __init__(self, body):
        self.body, self.calls = body, []

    def get(self, url, params, headers, timeout):
        self.calls.append((params, headers))
        return Resp(self.body)


def test_viewbox_is_left_top_right_bottom_with_margin():
    assert geocode.viewbox([19.3, 19.5], [-99.2, -99.1], margin=0.01) == (
        "-99.21000000000001,19.51,-99.08999999999999,19.29"
    )


def test_search_is_bounded_and_identifies_itself():
    s = Session([{"display_name": "Reforma 222, Juárez", "lat": "19.4287", "lon": "-99.1613"}])
    got = geocode.search("  Reforma 222 ", "-99.2,19.5,-99.1,19.3", session=s)
    assert got == [geocode.Place("Reforma 222, Juárez", 19.4287, -99.1613)]
    params, headers = s.calls[0]
    assert params["q"] == "Reforma 222" and params["bounded"] == 1
    assert params["viewbox"] == "-99.2,19.5,-99.1,19.3"
    assert headers["User-Agent"] == geocode.USER_AGENT


def test_empty_query_makes_no_request():
    s = Session([])
    assert geocode.search("   ", "box", session=s) == [] and not s.calls
