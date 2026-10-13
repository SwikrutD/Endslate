"""Soft UI physics: the two shadows every surface in the app is moulded with.

Neumorphism needs a light falling from the top left and a shade falling to the
bottom right of every element, both blurred, both translucent. Qt stylesheets
have no box-shadow, and QGraphicsDropShadowEffect casts one shadow per widget
and repaints the widget through an offscreen buffer, which is slow and breaks
item views. So the shadows are painted by hand, in two ways:

* A widget can be *styled*: `style(widget, "raised")`. An ancestor, its host,
  then paints the widget's shadows and fill underneath it, before the widget
  paints its own text on top. A shadow falls outside the element that casts
  it, where the element itself cannot draw, so the host is the nearest
  ancestor with room: a styled surface (a card), something marked as one with
  `surface()` (a page column, the rail), or a scroll area's viewport. Plain
  layout holders in between are looked through; painting on them clipped a
  row of tiles to the row. Every styled widget is transparent in the
  stylesheet; this module is what gives it a body.
* A widget that draws itself (the toggle switch, the dial, the row delegate)
  calls `paint_raised` or `paint_inset` on its own painter.

Shadows are cut from blurred sprites and nine-sliced to size, so a card that
resizes costs nine pixmap blits rather than a fresh blur. Blurring is done once
per radius, depth, colour and display scale, with Qt's own blur filter.
"""
from __future__ import annotations

import atexit
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QGraphicsBlurEffect,
    QGraphicsScene,
    QWidget,
)

try:
    from shiboken6 import getCppPointer as _pointer, isValid as _alive
except ImportError:  # pragma: no cover
    def _alive(_obj) -> bool:
        return True

    def _pointer(obj):
        return (id(obj),)


# Keyed by the C++ object, not the Python one. PySide can hand back a fresh
# wrapper for a widget Qt created itself (a scroll area's viewport), and an
# attribute set on the old wrapper is gone from the new one.
_specs: dict[int, "Spec"] = {}
_clients: dict[int, list] = {}


_closing = False


def _on_exit() -> None:
    # Python tears the wrappers down while Qt is still sending its last
    # events; a filter that answers then raises on every one of them.
    global _closing
    _closing = True


atexit.register(_on_exit)


def _key(obj) -> int:
    return int(_pointer(obj)[0])


def _forget(address: int) -> None:
    _specs.pop(address, None)
    _clients.pop(address, None)

from endslate.ui import theme


@dataclass(frozen=True)
class Depth:
    offset: float
    blur: float

    @property
    def extent(self) -> int:
        """How far outside its element a shadow of this depth can reach."""
        return int(math.ceil(self.offset + self.blur * 1.1))


# The scale from the design system, tightened a little for a desktop tool that
# packs more onto a screen than a landing page does. Names follow Theme.md.
RAISED = {
    "xs": Depth(2, 4),
    "sm": Depth(4, 8),       # Extruded Small
    "md": Depth(6, 12),
    "lg": Depth(9, 16),      # Extruded (standard)
}
LIFTED = {
    "xs": Depth(3, 6),
    "sm": Depth(5, 10),
    "md": Depth(8, 15),
    "lg": Depth(12, 20),     # Extruded Hover
}
INSET = {
    "sm": Depth(3, 6),       # Inset Small
    "md": Depth(6, 10),      # Inset
    "deep": Depth(10, 20),   # Inset Deep
}

DURATION = 300          # UI elements, per the design system
PRESS_DURATION = 120    # a press is felt, not watched
CACHE_LIMIT = 400


# ---------------------------------------------------------------- sprites


_sprites: "OrderedDict[tuple, tuple[QPixmap, float, float]]" = OrderedDict()


def _blurred(image: QImage, radius: float) -> QImage:
    """Qt's Gaussian blur, borrowed from the graphics view, which owns it."""
    scene = QGraphicsScene()
    item = scene.addPixmap(QPixmap.fromImage(image))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    effect.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(effect)
    out = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    scene.render(painter, QRectF(out.rect()), QRectF(image.rect()))
    painter.end()
    return out


