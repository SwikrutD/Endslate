"""How one reviewable change is drawn.

Two lines: what the file will be called, and where it is now. The second line is
monospaced and dimmed, so the eye runs down the new names and only drops to the
old path when something looks wrong. Rows are cut into the sheet they sit on:
the selected one is pressed in, the one under the pointer is lit.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from endslate.models import Bucket
from endslate.ui import icons, neu, theme
from endslate.ui.tablemodel import ENTRY_ROLE
from endslate.ui.theme import BUCKET_TONE, tone_colours

ROW_HEIGHT = 70
CHECK_X = 18
CHECK_SIZE = 22
DOT_X = 52
TEXT_X = 70
RIGHT_PAD = 18
INSET = 4


def human_size(value: int) -> str:
    if value <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024.0
    return ""


class PlanRowDelegate(QStyledItemDelegate):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), ROW_HEIGHT)

    # ------------------------------------------------------------------ paint

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: C901
        entry = index.data(ENTRY_ROLE)
        if entry is None:
            super().paint(painter, option, index)
            return

        palette = theme.active()
        tone = BUCKET_TONE.get(entry.bucket.value, "neutral")
        strong, _soft, _tone_text = tone_colours(palette, tone)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect
        body = QRectF(rect).adjusted(INSET, INSET, -INSET, -INSET)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected:
            neu.paint_inset(painter, body, 18, neu.INSET["sm"])
        elif hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(palette.surface_alt))
            painter.drawRoundedRect(body, 18, 18)
        else:
            # An etched groove between rows rather than a ruled line.
            dark, alpha = neu._rgba(palette.shadow_dark)
            groove = QColor(dark)
            groove.setAlphaF(alpha * 0.45)
            painter.setPen(Qt.NoPen)
            left = rect.left() + (TEXT_X if self.model.selectable else CHECK_X + 20)
            painter.fillRect(QRectF(left, rect.bottom(), rect.right() - left - RIGHT_PAD, 1), groove)

        # checkbox: a small well, or a violet key pressed down into it
        if self.model.selectable:
            box = QRectF(self._check_rect(rect))
            if entry.selected:
                neu.paint_raised(painter, box, 8, neu.RAISED["xs"], fill=neu.accent_fill(box))
                painter.drawPixmap(
                    int(box.left() + (CHECK_SIZE - 14) / 2), int(box.top() + (CHECK_SIZE - 14) / 2),
                    icons.pixmap("check", palette.on_accent, 14),
                )
            else:
                neu.paint_inset(painter, box, 8, neu.INSET["sm"])

        # tone mark: a short upright pill, like a clip colour on a timeline
        dot_x = DOT_X if self.model.selectable else CHECK_X + 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(strong))
        painter.drawRoundedRect(QRectF(rect.left() + dot_x, rect.top() + 18, 4, rect.height() - 36), 2, 2)
        painter.setBrush(Qt.NoBrush)

        # ------------------------------------------------------------- text
        left = rect.left() + (TEXT_X if self.model.selectable else dot_x + 20)
        right = rect.right() - RIGHT_PAD

        # a row you can open gets a hint that it opens
        if entry.bucket in (Bucket.NEEDS_YOU, Bucket.DUPLICATE) and entry.item is not None:
            painter.drawPixmap(
                right - 14, rect.center().y() - 7,
                icons.pixmap("chevron-right", palette.text_faint, 14),
            )
            right -= 24

        size_text = human_size(self.model.size_of(entry))
        extra = self.model.extra_moves(entry)
        meta_font = theme.mono_font(theme.SIZE_CAPTION)
        meta_metrics = QFontMetrics(meta_font)
        badge_font = theme.display_font(theme.SIZE_MICRO, 700)
        badge_metrics = QFontMetrics(badge_font)

        badges: list[str] = []
        if entry.item is not None and entry.item.is_anime:
            badges.append("ANIME")
        if extra:
            badges.append(f"+{extra} SUB" + ("S" if extra > 1 else ""))

        meta_width = meta_metrics.horizontalAdvance(size_text) + 14 if size_text else 0
        badge_width = sum(badge_metrics.horizontalAdvance(b) + 30 for b in badges)

        text_right = right - meta_width - badge_width
        available = max(120, text_right - left)

        primary, secondary = self._lines(entry)

        title_font = theme.font("body", weight=700 if entry.bucket is Bucket.PLANNED else 500)
        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        painter.setPen(QColor(palette.text if entry.bucket is not Bucket.NOOP else palette.text_dim))
        painter.drawText(
            QRect(left, rect.top() + 13, available, title_metrics.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            title_metrics.elidedText(primary, Qt.ElideMiddle, available),
        )

        # Families with fallbacks: asking for Cascadia Mono alone, on a machine
        # without it, got an arbitrary condensed face instead of Consolas.
        mono = theme.mono_font(theme.SIZE_CAPTION)
        painter.setFont(mono)
        mono_metrics = QFontMetrics(mono)
        glyph_y = rect.top() + 40
        painter.drawPixmap(left, glyph_y + 2, icons.pixmap("arrow-right", palette.text_faint, 12))
        painter.setPen(QColor(palette.text_faint))
        painter.drawText(
            QRect(left + 18, glyph_y, available - 18, mono_metrics.height() + 2),
            Qt.AlignLeft | Qt.AlignVCenter,
            mono_metrics.elidedText(secondary, Qt.ElideMiddle, available - 18),
        )

        # ------------------------------------------------------------- meta
        cursor = right
        if size_text:
            painter.setFont(meta_font)
            painter.setPen(QColor(palette.text_faint))
            width = meta_metrics.horizontalAdvance(size_text)
            painter.drawText(
                QRect(cursor - width, rect.top(), width, rect.height()),
                Qt.AlignRight | Qt.AlignVCenter,
                size_text,
            )
            cursor -= width + 16
        painter.setFont(badge_font)
        for badge_text in badges:
            width = badge_metrics.horizontalAdvance(badge_text) + 22
            badge = QRectF(cursor - width, rect.center().y() - 12, width, 24)
            neu.paint_inset(painter, badge, 12, neu.INSET["sm"])
            painter.setPen(QColor(palette.accent_text if badge_text == "ANIME" else palette.text_dim))
            painter.drawText(badge, Qt.AlignCenter, badge_text)
            cursor -= width + 8

        painter.restore()

    # ------------------------------------------------------------------ lines

    def _lines(self, entry) -> tuple[str, str]:
        source = self.model.relative(entry.source_path)
        target = self.model.relative(entry.target_path)

        if entry.bucket is Bucket.JUNK:
            return (f"Quarantine  ·  {entry.reason or 'debris'}", source)
        if entry.bucket in (Bucket.NEEDS_YOU, Bucket.SKIPPED):
            name = Path(source).name if source else ""
            return (name, entry.reason or source)
        if entry.bucket is Bucket.NOOP:
            return (Path(source).name if source else "", "already correct")
        if not target:
            return (Path(source).name if source else "", entry.reason)
        return (target, source)

    # ----------------------------------------------------------- interaction

    def _check_rect(self, rect: QRect) -> QRect:
        return QRect(rect.left() + CHECK_X, rect.center().y() - CHECK_SIZE // 2, CHECK_SIZE, CHECK_SIZE)

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: N802
        if not self.model.selectable:
            return False
        if event.type() == QEvent.MouseButtonRelease:
            hit = self._check_rect(option.rect).adjusted(-10, -10, 10, 10)
            if hit.contains(event.position().toPoint()):
                entry = index.data(ENTRY_ROLE)
                if entry is not None:
                    model.setData(
                        index,
                        Qt.Unchecked if entry.selected else Qt.Checked,
                        Qt.CheckStateRole,
                    )
                    return True
        return False
