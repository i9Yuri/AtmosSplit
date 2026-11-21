"""Trilha de eventos espaciais com o mesmo eixo de tempo das seções musicais."""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QToolTip, QWidget

from ..separation.stem_engine import STEM_DEFINITIONS
from ..spatial.vbap_engine import SPEAKER_COORDINATES_714
from . import theme as T

if TYPE_CHECKING:
    from ..spatial.micro_events import SpatialEvent
    from ..spatial.timeline_manager import SpatialSection
    from .timeline_widget import TimelineTrackCanvas


# Cada linha tem uma posição fixa mesmo quando a música está em silêncio.
KINDS = {
    "syllable": ("Sílaba", 0), "response": ("Resposta vocal", 0), "throw": ("Projeção vocal", 0),
    "fill": ("Virada", 1), "snare_hit": ("Ataque de caixa", 1), "crash": ("Prato de ataque", 1),
    "open_hat": ("Chimbal aberto", 1), "kick_hit": ("Ataque de bumbo", 1),
    "sub_drop": ("Queda de subgrave", 2), "bass_accent": ("Acento de baixo", 2),
    "motif": ("Motivo", 2), "swell": ("Crescendo", 2),
}
LANE_COLORS = ("#38BDF8", "#F59E0B", "#818CF8")
LANE_HELP = ("Microeventos de voz, percussão e instrumentos, de cima para baixo. "
             "Clique em um marcador para posicionar o cursor no evento. "
             "Use as setas para percorrer os eventos com o teclado.")


def event_row(ev: SpatialEvent) -> int:
    return KINDS.get(ev.kind, ("", 2))[1]


def event_title(ev: SpatialEvent) -> str:
    name = KINDS.get(ev.kind, (ev.kind.replace("_", " ").capitalize(), 2))[0]
    stem = STEM_DEFINITIONS.get(ev.stem, {}).get("display_name", ev.stem)
    return f"{name}  ·  {stem}"


def _nearest_speakers(x: float, y: float, z: float, mirrored: bool) -> str:
    speakers = tuple(s for s in SPEAKER_COORDINATES_714 if not s.is_lfe)
    xs = (-abs(x), abs(x)) if mirrored else (x,)
    nearest = (min(speakers, key=lambda s: (px-s.x)**2 + (y-s.y)**2 + (z-s.z)**2).code for px in xs)
    return " + ".join(dict.fromkeys(nearest))


def event_details(ev: SpatialEvent, enabled: bool = True) -> str:
    gain = f"{20 * math.log10(ev.gain):+.1f} dB" if ev.gain > 0 else "−∞ dB"
    if ev.gain == 0 and ev.lfe_send:
        route = "LFE"
    else:
        start = _nearest_speakers(ev.x, ev.y, ev.z, ev.mirrored)
        end = _nearest_speakers(ev.end_x, ev.end_y, ev.end_z, ev.mirrored)
        route = start if start == end else f"{start} → {end}"
    state = ("\nMicrocoreografia desativada na sessão." if not enabled else
             "\nEvento inativo nesta intensidade." if not ev.audible else "")
    return (f"{event_title(ev)}\n{ev.start_s:.2f}–{ev.end_s:.2f} s  ·  Confiança {ev.confidence:.0%}"
            f"  ·  Intensidade {ev.intensity:.0%}\nRota aproximada  {route}  ·  LFE {ev.lfe_send:.0%}"
            f"\nAtaque {ev.attack_s*1000:.0f} ms"
            f"  ·  Liberação {ev.release_s*1000:.0f} ms  ·  Ganho do envio {gain}"
            f"\nInício  X {ev.x:+.2f}  Y {ev.y:+.2f}  Z {ev.z:.2f}"
            f"\nFim     X {ev.end_x:+.2f}  Y {ev.end_y:+.2f}  Z {ev.end_z:.2f}{state}")


