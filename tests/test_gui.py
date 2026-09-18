"""A smoke test: the window builds and every page renders. Skipped without Qt."""
import pytest

pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_window_builds_and_pages_render(qapp, tmp_path, monkeypatch):
    import endslate.config as config_mod

    monkeypatch.setattr(config_mod, "app_dir", lambda: tmp_path)
    from endslate.ui.app import MainWindow

    window = MainWindow()
    for row in range(5):
        window.sidebar.setCurrentRow(row)
        qapp.processEvents()
    assert window.template_preview.toPlainText().startswith("Movies\\Fight Club (1999)")


def test_preset_switch_updates_the_example(qapp, tmp_path, monkeypatch):
    import endslate.config as config_mod

    monkeypatch.setattr(config_mod, "app_dir", lambda: tmp_path)
    from endslate.ui.app import MainWindow

    window = MainWindow()
    window.preset_combo.setCurrentIndex(2)  # Flat
    qapp.processEvents()
    assert "Fight Club (1999).mkv" in window.example.text()
