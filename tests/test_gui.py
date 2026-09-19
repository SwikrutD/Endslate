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

    return MainWindow()


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