def _remember(key: tuple, value: tuple) -> tuple:
    _sprites[key] = value
    _sprites.move_to_end(key)
    while len(_sprites) > CACHE_LIMIT:
        _sprites.popitem(last=False)
    return value


def _sprite(kind: str, radius: float, blur: float, rgb: str, dpr: float,
            size: Optional[tuple[float, float]] = None) -> tuple[QPixmap, float, float]:
    """A blurred rounded rectangle (raised) or a blurred frame around one (inset).

    Returns (pixmap at dpr, pad, core) in logical pixels. Without `size` the
    core is square and just big enough to nine-slice; with it the sprite is cut
    to that exact size, for elements too small to slice.
    """
    key = (kind, round(radius, 1), round(blur, 1), rgb, round(dpr, 2), size)
    hit = _sprites.get(key)
    if hit is not None:
        _sprites.move_to_end(key)
        return hit

    pad = math.ceil(blur * 1.3) + 2
    if size is None:
        # Wide enough that the centre of the slice is clear of the blur.
        core = 2 * max(radius, blur * 1.6) + 4
        core_w = core_h = core
    else:
        core_w, core_h = size
    width, height = core_w + 2 * pad, core_h + 2 * pad
    image = QImage(int(math.ceil(width * dpr)), int(math.ceil(height * dpr)),
                   QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(dpr, dpr)
    colour = QColor(rgb)
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(pad, pad, core_w, core_h), radius, radius)
    if kind == "raised":
        painter.fillPath(shape, colour)
    else:
        frame = QPainterPath()
        frame.addRect(QRectF(0, 0, width, height))
        painter.fillPath(frame.subtracted(shape), colour)
    painter.end()
    pixmap = QPixmap.fromImage(_blurred(image, blur * dpr))
    return _remember(key, (pixmap, float(pad), float(core_w if size is None else 0)))


def _draw_sliced(painter: QPainter, pixmap: QPixmap, target: QRectF, pad: float, core: float, dpr: float) -> None:
    """Stretch a square sprite over `target` (the element's rect) by its nine parts."""
    outer = target.adjusted(-pad, -pad, pad, pad)
    total = core + 2 * pad
    corner = total / 2 - 1
    xs_src = [0, corner, total - corner, total]
    ys_src = xs_src
    xs_dst = [outer.left(), outer.left() + corner, outer.right() - corner, outer.right()]
    ys_dst = [outer.top(), outer.top() + corner, outer.bottom() - corner, outer.bottom()]
    for row in range(3):
        for col in range(3):
            dst = QRectF(QPointF(xs_dst[col], ys_dst[row]), QPointF(xs_dst[col + 1], ys_dst[row + 1]))
            if dst.width() <= 0 or dst.height() <= 0:
                continue
            src = QRectF(
                QPointF(xs_src[col] * dpr, ys_src[row] * dpr),
                QPointF(xs_src[col + 1] * dpr, ys_src[row + 1] * dpr),
            )
            painter.drawPixmap(dst, pixmap, src)


def _shadow(painter: QPainter, kind: str, rect: QRectF, radius: float, depth: Depth,
            rgb: str, opacity: float, dx: float, dy: float) -> None:
    if opacity <= 0.005 or rect.width() <= 0 or rect.height() <= 0:
        return
    dpr = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
    radius = max(0.0, min(radius, rect.width() / 2, rect.height() / 2))
    pixmap, pad, core = _sprite(kind, radius, depth.blur, rgb, dpr)
    target = rect.translated(dx, dy)
    painter.save()
    painter.setOpacity(painter.opacity() * opacity)
    if rect.width() >= core and rect.height() >= core:
        _draw_sliced(painter, pixmap, target, pad, core, dpr)
    else:
        exact, pad, _ = _sprite(kind, radius, depth.blur, rgb, dpr,
                                size=(round(rect.width(), 1), round(rect.height(), 1)))
        painter.drawPixmap(
            target.adjusted(-pad, -pad, pad, pad), exact,
            QRectF(0, 0, exact.width(), exact.height()),
        )
    painter.restore()


