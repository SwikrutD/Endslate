"""Talking to Jellyfin, against a fake server."""
import pytest

from endslate.jellyfin import JellyfinClient, JellyfinError


class Response:
    def __init__(self, payload=None, status=200):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class FakeServer:
    """Enough of Jellyfin to exercise the client."""

    def __init__(self, items=None, key="good", needs_user=False):
        self.items = items or []
        self.key = key
        self.needs_user = needs_user
        self.calls = []
        self.refreshed = 0

    def request(self, method, url, params=None, headers=None, timeout=None):
        params = params or {}
        headers = headers or {}
        self.calls.append((method, url))
        supplied = params.get("api_key") or headers.get("X-Emby-Token")
        if supplied != self.key:
            return Response({"error": "no"}, 401)
        if url.endswith("/System/Info"):
            return Response({"ServerName": "Basement", "Version": "10.9.6"})
        if url.endswith("/Library/Refresh"):
            self.refreshed += 1
            return Response(status=204)
        if url.endswith("/Users"):
            return Response([{"Id": "u1", "Policy": {"IsAdministrator": True}}])
        if "/Users/u1/Items" in url:
            return Response({"Items": self.items})
        if url.endswith("/Items"):
            if self.needs_user:
                return Response(status=400)
            return Response({"Items": self.items})
        return Response(status=404)


def client(server, key="good"):
    return JellyfinClient("http://localhost:8096", key, session=server)


def movie(name, tmdb=None, path="X"):
    row = {"Name": name, "Type": "Movie", "Path": path, "ProviderIds": {}}
    if tmdb:
        row["ProviderIds"] = {"Tmdb": str(tmdb)}
    return row


def test_a_good_key_names_the_server():
    assert "Basement" in client(FakeServer()).server_name()


def test_a_bad_key_says_so_plainly():
    with pytest.raises(JellyfinError, match="rejected that API key"):
        client(FakeServer(), key="wrong").server_name()


def test_an_unreachable_server_says_so_plainly():
    class Dead:
        def request(self, *args, **kwargs):
            raise OSError("connection refused")

    with pytest.raises(JellyfinError, match="Could not reach"):
        client(Dead()).server_name()


def test_refresh_is_triggered():
    server = FakeServer()
    assert client(server).refresh()
    assert server.refreshed == 1


def test_the_report_counts_what_jellyfin_could_not_identify():
    server = FakeServer(items=[
        movie("Fight Club", 550),
        movie("Dark", 70523),
        movie("ZTropic Ahasss", None, path="M:\\Media\\Movies\\ZTropic"),
    ])
    report = client(server).report()
    assert report.ok
    assert (report.total, report.identified, report.unidentified_count) == (3, 2, 1)
    assert report.unidentified[0]["name"] == "ZTropic Ahasss"
    assert "1 still have no provider id" in report.summary()


def test_a_fully_identified_library_says_so():
    server = FakeServer(items=[movie("Fight Club", 550)])
    report = client(server).report()
    assert "identified all 1" in report.summary()


def test_the_report_falls_back_to_the_per_user_endpoint():
    server = FakeServer(items=[movie("Fight Club", 550)], needs_user=True)
    report = client(server).report()
    assert report.ok and report.total == 1
    assert any("/Users/u1/Items" in url for _method, url in server.calls)


def test_no_key_means_no_report():
    report = JellyfinClient("http://localhost:8096", "", session=FakeServer()).report()
    assert not report.ok
    assert "API key" in report.summary()


def test_the_key_travels_in_the_header_as_well_as_the_query():
    server = FakeServer()
    jf = client(server)
    headers = jf._headers()
    assert headers["X-Emby-Token"] == "good"
    assert 'MediaBrowser Token="good"' == headers["Authorization"]


def test_entries_whose_file_is_gone_are_reported_as_stale(tmp_path):
    here = tmp_path / "Movies" / "Nerve (2016)" / "Nerve (2016).mp4"
    here.parent.mkdir(parents=True)
    here.write_bytes(b"x")
    gone = tmp_path / "Movies" / "Nerve" / "Nerve.mp4"
    server = FakeServer(items=[
        movie("Nerve", 328425, path=str(here)),
        movie("Nerve", 328425, path=str(gone)),
    ])
    report = client(server).report()
    assert report.stale_checked
    assert [row["path"] for row in report.stale] == [str(gone)]
    assert "no longer exist" in report.summary()
    assert "UNIQUE constraint" in report.detail()


def test_paths_that_mean_nothing_from_here_are_not_called_stale(tmp_path):
    server = FakeServer(items=[
        movie("Fight Club", 550, path=str(tmp_path / "elsewhere" / "a.mkv")),
        movie("Dark", 70523, path="Shows/Dark/Dark.mkv"),
    ])
    report = client(server).report()
    assert not report.stale_checked
    assert report.stale == []


def test_episodes_are_checked_for_staleness_but_not_counted_as_titles(tmp_path):
    video = tmp_path / "e.mkv"
    video.write_bytes(b"x")
    server = FakeServer(items=[
        {"Name": "Dark", "Type": "Series", "Path": str(tmp_path), "ProviderIds": {"Tmdb": "1"}},
        {"Name": "Secrets", "Type": "Episode", "Path": str(video), "ProviderIds": {}},
        {"Name": "Lies", "Type": "Episode", "Path": str(tmp_path / "gone.mkv"), "ProviderIds": {}},
    ])
    report = client(server).report()
    assert report.total == 1 and report.identified == 1
    assert [row["name"] for row in report.stale] == ["Lies"]
