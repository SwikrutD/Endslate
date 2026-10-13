"""The window builds, every screen renders, and the review list filters. Skipped without Qt."""
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")

from endslate.planner import Options, build_plan
from endslate.presets import builtin
from endslate.scanner import scan


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    import endslate.config as config_mod

    monkeypatch.setattr(config_mod, "app_dir", lambda: tmp_path)
    from endslate.ui.app import MainWindow

    made = MainWindow()
    yield made
    # Left alive, every window from every earlier test is restyled on each
    # theme change, and the suite slows with each one.
    from PySide6.QtCore import QCoreApplication, QEvent

    made.close()
    made.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_every_screen_renders(window, qapp):
    for key in ("library", "review", "apply", "history", "settings"):
        window.go_to(key)
        qapp.processEvents()
        assert window.pages.currentWidget() is window.page_map[key]


def test_the_template_preview_shows_real_filenames(window, qapp):
    window.preview_templates()
    text = window.settings_page.preview.toPlainText()
    assert "Fight Club (1999).mkv" in text
    assert "The 100 (2014) S01E04 Murphy's Law.mkv" in text


def test_choosing_a_preset_changes_the_preview(window, qapp):
    window.library_page.select_preset("Plex")
    qapp.processEvents()
    assert "s01e04" in window.settings_page.preview.toPlainText()


def test_both_themes_apply_without_error(window, qapp):
    from endslate.ui import theme

    for mode in ("dark", "light", "system"):
        window.set_theme(mode)
        qapp.processEvents()
    assert theme.active_mode() in ("dark", "light")


def test_review_fills_from_a_plan_and_filters(window, qapp, library):
    plan = build_plan(scan(library), builtin("Jellyfin"), Options())
    window.plan = plan
    window.review_page.set_plan(plan)
    qapp.processEvents()

    assert window.review_page.tiles["planned"].value.text() != "0"
    assert window.review_page.model.rowCount() > 0

    window.review_page.search.setText("fight club")
    qapp.processEvents()
    assert window.review_page.proxy.rowCount() == 1

    window.review_page.search.setText("")
    window.review_page.set_filter("junk")
    qapp.processEvents()
    assert all(e.bucket.value == "junk" for e in window.review_page.model.entries)


def test_clearing_the_plan_leaves_an_explanation(window, qapp, library):
    plan = build_plan(scan(library), builtin("Jellyfin"), Options())
    window.review_page.set_plan(plan)
    window.review_page.set_plan_cleared()
    qapp.processEvents()
    assert window.review_page.stack.currentWidget() is window.review_page.empty
    assert "Scan again" in window.review_page.empty.body.text()


def test_the_row_delegate_paints_without_crashing(window, qapp, library):
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem

    plan = build_plan(scan(library), builtin("Jellyfin"), Options())
    window.review_page.set_plan(plan)
    qapp.processEvents()

    view = window.review_page.table
    delegate = view.itemDelegate()
    pixmap = QPixmap(900, 64)
    painter = QPainter(pixmap)
    for row in range(min(6, window.review_page.proxy.rowCount())):
        option = QStyleOptionViewItem()
        option.rect = pixmap.rect()
        delegate.paint(painter, option, window.review_page.proxy.index(row, 0))
    painter.end()


def test_the_resolve_dialog_opens_with_candidates(qapp, tmp_path, monkeypatch):
    """It crashed on open: the candidate list touched a button built after it."""
    import endslate.config as config_mod

    monkeypatch.setattr(config_mod, "app_dir", lambda: tmp_path)
    from endslate.models import Candidate, FileKind, Item, ParsedName, ScannedFile
    from endslate.ui.dialogs import ResolveDialog

    item = Item(
        video=ScannedFile(path=Path("/library/Movies/The Witch/The Witch.mkv"), size=1, kind=FileKind.VIDEO),
        parsed=ParsedName(title="The Witch", year=2015),
    )
    item.candidates = [
        Candidate(title="The Witch", year=2015, tmdb_id=1, overview="A farm.", score=1.15),
        Candidate(title="The Witch", year=2016, tmdb_id=2, overview="Another.", score=1.05),
    ]
    dialog = ResolveDialog(item)
    qapp.processEvents()
    assert dialog.results.count() == 2
    assert dialog.confirm.isEnabled()

    dialog.results.setCurrentRow(1)
    dialog._accept_selected()
    assert dialog.result_meta == {"title": "The Witch", "year": 2016, "tmdb_id": 2}