def _rgba(value: str) -> tuple[str, float]:
    """Split a palette shadow ("rgba(163,177,198,0.6)") into colour and alpha."""
    text = value.strip()
    if text.startswith("rgba"):
        parts = [p.strip() for p in text[text.index("(") + 1:text.rindex(")")].split(",")]
        r, g, b = (int(float(x)) for x in parts[:3])
        alpha = float(parts[3]) if len(parts) > 3 else 1.0
        return QColor(r, g, b).name(), alpha
    return QColor(text).name(), 1.0


def rounded(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


# ------------------------------------------------------------ public paint


def paint_raised(painter: QPainter, rect: QRectF, radius: float, depth: Depth, *,
                 fill=None, strength: float = 1.0) -> None:
    """An element extruded from the surface: light above left, shade below right."""
    palette = theme.active()
    light, light_alpha = _rgba(palette.shadow_light)
    dark, dark_alpha = _rgba(palette.shadow_dark)
    _shadow(painter, "raised", rect, radius, depth, light, light_alpha * strength, -depth.offset, -depth.offset)
    _shadow(painter, "raised", rect, radius, depth, dark, dark_alpha * strength, depth.offset, depth.offset)
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(fill if fill is not None else QColor(palette.canvas))
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


def paint_inset(painter: QPainter, rect: QRectF, radius: float, depth: Depth, *,
                fill=None, strength: float = 1.0) -> None:
    """An element pressed into the surface: shade inside the top left edge."""
    palette = theme.active()
    light, light_alpha = _rgba(palette.shadow_light)
    dark, dark_alpha = _rgba(palette.shadow_dark)
    radius = max(0.0, min(radius, rect.width() / 2, rect.height() / 2))
    painter.save()
    painter.setClipPath(rounded(rect, radius), Qt.IntersectClip)
    painter.fillRect(rect, fill if fill is not None else QColor(palette.canvas))
    _shadow(painter, "inset", rect, radius, depth, dark, dark_alpha * strength, depth.offset, depth.offset)
    _shadow(painter, "inset", rect, radius, depth, light, light_alpha * strength, -depth.offset, -depth.offset)
    painter.restore()


def paint_ring(painter: QPainter, rect: QRectF, radius: float, colour: str, offset: float = 3.0,
               width: float = 2.0) -> None:
    """The focus ring: 2px of accent, held 2px off the element."""
    painter.save()
    pen = QPen(QColor(colour), width)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    grown = rect.adjusted(-offset, -offset, offset, offset)
    painter.drawRoundedRect(grown, radius + offset, radius + offset)
    painter.restore()


def accent_fill(rect: QRectF) -> QLinearGradient:
    """The one coloured surface: violet, lit from the same top left."""
    palette = theme.active()
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor(palette.accent_hover))
    gradient.setColorAt(1.0, QColor(palette.accent))
    return gradient


def mix(a: Depth, b: Depth, t: float) -> Depth:
    t = max(0.0, min(1.0, t))
    return Depth(a.offset + (b.offset - a.offset) * t, round(a.blur + (b.blur - a.blur) * t))


# ---------------------------------------------------------- styled widgets


@dataclass
class Spec:
    kind: str = "raised"            # raised, inset, flat
    radius: float = theme.RADIUS_BASE
    depth: str = "sm"
    interactive: bool = False       # lifts on hover, sinks when pressed
    fill: str = ""                  # "", "accent", or a palette attribute
    focus_ring: bool = False        # the widget, or one inside it, has focus
    margin: float = 0.0             # draw this far inside the widget's rect
    hover_flat: bool = False        # flat at rest, raised only on hover (ghost buttons)
    keyboard_ring: bool = False     # ring only when focus came from the keyboard
    ring: bool = False              # ringed regardless of focus: a drop target that is live
    kbd_focus: bool = False
    level: float = 0.0              # animated: -1 pressed, 0 resting, 1 lifted
    anim: Optional[QVariantAnimation] = field(default=None, repr=False)
    host: Optional[QWidget] = field(default=None, repr=False)


