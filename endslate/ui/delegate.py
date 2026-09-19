"""How one reviewable change is drawn.

Two lines: what the file will be called, and where it is now. The second line is
monospaced and dimmed, so the eye runs down the new names and only drops to the
old path when something looks wrong.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from endslate.models import Bucket, OpKind
from endslate.ui import icons, theme
from endslate.ui.tablemodel import ENTRY_ROLE
from endslate.ui.theme import BUCKET_TONE, RADIUS_SM, tone_colours

ROW_HEIGHT = 64
CHECK_X = 16
CHECK_SIZE = 17
DOT_X = 45
TEXT_X = 62
RIGHT_PAD = 16


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
        strong, soft, _tone_text = tone_colours(palette, tone)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected:
            painter.fillRect(rect, QColor(palette.selection))
        elif hovered:
            painter.fillRect(rect, QColor(palette.surface_alt))

        # hairline between rows
        painter.setPen(QPen(QColor(palette.line), 1))
        painter.drawLine(
            rect.left() + (TEXT_X if self.model.selectable else CHECK_X), rect.bottom(),
            rect.right(), rect.bottom(),
        )

        # selection accent on the left edge
        if selected:
            painter.fillRect(QRect(rect.left(), rect.top(), 2, rect.height()), QColor(palette.accent))

        # checkbox
        if self.model.selectable:
            box = self._check_rect(rect)
            checked = entry.selected
            painter.setPen(QPen(QColor(palette.accent if checked else palette.line_strong), 1))
            painter.setBrush(QColor(palette.accent) if checked else Qt.NoBrush)
            painter.drawRoundedRect(box, 5, 5)
            if checked:
                painter.drawPixmap(box.left() + 2, box.top() + 2, icons.pixmap("check", palette.on_accent, 13))
            painter.setBrush(Qt.NoBrush)

        # tone dot, pulled left when there is no checkbox to sit beside
        dot_x = DOT_X if self.model.selectable else CHECK_X + 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(strong))
        painter.drawEllipse(rect.left() + dot_x, rect.center().y() - 4, 8, 8)
        painter.setBrush(Qt.NoBrush)

        # ------------------------------------------------------------- text
        left = rect.left() + (TEXT_X if self.model.selectable else dot_x + 20)
        right = rect.right() - RIGHT_PAD

        # a row you can open gets a hint that it opens
        if entry.bucket in (Bucket.NEEDS_YOU, Bucket.DUPLICATE) and entry.item is not None:
            painter.drawPixmap(
                right - 14, rect.center().y() - 7,
                icons.pixmap("chevron-right", palette.line_strong, 14),
            )
            right -= 22

        size_text = human_size(self.model.size_of(entry))
        extra = self.model.extra_moves(entry)
        meta_font = QFont(painter.font())
        meta_font.setPointSize(theme.SIZE_CAPTION)
        meta_metrics = QFontMetrics(meta_font)

        meta_width = 0
        if size_text:
            meta_width = meta_metrics.horizontalAdvance(size_text) + 12
        badge_width = 0
        badge_text = ""
        if extra:
            badge_text = f"+{extra} sub" + ("s" if extra > 1 else "")
            badge_width = meta_metrics.horizontalAdvance(badge_text) + 20

        text_right = right - meta_width - badge_width
        available = max(120, text_right - left)

        primary, secondary = self._lines(entry)

        title_font = QFont(painter.font())
        title_font.setPointSize(theme.SIZE_BODY)
        title_font.setWeight(QFont.DemiBold if entry.bucket is Bucket.PLANNED else QFont.Normal)
        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        painter.setPen(QColor(palette.text if entry.bucket is not Bucket.NOOP else palette.text_dim))
        painter.drawText(
            QRect(left, rect.top() + 11, available, title_metrics.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            title_metrics.elidedText(primary, Qt.ElideMiddle, available),
        )

        mono = QFont(theme.FONT_MONO.split(",")[0].strip('"'))
        mono.setPointSize(theme.SIZE_CAPTION)
        painter.setFont(mono)
        mono_metrics = QFontMetrics(mono)
        glyph_y = rect.top() + 36
        painter.drawPixmap(left, glyph_y + 2, icons.pixmap("arrow-right", palette.text_faint, 12))
        painter.setPen(QColor(palette.text_faint))
        painter.drawText(
            QRect(left + 17, glyph_y, available - 17, mono_metrics.height() + 2),
            Qt.AlignLeft | Qt.AlignVCenter,
            mono_metrics.elidedText(secondary, Qt.ElideMiddle, available - 17),
        )

        # ------------------------------------------------------------- meta
        painter.setFont(meta_font)
        cursor = right
        if size_text:
            painter.setPen(QColor(palette.text_faint))
            width = meta_metrics.horizontalAdvance(size_text)
            painter.drawText(
                QRect(cursor - width, rect.top(), width, rect.height()),
                Qt.AlignRight | Qt.AlignVCenter,
                size_text,
            )
            cursor -= width + 14
        if badge_text:
            width = meta_metrics.horizontalAdvance(badge_text) + 14
            badge = QRect(cursor - width, rect.center().y() - 10, width, 20)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(palette.surface_hi))
            painter.drawRoundedRect(badge, 10, 10)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QColor(palette.text_dim))
            painter.drawText(badge, Qt.AlignCenter, badge_text)

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
            hit = self._check_rect(option.rect).adjusted(-8, -8, 8, 8)
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