def test_the_resolve_dialog_opens_with_nothing_to_show(qapp, tmp_path, monkeypatch):
    import endslate.config as config_mod

    monkeypatch.setattr(config_mod, "app_dir", lambda: tmp_path)
    from endslate.models import FileKind, Item, ParsedName, ScannedFile
    from endslate.ui.dialogs import ResolveDialog

    item = Item(
        video=ScannedFile(path=Path("/library/Movies/Nerve/Nerve.mp4"), size=1, kind=FileKind.VIDEO),
        parsed=ParsedName(title="Nerve"),
    )
    dialog = ResolveDialog(item)
    qapp.processEvents()
    assert not dialog.confirm.isEnabled()
    assert not dialog.empty.isHidden() and dialog.results.isHidden()


@pytest.mark.parametrize("point_size", [9, 11, 13])
def test_cards_never_overlap_their_own_text(qapp, point_size):
    """The preset cards collided with themselves wherever the system font was larger."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QWidget

    from endslate.ui import theme
    from endslate.ui.widgets import PresetCard, StatTile

    original = qapp.font()
    qapp.setFont(QFont(original.family(), point_size))
    theme.apply_theme(qapp, "dark")
    try:
        holder = QWidget()
        holder.resize(430, 460)
        card = PresetCard(
            "Jellyfin",
            "Jellyfin's documented layout. Folder per movie, Season 01 subfolders.",
            "Fight Club (1999)\\Fight Club (1999).mkv\nDark (2017) S01E02 Lies.mkv",
            holder,
        )
        card.resize(420, card.sizeHint().height())
        tile = StatTile("planned", "Already correct", "green", holder)
        tile.resize(200, tile.sizeHint().height())
        holder.show()
        qapp.processEvents()

        assert card.title.geometry().bottom() <= card.description.geometry().top()
        assert card.description.geometry().bottom() <= card.examples[0].geometry().top()
        assert card.examples[0].geometry().bottom() <= card.examples[1].geometry().top()
        assert card.examples[1].geometry().bottom() <= card.height()
        assert tile.value.geometry().bottom() <= tile.caption.geometry().top()
        assert tile.caption.geometry().bottom() <= tile.height()
    finally:
        qapp.setFont(original)
        theme.apply_theme(qapp, "dark")


def test_the_duplicates_view_offers_a_way_out(window, qapp, tmp_path):
    from endslate.models import Bucket

    root = tmp_path / "Dupes"
    for folder, size in (("A Film", 400), ("A Film 2011", 900)):
        path = root / "Movies" / folder
        path.mkdir(parents=True)
        (path / "A Film 2011.mkv").write_bytes(b"x" * size)

    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    window.plan = plan
    window.review_page.set_plan(plan)
    window.review_page.set_filter("duplicate")
    qapp.processEvents()

    assert not window.review_page.duplicate_bar.isHidden()
    assert not window.review_page.keep_button.isHidden()

    window.keep_largest_duplicates()
    qapp.processEvents()
    assert not window.plan.by_bucket(Bucket.DUPLICATE)
    assert window.review_page.tiles["duplicate"].value.text() == "0"


def test_the_tvdb_key_is_saved_with_the_settings(window, qapp):
    window.settings_page.tvdb_key.setText("a-tvdb-key")
    window.settings_page.tvdb_pin.setText("1234")
    window.save_settings()
    from endslate.config import load_config

    config = load_config()
    assert config.tvdb_api_key == "a-tvdb-key" and config.tvdb_pin == "1234"
    assert window.tvdb() is not None


def test_a_refused_apply_keeps_the_plan(window, qapp, library):
    """Preflight refused, nothing moved, and the review was thrown away anyway."""
    from endslate.executor import Problem, Result

    plan = build_plan(scan(library), builtin("Jellyfin"), Options())
    window.plan = plan
    window.review_page.set_plan(plan)
    window._apply_done(Result(failures=[Problem(library, "target already exists")]))
    qapp.processEvents()
    assert window.plan is plan
    assert window.review_page.plan is plan
    assert "Nothing was moved" in window.apply_page.result.text.text()


def test_a_second_scan_waits_for_the_first(window, qapp, tmp_path):
    """F5 during a scan started another job over the running one."""
    class Running:
        def isRunning(self):
            return True

    window.job = Running()
    window.library_page.dropzone.set_path(str(tmp_path))
    window.start_scan()
    assert isinstance(window.job, Running)


def test_switches_and_moulded_widgets_follow_their_state(window, qapp):
    from endslate.ui import neu

    row = window.library_page.english_only
    before = row.isChecked()
    row.check.click()
    qapp.processEvents()
    assert row.isChecked() is not before
    tile = window.review_page.tiles["junk"]
    tile.setChecked(True)
    assert neu._target_level(tile, neu.spec_of(tile)) == -1.0
    button = window.library_page.scan_button
    assert neu.spec_of(button) is not None and neu.spec_of(button).fill == "accent"