def style(widget: QWidget, kind: str = "raised", *, radius: Optional[float] = None, depth: str = "sm",
          interactive: bool = False, fill: str = "", focus_ring: bool = False, margin: float = 0.0,
          hover_flat: bool = False, keyboard_ring: bool = False, ring: bool = False) -> QWidget:
    """Give a widget a moulded body, painted by its parent beneath it."""
    spec = spec_of(widget)
    if spec is None:
        spec = Spec()
        address = _key(widget)
        _specs[address] = spec
        widget.destroyed.connect(lambda _obj=None, a=address: _forget(a))
        widget.installEventFilter(_watcher())
        widget.setAttribute(Qt.WA_Hover, True)
        widget.setProperty("neu", True)
        if isinstance(widget, QAbstractButton):
            # Set in code, a check changes no event the watcher would see.
            widget.toggled.connect(lambda _on=False, w=widget: update_state(w))
            widget.pressed.connect(lambda w=widget: update_state(w))
            widget.released.connect(lambda w=widget: update_state(w))
        if widget.style() is not None:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
    spec.kind = kind
    spec.radius = theme.RADIUS_BASE if radius is None else radius
    spec.depth = depth
    spec.interactive = interactive
    spec.fill = fill
    spec.focus_ring = focus_ring
    spec.margin = margin
    spec.hover_flat = hover_flat
    spec.keyboard_ring = keyboard_ring
    spec.ring = ring
    _attach(widget)
    _refresh(widget)
    return widget


def spec_of(widget: QWidget) -> Optional[Spec]:
    if widget is None or not _alive(widget):
        return None
    return _specs.get(_key(widget))


def extent_of(spec: Spec) -> int:
    table = INSET if spec.kind == "inset" else LIFTED
    depth = table.get(spec.depth) or LIFTED["lg"]
    return depth.extent + 6


def surface(widget: QWidget) -> QWidget:
    """Mark a container as a surface: the shadows of what it holds land on it."""
    widget.setProperty("neuSurface", True)
    return widget


def _find_host(widget: QWidget) -> Optional[QWidget]:
    ancestor = widget.parentWidget()
    while ancestor is not None:
        if ancestor.isWindow() or ancestor.property("neuSurface") or spec_of(ancestor) is not None:
            return ancestor
        parent = ancestor.parentWidget()
        if isinstance(parent, QAbstractScrollArea) and parent.viewport() is ancestor:
            return ancestor
        ancestor = parent
    return None


def _attach(widget: QWidget) -> None:
    spec = spec_of(widget)
    if spec is None:
        return
    host = _find_host(widget)
    old = spec.host if spec.host is not None and _alive(spec.host) else None
    if host is old:
        return
    if old is not None:
        clients = _clients.get(_key(old), [])
        if widget in clients:
            clients.remove(widget)
    spec.host = host
    if host is None:
        return
    address = _key(host)
    if address not in _clients:
        _clients[address] = []
        host.installEventFilter(_host())
        host.destroyed.connect(lambda _obj=None, a=address: _clients.pop(a, None))
    _clients[address].append(widget)
    # Holders between the widget and its host move it without telling it.
    ancestor = widget.parentWidget()
    while ancestor is not None and ancestor is not host:
        if not ancestor.property("neuRelay"):
            ancestor.setProperty("neuRelay", True)
            ancestor.installEventFilter(_relay())
        ancestor = ancestor.parentWidget()


def _host_rect(widget: QWidget, host: QWidget) -> QRectF:
    origin = widget.mapTo(host, QPoint(0, 0))
    return QRectF(origin.x(), origin.y(), widget.width(), widget.height())


def _refresh(widget: QWidget) -> None:
    spec = spec_of(widget)
    if spec is None:
        return
    host = spec.host
    if host is None or not _alive(host):
        _attach(widget)
        host = spec.host
    if host is None:
        return
    grow = extent_of(spec)
    rect = _host_rect(widget, host).toAlignedRect()
    host.update(rect.adjusted(-grow, -grow, grow, grow))


