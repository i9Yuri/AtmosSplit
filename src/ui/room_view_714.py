"""Planta do estúdio com projeção de altura, picking e edição de objetos."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QMenu, QToolTip, QWidget

from ..separation.stem_engine import StemTrack
from ..spatial.auto_director import SpatialPlacement
from ..spatial.vbap_engine import SPEAKER_COORDINATES_714, VBAP714Engine
from . import theme as T
from .micro_event_lane import LANE_COLORS, event_details, event_row

if TYPE_CHECKING:
    from ..spatial.micro_events import SpatialEvent


class RoomView714(QWidget):
    placement_changed = Signal(str, float, float, float)
    stereo_toggled = Signal(str, bool)
    stem_selected = Signal(str)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    copy_requested = Signal(str)
    paste_requested = Signal()
    playback_toggle_requested = Signal()
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(350, 260)
        self.setAccessibleName("Sala espacial 7.1.4")
        self.setToolTip("Arraste a fonte no plano. A roda ajusta a altura. D alterna o espelhamento.")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.vbap = VBAP714Engine()
        self.stems: dict[str, StemTrack] = {}
        self._sources: dict[str, StemTrack] = {}
        self.placements: dict[str, SpatialPlacement] = {}
        self.projections: dict[str, SpatialPlacement] = {}
        self.micro_events: tuple[SpatialEvent, ...] = ()
        self._event_by_stem: dict[str, SpatialEvent] = {}
        self.active_stem_name: str | None = None
        self.hovered_stem_info: tuple[str, str] | None = None
        self._is_dragging = False
        self.stems_vu: dict[str, float] = {}
        self.sub_vu = 0.0
        self._ray_key = None
        self._rays = []
        self.reduced_motion = False

    @staticmethod
    def get_visual_radius(z: float, vu: float = 0.0) -> float:
        return 11.0 + 22.0 * z + 3.5 * vu

    @staticmethod
    def _nodes(p: SpatialPlacement) -> tuple[tuple[str, float], ...]:
        if p.is_stereo:
            d = abs(p.x)
            return (("L", -d), ("R", d))
        return (("C", p.x),)

    def set_stems_and_placements(self, stems: list[StemTrack], placements: dict[str, SpatialPlacement]) -> None:
        self._is_dragging = False
        self._sources = {s.name: s for s in stems}
        self.stems.clear()
        self.set_micro_events(())
        self.set_playback_placements(placements)

    def set_playback_placements(self, placements: dict[str, SpatialPlacement]) -> None:
        if self._is_dragging:
            return
        self.projections = {key: p for key, p in placements.items() if key.endswith("::micro")}
        if self.stems.keys() != placements.keys() - self.projections.keys():
            self.stems = {}
            for key, p in placements.items():
                if key in self.projections:
                    continue
                base = self._sources.get(p.source_stem_name or key.split("::")[0])
                if base:
                    name = base.display_name
                    if "::spatial_throw" in key:
                        name = "Vocal Throw (BL/BR)"
                    elif "::" in key:
                        name = f"{name} #{key.rsplit('::', 1)[1]}"
                    self.stems[key] = base if key == base.name else replace(base, name=key, display_name=name)
        self.placements = placements
        if self.active_stem_name not in self.stems:
            self.active_stem_name = next(iter(self.stems), None)
        self._update_rays_cache()
        self.update()

    def set_micro_events(self, events: tuple[SpatialEvent, ...]) -> None:
        if events != self.micro_events:
            self.micro_events = events
            self._event_by_stem = {ev.stem: ev for ev in events}
            self.update()

    def _update_rays_cache(self) -> None:
        p = self.placements.get(self.active_stem_name)
        if not p:
            self._rays = []
            self._ray_key = None
            return
        other_solo = any(item.is_solo for item in self.placements.values()) and not p.is_solo
        key = (p.x, p.y, p.z, p.spread, p.lfe_send, p.is_muted, p.is_stereo, p.volume_gain, other_solo)
        if key == self._ray_key:
            return
        self._ray_key = key
        self._rays = []
        if p.is_muted or p.volume_gain <= 0.0 or other_solo:
            return
        for _, x in self._nodes(p):
            gains = self.vbap.calculate_gains(x, p.y, p.z, p.spread, p.lfe_send)
            self._rays.append((x, gains))

    def set_vu_levels(self, stems_vu: dict[str, float], sub_vu: float) -> None:
        if self.stems_vu != stems_vu or self.sub_vu != sub_vu:
            self.stems_vu, self.sub_vu = stems_vu, sub_vu
            self.update()

    def set_active_stem(self, stem_name: str) -> None:
        if stem_name in self.stems and stem_name != self.active_stem_name:
            self.active_stem_name = stem_name
            self._update_rays_cache()
            self.stem_selected.emit(stem_name)
            self.update()

    def update_placement(self, name: str, x: float, y: float, z: float, is_stereo: bool | None = None) -> None:
        if name in self.stems:
            p = self.placements[name]
            p.x, p.y, p.z = x, y, z
            if is_stereo is not None:
                p.is_stereo = is_stereo
            self._update_rays_cache()
            self.update()

    def toggle_stereo_mirror(self, name: str) -> None:
        if name in self.stems:
            p = self.placements[name]
            p.is_stereo = not p.is_stereo
            if p.is_stereo and abs(p.x) < 0.2:
                p.x = 0.6
            self.stereo_toggled.emit(name, p.is_stereo)
            self._move(name, p.x, p.y, p.z)

    def _room_to_widget_coords(self, x: float, y: float) -> QPointF:
        w, h = self.width(), self.height()
        return QPointF(w * 0.5 + x * (w * 0.5 - 46) * (0.91 - y * 0.09),
                       h * 0.5 + 8 - y * max(1, h * 0.5 - 58))

    def _widget_to_room_coords(self, px: float, py: float) -> tuple[float, float]:
        w, h = self.width(), self.height()
        y = np.clip((h * 0.5 + 8 - py) / max(1, h * 0.5 - 58), -1.0, 1.0)
        x = np.clip((px - w * 0.5) / max(1, (w * 0.5 - 46) * (0.91 - y * 0.09)), -1.0, 1.0)
        return float(x), float(y)

    def _get_node_positions(self, x_or_plc: float | SpatialPlacement, y: float = 0, z: float = 0) -> tuple[QPointF, QPointF]:
        if isinstance(x_or_plc, SpatialPlacement):
            x, y, z = x_or_plc.x, x_or_plc.y, x_or_plc.z
        else:
            x = x_or_plc
        floor = self._room_to_widget_coords(x, y)
        return floor, floor - QPointF(0, z * 34)

    def _speaker_point(self, speaker) -> QPointF:
        if speaker.is_lfe:
            return self._room_to_widget_coords(-0.99, 0.87)
        return self._get_node_positions(speaker.x, speaker.y, speaker.z)[1]

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(T.CANVAS))
        painter.setPen(QPen(QColor(T.ACCENT if self.hasFocus() else T.LINE), 1))
        painter.setBrush(QColor(T.PANEL))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        floor = QPolygonF([self._room_to_widget_coords(x, y) for x, y in
                           ((-1, 1), (1, 1), (1, -1), (-1, -1))])
        painter.setPen(QPen(QColor(T.LINE), 1))
        painter.setBrush(QColor(T.CANVAS))
        painter.drawPolygon(floor)
        for t in (-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75):
            painter.setPen(QPen(QColor(T.GRID if t else T.LINE), 1,
                                Qt.SolidLine if t else Qt.DashLine))
            painter.drawLine(self._room_to_widget_coords(t, 1), self._room_to_widget_coords(t, -1))
            painter.drawLine(self._room_to_widget_coords(-1, t), self._room_to_widget_coords(1, t))
        painter.setFont(QFont(T.BODY, 9, QFont.DemiBold))
        painter.setPen(QColor(T.SECONDARY))
        painter.drawText(QRectF(0, 5, self.width(), 22), Qt.AlignCenter, "Frente · TV")
        self._draw_speakers(painter)
        center = self._room_to_widget_coords(0, 0)
        painter.setPen(QPen(QColor(T.SECONDARY), 1.2))
        painter.setBrush(QColor(T.PANEL_ALT))
        painter.drawEllipse(center, 6.0, 6.0)
        painter.setPen(QColor(T.INK))
        painter.drawText(QRectF(center.x()-55, center.y()+9, 110, 18), Qt.AlignCenter, "Escuta")
        active = self.placements.get(self.active_stem_name)
        if active:
            for x, gains in self._rays:
                point = self._get_node_positions(x, active.y, active.z)[1]
                for speaker, gain in zip(SPEAKER_COORDINATES_714, gains):
                    if gain > 0.10:
                        painter.setPen(QPen(T.tint(T.ACCENT, 55 + 105 * gain), 1.0 + gain))
                        painter.drawLine(point, self._speaker_point(speaker))
        for name in sorted(self.stems, key=lambda n: (n == self.active_stem_name, self.placements[n].z)):
            self._draw_source(painter, name)
        for key, projection in self.projections.items():
            self._draw_projection(painter, key, projection)
        painter.end()

    def _projection_nodes(self, p: SpatialPlacement):
        if p.is_muted:
            return
        if p.volume_gain > 0:
            for side, x in self._nodes(p):
                yield side, *self._get_node_positions(x, p.y, p.z)
        elif p.lfe_send > 0:
            lfe = next(s for s in SPEAKER_COORDINATES_714 if s.is_lfe)
            anchor = self._speaker_point(lfe) + QPointF(0, 17)
            yield "LFE", anchor, anchor

    def _draw_projection(self, painter: QPainter, key: str, p: SpatialPlacement) -> None:
        ev = self._event_by_stem.get(key.removesuffix("::micro"))
        color = QColor(LANE_COLORS[event_row(ev)] if ev else T.WARM)
        for side, floor, point in self._projection_nodes(p):
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color, 1, Qt.DotLine))
            if ev and side != "LFE":
                sign = -1 if side == "L" else 1
                x1 = sign*abs(ev.x) if p.is_stereo else ev.x
                x2 = sign*abs(ev.end_x) if p.is_stereo else ev.end_x
                start = self._get_node_positions(x1, ev.y, ev.z)[1]
                end = self._get_node_positions(x2, ev.end_y, ev.end_z)[1]
                painter.drawLine(start, end)
                painter.drawEllipse(end, 3.0, 3.0)
            if p.z > .05:
                painter.drawLine(floor, point)
            # Losango e ponto central distinguem um envio breve de uma fonte editável.
            size = 8.0
            shape = QPolygonF([point + QPointF(0, -size), point + QPointF(size, 0),
                               point + QPointF(0, size), point + QPointF(-size, 0)])
            painter.setPen(QPen(color, 1.8))
            painter.setBrush(QColor(T.CANVAS))
            painter.drawPolygon(shape)
            painter.setBrush(color)
            painter.drawEllipse(point, 2.0, 2.0)

    def _projection_at(self, pos: QPointF) -> str | None:
        for key, p in self.projections.items():
            for _, _, point in self._projection_nodes(p):
                if math.hypot(pos.x()-point.x(), pos.y()-point.y()) <= 10:
                    return key
        return None

    def event(self, event) -> bool:
        if event.type() == QEvent.ToolTip:
            key = self._projection_at(QPointF(event.pos()))
            if key:
                ev = self._event_by_stem.get(key.removesuffix("::micro"))
                tip = event_details(ev) if ev else "Projeção de microcoreografia"
                QToolTip.showText(event.globalPos(), tip, self)
                return True
        return super().event(event)

    def _draw_speakers(self, painter: QPainter) -> None:
        for s in SPEAKER_COORDINATES_714:
            anchor = self._speaker_point(s)
            # Etiquetas ficam fora das posições de ancoragem, inclusive FC com voz central.
            offset = (-19.0 if s.code in ("FL", "FC", "FR") else
                      17.0 if s.code in ("BL", "BR") else 0.0)
            pt = anchor + QPointF(0, offset)
            color = T.COOL if s.z else T.LINE
            if s.is_lfe:
                color = T.WARM
            if s.is_lfe and self.sub_vu and not self.reduced_motion:
                painter.setPen(QPen(T.tint(T.WARM, 120), 1.4))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(pt, 17 + min(1, self.sub_vu) * 8, 17 + min(1, self.sub_vu) * 8)
            rect = QRectF(pt.x()-16, pt.y()-10, 32, 20)
            painter.setPen(QPen(QColor(color), 1, Qt.DashLine if s.z else Qt.SolidLine))
            painter.setBrush(QColor(T.PANEL_ALT))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(T.WARM if s.is_lfe else T.INK))
            painter.setFont(QFont(T.MONO, 8))
            painter.drawText(rect, Qt.AlignCenter, s.code)

    def _draw_source(self, painter: QPainter, name: str) -> None:
        p = self.placements[name]
        active = name == self.active_stem_name
        hovered = bool(self.hovered_stem_info and self.hovered_stem_info[0] == name)
        vu = self.stems_vu.get(name, self.stems_vu.get(p.source_stem_name or name, 0.0))
        muted = p.is_muted or p.volume_gain <= 0
        level = 0.0 if muted or self.reduced_motion else min(1.0, max(0.0, vu))
        radius = self.get_visual_radius(p.z, level)
        nodes = self._nodes(p)
        points = [self._get_node_positions(x, p.y, p.z) for _, x in nodes]
        color = QColor(self.stems[name].color_hex)
        if len(points) == 2:
            painter.setPen(QPen(T.tint(color, 165 if active else 70), 1.2, Qt.DashLine))
            painter.drawLine(points[0][1], points[1][1])
        for (side, _), (floor, top) in zip(nodes, points):
            self._draw_single_puck(painter, floor, top, radius, p.z, level, color,
                                   active, hovered, side if len(nodes) == 2 else None, muted)
        if active or hovered:
            cx = sum(pair[1].x() for pair in points) / len(points)
            top_y = points[0][1].y()
            painter.setFont(QFont(T.BODY, 9, QFont.DemiBold))
            text = self.stems[name].display_name + ("  /  Mudo" if muted else f"  /  Z {round(p.z * 100)}%")
            width = min(self.width()-8, painter.fontMetrics().horizontalAdvance(text) + 16)
            x, y = cx-width/2, top_y-radius-24
            if top_y < self.height() * 0.20 and len(points) == 1:
                x, y = cx+radius+9, top_y-11
            rect = QRectF(max(4, min(x, self.width()-width-4)), max(3, y), width, 21)
            painter.setPen(QPen(QColor(T.ACCENT if active else T.LINE), 1))
            painter.setBrush(QColor(T.CANVAS))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(T.INK))
            painter.drawText(rect, Qt.AlignCenter, painter.fontMetrics().elidedText(text, Qt.ElideRight, int(width)-6))

    def _draw_single_puck(self, painter: QPainter, ground_pt: QPointF, sphere_pt: QPointF,
                          radius: float, z: float, vu_val: float, base_color: QColor,
                          is_active: bool, is_hovered: bool, puck_side_badge: str | None,
                          is_muted: bool = False) -> None:
        # Apenas preenchimentos sólidos no hot path de Shiboken 6.12.
        if z > 0.03:
            painter.setPen(QPen(QColor(T.MUTED), 1, Qt.DotLine))
            painter.drawLine(ground_pt, sphere_pt)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(ground_pt, 5.0, 2.0)
        if vu_val > 0.04:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(T.tint(base_color, 100), 1.0))
            painter.drawEllipse(sphere_pt, radius+2.0+vu_val*4.0, radius+2.0+vu_val*4.0)
        color = QColor(T.LINE) if is_muted else base_color
        painter.setPen(QPen(QColor(T.INK) if is_active or is_hovered else color, 2.0 if is_active else 1.0))
        painter.setBrush(color if is_active or is_hovered else QColor(T.PANEL_ALT))
        painter.drawEllipse(sphere_pt, radius, radius)
        if puck_side_badge or is_muted:
            painter.setFont(QFont(T.MONO, 8, QFont.DemiBold))
            if is_active or is_hovered:
                text = T.DARK_TEXT if color.lightnessF() > 0.46 else T.INK
            else:
                text = T.INK
            painter.setPen(QColor(text))
            painter.drawText(QRectF(sphere_pt.x()-radius, sphere_pt.y()-radius, 2*radius, 2*radius),
                             Qt.AlignCenter, "M" if is_muted else puck_side_badge)

    def _find_stem_at_pos(self, pos: QPointF) -> tuple[str, str] | None:
        selected = None
        shortest = float("inf")
        for name in self.stems:
            p = self.placements[name]
            for side, x in self._nodes(p):
                point = self._get_node_positions(x, p.y, p.z)[1]
                d = math.hypot(pos.x()-point.x(), pos.y()-point.y())
                if d < shortest and d <= max(22.0, self.get_visual_radius(p.z)+8.0):
                    shortest, selected = d, (name, side)
        return selected

    def _move(self, name: str, x: float, y: float, z: float) -> None:
        if name in self.stems:
            self.update_placement(name, x, y, z)
            self.placement_changed.emit(name, x, y, z)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._projection_at(event.position()):
            event.accept()
            return
        target = self._find_stem_at_pos(event.position())
        if target:
            self.set_active_stem(target[0])
            if event.button() == Qt.LeftButton:
                self._is_dragging = True
                self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        name = self.active_stem_name
        if self._is_dragging and name in self.placements:
            p = self.placements[name]
            x, y = self._widget_to_room_coords(pos.x(), pos.y()+p.z*34)
            self._move(name, max(0.10, abs(x)) if p.is_stereo else x, y, p.z)
            return
        if self._projection_at(pos):
            self.hovered_stem_info = None
            self.setCursor(Qt.WhatsThisCursor)
            self.update()
            return
        target = self._find_stem_at_pos(pos)
        self.setCursor(Qt.OpenHandCursor if target else Qt.ArrowCursor)
        if target != self.hovered_stem_info:
            self.hovered_stem_info = target
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._is_dragging = False
        self.setCursor(Qt.OpenHandCursor if self._find_stem_at_pos(event.position()) else Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._projection_at(event.position()):
            event.accept()
            return
        target = self._find_stem_at_pos(event.position())
        if target and event.button() == Qt.LeftButton:
            self.toggle_stereo_mirror(target[0])

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._projection_at(event.position()):
            event.accept()
            return
        target = self._find_stem_at_pos(event.position())
        name = target[0] if target else self.active_stem_name
        if name in self.placements:
            self.set_active_stem(name)
            p = self.placements[name]
            self._move(name, p.x, p.y, max(0.0, min(1.0, p.z + event.angleDelta().y()/2400)))
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key, name = event.key(), self.active_stem_name
        if key == Qt.Key_Space:
            self.playback_toggle_requested.emit()
        elif key in (Qt.Key_Left, Qt.Key_Right):
            self.seek_requested.emit(5.0 if key == Qt.Key_Right else -5.0)
        elif key == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
            self.paste_requested.emit()
        elif name and name in self.placements:
            p = self.placements[name]
            if key == Qt.Key_D:
                self.toggle_stereo_mirror(name)
            elif key == Qt.Key_0:
                self._move(name, 0.0, 0.0, 0.0)
            elif key in (Qt.Key_Up, Qt.Key_Down):
                self._move(name, p.x, p.y, max(0.0, min(1.0, p.z + (0.05 if key == Qt.Key_Up else -0.05))))
            elif key == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                self.copy_requested.emit(name)
            elif key in (Qt.Key_Delete, Qt.Key_Backspace) and "::" in name:
                self.delete_requested.emit(name)
            else:
                super().keyPressEvent(event)
                return
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def contextMenuEvent(self, event) -> None:
        if self._projection_at(QPointF(event.pos())):
            event.accept()
            return
        target = self._find_stem_at_pos(QPointF(event.pos()))
        name = target[0] if target else self.active_stem_name
        menu = QMenu(self)
        if name in self.placements:
            menu.addAction("Espelhar em estéreo", lambda: self.toggle_stereo_mirror(name))
            menu.addAction("Copiar posição", lambda: self.copy_requested.emit(name))
            menu.addAction("Duplicar fonte", lambda: self.duplicate_requested.emit(name))
            menu.addAction("Centralizar", lambda: self._move(name, 0.0, 0.0, 0.0))
            if "::" in name:
                menu.addAction("Excluir cópia", lambda: self.delete_requested.emit(name))
        menu.addAction("Colar fonte", self.paste_requested.emit)
        menu.exec(event.globalPos())
