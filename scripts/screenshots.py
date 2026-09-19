"""Render every screen to a PNG so the design can be inspected without a display.

    python scripts/screenshots.py <library folder> [output folder]

Runs the real window against a real plan, offscreen, and never writes to the
library it reads.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from endslate.planner import Options, build_plan  # noqa: E402
from endslate.presets import builtin  # noqa: E402
from endslate.scanner import scan  # noqa: E402

SIZE = (1440, 920)


def main() -> int:
    root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else None
    out = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path("shots")
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv[:1])
    # ENDSLATE_SHOT_FONT=12 reproduces a machine whose system font is larger than
    # the one the layout was designed against, which is where text collided.
    bump = os.environ.get("ENDSLATE_SHOT_FONT")
    if bump:
        from PySide6.QtGui import QFont

        app.setFont(QFont(app.font().family(), int(bump)))
    from endslate.ui import theme
    from endslate.ui.app import MainWindow

    window = MainWindow()
    window.resize(*SIZE)
    window.show()
    app.processEvents()

    plan = None
    if root and root.is_dir():
        scanned = scan(root)
        plan = build_plan(scanned, builtin("Jellyfin"), Options())
        window.scan_result = scanned
        window.plan = plan
        window.library_page.dropzone.set_path(str(root))
        window.library_page.set_hint(
            f"{len(scanned.files):,} files  ·  {scanned.total_bytes / 1_000_000_000:.1f} GB"
        )
        window.review_page.set_plan(plan)
        window.apply_page.set_plan(plan, "Jellyfin looks like it is running (something is "
                                         "listening on http://localhost:8096). Stop the server "
                                         "before applying.")
        app.processEvents()

    shots = []
    for mode in ("dark", "light"):
        window.set_theme(mode)
        app.processEvents()
        for page in ("library", "review", "apply", "history", "settings"):
            window.go_to(page)
            app.processEvents()
            app.processEvents()
            path = out / f"{mode}-{page}.png"
            window.grab().save(str(path))
            shots.append(path)

        if plan is not None:
            window.go_to("review")
            for bucket in ("needs_you", "duplicate", "junk"):
                window.review_page.set_filter(bucket)
                app.processEvents()
                path = out / f"{mode}-review-{bucket}.png"
                window.grab().save(str(path))
                shots.append(path)
            window.review_page.set_filter("planned")

    for path in shots:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