def _target_level(widget: QWidget, spec: Spec) -> float:
    if not widget.isEnabled():
        return 0.0
    pressed = False
    if isinstance(widget, QAbstractButton):
        pressed = widget.isDown() or (widget.isCheckable() and widget.isChecked())
    else:
        checked = getattr(widget, "isChecked", None)
        pressed = bool(callable(checked) and checked())
    if widget.property("neuPressed"):
        pressed = True
    if pressed:
        return -1.0
    if spec.interactive and widget.underMouse():
        return 1.0
    return 0.0


def update_state(widget: QWidget) -> None:
    """Move toward the state the widget is in now, over the design's 300 ms."""
    spec = spec_of(widget)
    if spec is None:
        return
    target = _target_level(widget, spec)
    if abs(target - spec.level) < 0.001:
        _refresh(widget)
        return
    if spec.anim is None:
        anim = QVariantAnimation(widget)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def step(value, w=widget):
            s = spec_of(w)
            if s is not None:
                s.level = float(value)
                _refresh(w)

        anim.valueChanged.connect(step)
        spec.anim = anim
    anim = spec.anim
    anim.stop()
    anim.setDuration(PRESS_DURATION if target < spec.level else DURATION)
    anim.setStartValue(float(spec.level))
    anim.setEndValue(float(target))
    anim.start()


class _Watcher(QObject):
    """Sits on every styled widget, telling its parent when to repaint it."""

    STATE = {
        QEvent.Enter, QEvent.Leave, QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
        QEvent.EnabledChange, QEvent.FocusIn, QEvent.FocusOut, QEvent.HoverEnter, QEvent.HoverLeave,
        QEvent.KeyRelease, QEvent.DynamicPropertyChange,
    }
    GEOMETRY = {QEvent.Move, QEvent.Resize, QEvent.Show, QEvent.Hide}

    def eventFilter(self, obj, event):  # noqa: N802
        if _closing:
            return False
        try:
            self._handle(obj, event)
        except RuntimeError:
            pass  # the widget is already gone on the C++ side
        return False

    def _handle(self, obj, event) -> None:
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.FocusOut):
            spec = spec_of(obj)
            if spec is not None:
                spec.kbd_focus = kind == QEvent.FocusIn and event.reason() in (
                    Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)
        if kind == QEvent.ParentChange:
            _attach(obj)
            _refresh(obj)
        elif kind in self.GEOMETRY:
            if kind == QEvent.Show:
                _attach(obj)
            _refresh(obj)
        elif kind in self.STATE:
            update_state(obj)


class _Host(QObject):
    """Sits on every host and paints the bodies of its styled widgets beneath them."""

    def eventFilter(self, obj, event):  # noqa: N802
        if _closing:
            return False
        if event.type() == QEvent.Paint:
            if obj.isWindow():
                # A window paints its own background, which would cover the
                # bodies. Let it, then paint them on top, under the children.
                obj.event(event)
                paint_children(obj)
                return True
            paint_children(obj)
        return False


class _Relay(QObject):
    """Sits on the plain holders between a styled widget and its host."""

    def eventFilter(self, obj, event):  # noqa: N802
        if _closing:
            return False
        if event.type() in (QEvent.Move, QEvent.Resize, QEvent.Show, QEvent.Hide):
            for child in obj.findChildren(QWidget):
                spec = spec_of(child)
                if spec is not None and spec.host is not None and _alive(spec.host):
                    rect = _host_rect(obj, spec.host).toAlignedRect()
                    spec.host.update(rect.adjusted(-48, -48, 48, 48))
                    break
        return False


_watcher_instance: Optional[_Watcher] = None
_host_instance: Optional[_Host] = None
_relay_instance: Optional[_Relay] = None


def _relay() -> _Relay:
    global _relay_instance
    if _relay_instance is None:
        _relay_instance = _Relay()
    return _relay_instance


def _watcher() -> _Watcher:
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = _Watcher()
    return _watcher_instance