class MicroEventLane(QWidget):
    """Marcadores estáticos em cache. Só a agulha e os eventos ativos se movem."""

    seek_requested = Signal(float)
    ROW_HEIGHT = 8
    HEIGHT = 3 * ROW_HEIGHT + 6

    def __init__(self, canvas: TimelineTrackCanvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._events: tuple[SpatialEvent, ...] = ()
        self._starts: tuple[float, ...] = ()
        self._audition_points: tuple[float, ...] = ()
        self._end_prefix: list[float] = []
        self._enabled: dict[SpatialEvent, bool] = {}
        self._cache_key: tuple | None = None
        self._image: QPixmap | None = None
        self._section_events: tuple = ()
        self.setAccessibleName("Microeventos espaciais")
        self.setAccessibleDescription(LANE_HELP)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    @property
    def count(self) -> int:
        return len(self._events)

    def set_sections(self, sections: list[SpatialSection]) -> None:
        section_events = tuple((s.micro_events, s.micro_enabled) for s in sections)
        if section_events == self._section_events:
            return
        self._section_events = section_events
        # Uma projeção que atravessa um corte pode pertencer a dois trechos.
        self._enabled = {ev: s.micro_enabled for s in sections for ev in s.micro_events}
        self._events = tuple(sorted(self._enabled, key=lambda ev: (ev.start_s, ev.stem, ev.kind)))
        self._starts = tuple(ev.start_s for ev in self._events)
        self._audition_points = tuple(sorted({self._audition_time(ev) for ev in self._events}))
        self._end_prefix = []
        end = 0.0
        for ev in self._events:
            end = max(end, ev.end_s)
            self._end_prefix.append(end)
        self._cache_key = None
        self.setAccessibleDescription(LANE_HELP)
        self.update()

    def _between(self, start: float, stop: float) -> tuple[SpatialEvent, ...]:
        left = bisect_left(self._end_prefix, start)
        right = bisect_right(self._starts, stop)
        return self._events[left:right]

    def active_at(self, time_s: float) -> tuple[SpatialEvent, ...]:
        return tuple(ev for ev in self._between(time_s, time_s)
                     if time_s < ev.end_s and self._enabled[ev] and ev.audible)

    def _marker_at(self, x: float, y: float) -> SpatialEvent | None:
        t = self.canvas.x_to_time(x)
        radius = 4 * self.canvas.visible_duration_s / max(1, self.width())
        row = max(0, min(2, int((y-3) // self.ROW_HEIGHT)))
        candidates = (ev for ev in self._between(t-radius, t+radius)
                      if ev.end_s >= t-radius and event_row(ev) == row)
        return min(candidates, key=lambda ev: (max(0, ev.start_s-t, t-ev.end_s), abs(t-ev.start_s)), default=None)

    def _rect(self, ev: SpatialEvent) -> QRectF:
        left = self.canvas.time_to_x(ev.start_s)
        width = max(3.0, self.canvas.time_to_x(ev.end_s) - left)
        return QRectF(left, 4 + event_row(ev)*self.ROW_HEIGHT, width, self.ROW_HEIGHT-3)

    def paintEvent(self, event) -> None:
        key = (self.width(), self.devicePixelRatioF(), self.canvas.visible_duration_s, self.canvas.current_view_start, T.CURRENT_THEME)
        if key != self._cache_key:
            self._cache_key = key
            dpr = self.devicePixelRatioF()
            self._image = QPixmap(round(self.width()*dpr), round(self.HEIGHT*dpr))
            self._image.setDevicePixelRatio(dpr)
            self._image.fill(QColor(T.CANVAS))
            base = QPainter(self._image)
            for row in range(3):
                y = 4 + row*self.ROW_HEIGHT + 2
                base.setPen(QColor(T.GRID))
                base.drawLine(0, y, self.width(), y)
            first = self.canvas.current_view_start
            for ev in self._between(first, first+self.canvas.visible_duration_s):
                if ev.end_s >= first:
                    col = LANE_COLORS[event_row(ev)] if self._enabled[ev] and ev.audible else T.LINE
                    base.fillRect(self._rect(ev), QColor(col))
            if not self._events:
                caption = "Nenhum microevento detectado"
                base.setFont(QFont(T.BODY, 8))
                text_area = QRectF(0, 0, base.fontMetrics().horizontalAdvance(caption)+14, self.HEIGHT)
                base.fillRect(text_area, QColor(T.CANVAS))
                base.setPen(QColor(T.MUTED))
                base.drawText(text_area, Qt.AlignCenter, caption)
            base.end()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._image)
        t = self.canvas.current_time_s
        for ev in self.active_at(t):
            painter.fillRect(self._rect(ev).adjusted(0, -1, 0, 1), QColor(T.INK))
        x = self.canvas.time_to_x(t)
        painter.setPen(QPen(QColor(T.ACCENT), 1.8))
        painter.drawLine(round(x), 0, round(x), self.HEIGHT)
        if self.hasFocus():
            painter.setPen(QPen(QColor(T.WARM), 1))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    @staticmethod
    def _audition_time(ev: SpatialEvent) -> float:
        # Exibe uma projeção com ganho audível mesmo com o transporte pausado.
        return ev.start_s + min(ev.attack_s, (ev.end_s-ev.start_s) / 2)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position()
            ev = self._marker_at(pos.x(), pos.y())
            self.setAccessibleDescription(event_details(ev, self._enabled[ev]) if ev else LANE_HELP)
            self.seek_requested.emit(self._audition_time(ev) if ev else self.canvas.x_to_time(pos.x()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._events and event.key() in (Qt.Key_Left, Qt.Key_Right):
            t = self.canvas.current_time_s
            if event.key() == Qt.Key_Right:
                i = min(len(self._audition_points)-1, bisect_right(self._audition_points, t+.0001))
            else:
                i = max(0, bisect_left(self._audition_points, t-.0001) - 1)
            t = self._audition_points[i]
            if not self.canvas.current_view_start <= t < self.canvas.current_view_start+self.canvas.visible_duration_s:
                self.canvas.set_view(self.canvas.zoom, t-self.canvas.visible_duration_s/2)
            chosen = (ev for ev in self._between(t, t) if self._audition_time(ev) == t)
            self.setAccessibleDescription("\n".join(event_details(ev, self._enabled[ev]) for ev in chosen))
            self.seek_requested.emit(t)
            event.accept()
        else:
            super().keyPressEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.ToolTip:
            ev = self._marker_at(event.pos().x(), event.pos().y())
            tip = event_details(ev, self._enabled[ev]) if ev else LANE_HELP
            QToolTip.showText(event.globalPos(), tip, self)
            return True
        return super().event(event)
