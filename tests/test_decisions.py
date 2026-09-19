"""What you resolve by hand has to survive the window closing."""
from pathlib import Path

from endslate.decisions import Decisions
from endslate.models import FileKind, Item, ParsedName, ScannedFile
from endslate.ui.resolver import Resolver


def movie_item(title, year=None, path=None):
    return Item(
        video=ScannedFile(
            path=Path(path or f"/library/Movies/{title}/{title}.mkv"), size=10, kind=FileKind.VIDEO
        ),
        parsed=ParsedName(title=title, year=year),
    )


def episode_item(show, season, number):
    return Item(
        video=ScannedFile(
            path=Path(f"/library/Shows/{show}/S{season:02}E{number:02}.mkv"), size=10, kind=FileKind.VIDEO
        ),
        is_tv=True,
        show_hint=show,
        parsed=ParsedName(title=show, season=season, episode=number),
    )


def test_a_decision_outlives_the_session(tmp_path):
    store = Decisions(tmp_path / "decisions.json")
    item = movie_item("Nerve")
    store.remember(item, {"title": "Nerve", "year": 2016, "tmdb_id": 328111})
    assert store.save()

    reopened = Decisions(tmp_path / "decisions.json")
    found = reopened.lookup(movie_item("Nerve"))
    assert found is not None
    assert (found.title, found.year, found.tmdb_id) == ("Nerve", 2016, 328111)


def test_a_decision_survives_the_file_being_renamed(tmp_path):
    store = Decisions(tmp_path / "decisions.json")
    store.remember(movie_item("Nerve"), {"title": "Nerve", "year": 2016, "tmdb_id": 328111})

    renamed = movie_item("Nerve", path="/library/Movies/Nerve (2016)/Nerve (2016).mkv")
    assert store.lookup(renamed) is not None


def test_a_decision_generalises_to_another_copy(tmp_path):
    store = Decisions(tmp_path / "decisions.json")
    store.remember(
        movie_item("INDIANA JONES RAIDERS LOST ARK"),
        {"title": "Raiders of the Lost Ark", "year": 1981, "tmdb_id": 85},
    )
    other = movie_item("Indiana Jones Raiders Lost Ark", path="/elsewhere/x.mkv")
    found = store.lookup(other)
    assert found is not None and found.tmdb_id == 85


def test_a_show_decision_covers_every_episode(tmp_path):
    store = Decisions(tmp_path / "decisions.json")
    store.remember(episode_item("Dark", 1, 1), {"title": "Dark", "year": 2017, "tmdb_id": 70523})
    assert store.lookup(episode_item("Dark", 3, 8)) is not None


def test_movies_and_shows_do_not_share_a_key(tmp_path):
    store = Decisions(tmp_path / "decisions.json")
    store.remember(movie_item("Dark"), {"title": "Dark Film", "year": 2020, "tmdb_id": 1})
    assert store.lookup(episode_item("Dark", 1, 1)) is None


def test_the_resolver_prefers_what_you_decided(tmp_path):
    from endslate.models import Confidence

    store = Decisions(tmp_path / "decisions.json")
    item = movie_item("Nerve")
    store.remember(item, {"title": "Nerve", "year": 2016, "tmdb_id": 328111})

    resolver = Resolver(None, store)
    fresh = movie_item("Nerve")
    resolver([fresh])
    assert fresh.confidence is Confidence.HIGH
    assert fresh.meta.year == 2016
    assert resolver.applied == 1


def test_the_resolver_leaves_unknown_titles_to_the_provider(tmp_path):
    from endslate.models import Confidence

    resolver = Resolver(None, Decisions(tmp_path / "decisions.json"))
    item = movie_item("Something Nobody Resolved")
    resolver([item])
    assert item.confidence is Confidence.LOW
    assert resolver.applied == 0


def test_forgetting_puts_it_back_in_needs_you(tmp_path):
    store = Decisions(tmp_path / "decisions.json")
    store.remember(movie_item("Nerve"), {"title": "Nerve", "year": 2016, "tmdb_id": 328111})
    assert store.forget_all() >= 1
    assert store.lookup(movie_item("Nerve")) is None


def test_a_corrupt_store_is_ignored_not_fatal(tmp_path):
    path = tmp_path / "decisions.json"
    path.write_text("{not json", encoding="utf-8")
    store = Decisions(path)
    assert len(store) == 0
    store.remember(movie_item("Nerve"), {"title": "Nerve", "year": 2016})
    assert store.save()