def _host() -> _Host:
    global _host_instance
    if _host_instance is None:
        _host_instance = _Host()
    return _host_instance


def _has_focus_within(widget: QWidget) -> bool:
    if widget.hasFocus():
        return True
    focused = widget.focusWidget()
    return focused is not None and focused is not widget and widget.isAncestorOf(focused) and focused.hasFocus()


def _fill_for(spec: Spec, rect: QRectF, enabled: bool):
    palette = theme.active()
    if spec.fill == "accent" and enabled:
        return QBrush(accent_fill(rect))
    if spec.fill and spec.fill != "accent":
        return QColor(getattr(palette, spec.fill, palette.canvas))
    return QColor(palette.canvas)


def paint_widget_body(painter: QPainter, widget: QWidget, rect: QRectF) -> None:
    """Paint one styled widget's body into `rect`, in its parent's coordinates."""
    spec = spec_of(widget)
    if spec is None or spec.kind == "flat" and not spec.hover_flat:
        return
    enabled = widget.isEnabled()
    level = spec.level
    fill = _fill_for(spec, rect, enabled)
    strength = 1.0 if enabled else 0.45

    if spec.kind == "inset":
        depth = INSET.get(spec.depth, INSET["md"])
        if spec.focus_ring and _has_focus_within(widget):
            depth = INSET["deep"] if spec.depth != "sm" else INSET["md"]
        paint_inset(painter, rect, spec.radius, depth, fill=fill, strength=strength)
    else:
        rest = RAISED.get(spec.depth, RAISED["sm"])
        lifted = LIFTED.get(spec.depth, LIFTED["sm"])
        if spec.hover_flat:
            # A ghost: no body until the pointer is over it.
            raised_strength = max(0.0, level) * strength
            if raised_strength > 0.01:
                paint_raised(painter, rect, spec.radius, rest, fill=fill, strength=raised_strength)
            if level < 0:
                paint_inset(painter, rect, spec.radius, INSET["sm"], fill=fill, strength=-level * strength)
        elif level >= 0:
            paint_raised(painter, rect, spec.radius, mix(rest, lifted, level), fill=fill,
                         strength=strength * (1.0 + 0.12 * level))
        else:
            # Pressed: the extrusion fades as the well appears.
            press = -level
            if press < 1.0:
                paint_raised(painter, rect, spec.radius, rest, fill=fill, strength=strength * (1.0 - press))
            paint_inset(painter, rect, spec.radius, INSET["sm"] if spec.depth in ("xs", "sm") else INSET["md"],
                        fill=fill, strength=strength * press)

    focused = spec.focus_ring and _has_focus_within(widget) and (not spec.keyboard_ring or spec.kbd_focus)
    if spec.ring or focused:
        paint_ring(painter, rect, min(spec.radius, rect.height() / 2), theme.active().accent)


def _depth(widget: QWidget, host: QWidget) -> int:
    depth = 0
    ancestor = widget.parentWidget()
    while ancestor is not None and ancestor is not host:
        depth += 1
        ancestor = ancestor.parentWidget()
    return depth


def paint_children(host: QWidget) -> None:
    address = _key(host)
    clients = _clients.get(address)
    if not clients:
        return
    alive = [w for w in clients if _alive(w)]
    if len(alive) != len(clients):
        _clients[address] = alive
    styled = [
        w for w in alive
        if spec_of(w) is not None and spec_of(w).host is host and w.isVisible()
        and not w.isWindow() and host.isAncestorOf(w)
    ]
    if not styled:
        return
    # Outer bodies first: a card is moulded before the buttons set into it.
    styled.sort(key=lambda w: _depth(w, host))
    painter = QPainter(host)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    for child in styled:
        spec = spec_of(child)
        m = spec.margin
        rect = _host_rect(child, host).adjusted(m, m, -m, -m)
        paint_widget_body(painter, child, rect)
    painter.end()


def restyle_all() -> None:
    """Theme changed: the sprites carry the old colours, so throw them away."""
    _sprites.clear()
