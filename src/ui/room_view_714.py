"""
AtmosSplit — Planta Interativa 2D / 3D da Sala 7.1.4
Mostra o ponto de escuta, a Soundbar JBL Bar 1000, satélites e drivers de teto.
Suporta:
- Espelhamento estéreo (is_stereo) com nós gêmeos (L e R) perfeitamente simétricos e ponte estéreo
- Arraste sincronizado onde mover um lado espelha instantaneamente o outro
- Seleção e controle dinâmico de altura Z via scroll do mouse
- Visualização tridimensional pelo raio do círculo (maior raio = mais alto/perto do teto)
- Duplo clique ou tecla 'D' para alternar espelhamento estéreo
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QLinearGradient,
    QRadialGradient,
    QPainterPath,
    QMouseEvent,
    QWheelEvent,
    QCursor,
)
from PySide6.QtWidgets import QWidget

from ..spatial.vbap_engine import SPEAKER_COORDINATES_714, SpeakerPosition714, VBAP714Engine
from ..spatial.auto_director import SpatialPlacement
from ..separation.stem_engine import StemTrack


class RoomView714(QWidget):
    """
    Widget gráfico renderizando a sala de audição 7.1.4.
    Permite selecionar bolinhas clicando nelas e ajustar a altura sonora Z usando a roda do mouse.
    Oferece nós gêmeos espelhados (L e R) para instrumentos em modo estéreo surround.
    """
    placement_changed = Signal(str, float, float, float)
    stereo_toggled = Signal(str, bool)
    stem_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(480, 440)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.vbap = VBAP714Engine()
        self.stems: Dict[str, StemTrack] = {}
        self.placements: Dict[str, SpatialPlacement] = {}
        self.active_stem_name: Optional[str] = None
        self.hovered_stem_info: Optional[Tuple[str, str]] = None  # (stem_name, "L"|"R"|"C")
        self._is_dragging: bool = False
        self._drag_puck_side: str = "C"  # "L", "R", ou "C"

        # VU Meters reativos em tempo real
        self.stems_vu: Dict[str, float] = {}
        self.sub_vu: float = 0.0

        # Paleta estética Hallmark (Dark Neutro, alto contraste, sem roxo genérico)
        self.color_bg = QColor("#0D0E11")
        self.color_grid = QColor("#1A1D24")
        self.color_walls = QColor("#262A34")
        self.color_listener = QColor("#4A5568")
        self.color_soundbar = QColor("#2D3748")
        self.color_surround = QColor("#232936")
        self.color_ceiling_ring = QColor(255, 255, 255, 28)
        self.color_text_sec = QColor("#718096")

    def set_stems_and_placements(self, stems: List[StemTrack], placements: Dict[str, SpatialPlacement]):
        """Atualiza a lista de instrumentos e seus posicionamentos espaciais."""
        self.stems = {s.name: s for s in stems}
        self.placements = placements
        if stems and (self.active_stem_name not in self.stems):
            self.active_stem_name = stems[0].name
        self.update()

    def set_active_stem(self, stem_name: str):
        """Seleciona o instrumento ativo."""
        if stem_name in self.stems:
            self.active_stem_name = stem_name
            self.stem_selected.emit(stem_name)
            self.update()

    def update_placement(self, stem_name: str, x: float, y: float, z: float, is_stereo: Optional[bool] = None):
        """Atualiza a posição de um instrumento e redesenha."""
        if stem_name in self.placements:
            plc = self.placements[stem_name]
            plc.x = x
            plc.y = y
            plc.z = z
            if is_stereo is not None:
                plc.is_stereo = is_stereo
            self.update()

    def toggle_stereo_mirror(self, stem_name: str):
        """Alterna espelhamento estéreo para o instrumento."""
        if stem_name in self.placements:
            plc = self.placements[stem_name]
            plc.is_stereo = not plc.is_stereo
            if plc.is_stereo and abs(plc.x) < 0.20:
                plc.x = 0.60
            self.stereo_toggled.emit(stem_name, plc.is_stereo)
            self.placement_changed.emit(stem_name, plc.x, plc.y, plc.z)
            self.update()

    def set_vu_levels(self, stems_vu: Dict[str, float], sub_vu: float):
        """Atualiza os medidores VU instantâneos para animação de pulsação."""
        self.stems_vu = stems_vu
        self.sub_vu = sub_vu
        self.update()

    # --- Cálculo de Raio Visual & Perspectiva 3D ---
    @staticmethod
    def get_visual_radius(z: float, vu: float = 0.0) -> float:
        """
        Calcula o raio visual do círculo proporcional à altura Z no espaço sonoro:
        - z = 0.0 (chão/ouvido): raio base de 11.0 px
        - z = 1.0 (teto surround): raio base de 33.0 px
        Aumento de 3x no raio, comunicando instantaneamente elevação tridimensional.
        """
        base_r = 11.0 + z * 22.0
        return base_r + vu * 3.5

    # --- Conversão de Coordenadas ---
    def _room_to_widget_coords(self, x: float, y: float) -> QPointF:
        """Converte coordenadas [-1, 1] do plano da sala para pixels do widget."""
        w = self.width()
        h = self.height()
        margin = 52.0
        center_x = w / 2.0
        center_y = h / 2.0
        scale_x = (w - 2.0 * margin) / 2.0
        scale_y = (h - 2.0 * margin) / 2.0

        px = center_x + x * scale_x
        py = center_y - y * scale_y
        return QPointF(px, py)

    def _widget_to_room_coords(self, px: float, py: float) -> Tuple[float, float]:
        """Converte pixels do widget para coordenadas normalizadas [-1, 1]."""
        w = self.width()
        h = self.height()
        margin = 52.0
        center_x = w / 2.0
        center_y = h / 2.0
        scale_x = (w - 2.0 * margin) / 2.0
        scale_y = (h - 2.0 * margin) / 2.0

        rx = (px - center_x) / scale_x
        ry = -(py - center_y) / scale_y
        return max(-1.0, min(1.0, rx)), max(-1.0, min(1.0, ry))

    def _get_node_positions(self, x_or_plc, y: Optional[float] = None, z: Optional[float] = None) -> Tuple[QPointF, QPointF]:
        """Retorna (ponto_no_chão, ponto_flutuante_da_esfera), aceitando SpatialPlacement ou coordenadas (x, y, z)."""
        if isinstance(x_or_plc, SpatialPlacement):
            rx, ry, rz = x_or_plc.x, x_or_plc.y, x_or_plc.z
        else:
            rx, ry, rz = float(x_or_plc), float(y or 0.0), float(z or 0.0)
        ground_pt = self._room_to_widget_coords(rx, ry)
        y_lift = rz * 18.0
        sphere_pt = QPointF(ground_pt.x(), ground_pt.y() - y_lift)
        return ground_pt, sphere_pt

    # --- Pintura / Renderização ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Fundo da Sala Acústica
        painter.fillRect(0, 0, w, h, self.color_bg)

        # 2. Grade de Distância Acústica
        pen_grid = QPen(self.color_grid, 1.0, Qt.DotLine)
        painter.setPen(pen_grid)

        center = self._room_to_widget_coords(0.0, 0.0)
        radius_max = min(w, h) / 2.0 - 52.0
        for r_factor in [0.33, 0.66, 1.0]:
            r_px = radius_max * r_factor
            painter.drawEllipse(center, r_px, r_px)

        painter.drawLine(int(center.x()), 25, int(center.x()), h - 25)
        painter.drawLine(25, int(center.y()), w - 25, int(center.y()))

        # 3. Desenhar Caixas Físicas da JBL Bar 1000MK2 e Subwoofer
        self._draw_speakers(painter)

        # 4. Desenhar Raios de Energia Acústica do Instrumento Ativo
        if self.active_stem_name and self.active_stem_name in self.placements:
            self._draw_acoustic_energy_rays(painter, self.active_stem_name)

        # 5. Ouvinte no Centro (Ponto de Escuta)
        self._draw_listener(painter, center)

        # 6. Desenhar Instrumentos com Projeção 3D de Altura e Suporte a Nós Estéreo Gêmeos
        self._draw_stem_nodes(painter)

        # 7. Dica Visual no Rodapé
        self._draw_canvas_hints(painter, w, h)

    def _draw_canvas_hints(self, painter: QPainter, w: int, h: int):
        painter.setFont(QFont("sans-serif", 8))
        painter.setPen(QColor("#718096"))
        hint_text = "💡 Clique na bolinha para mover • Scroll do Mouse = Altura Z (Raio) • Duplo clique ou 'D' = Espelhar Estéreo (L/R)"
        painter.drawText(QRectF(10, h - 22, w - 20, 18), Qt.AlignCenter, hint_text)

    def _draw_speakers(self, painter: QPainter):
        """Renderiza a Soundbar Frontal, Satélites e Drivers Superiores de Teto."""
        font = QFont("sans-serif", 8, QFont.Medium)
        painter.setFont(font)

        # Soundbar Frontal (FL, Center, FR)
        p_fl = self._room_to_widget_coords(-0.7, 1.0)
        p_fc = self._room_to_widget_coords(0.0, 1.0)
        p_fr = self._room_to_widget_coords(0.7, 1.0)

        bar_rect = QRectF(p_fl.x() - 10, p_fc.y() - 12, (p_fr.x() - p_fl.x()) + 20, 24)
        painter.setPen(QPen(QColor("#3A4150"), 1.5))
        painter.setBrush(QBrush(self.color_soundbar))
        painter.drawRoundedRect(bar_rect, 6.0, 6.0)

        painter.setPen(QColor("#A0AEC0"))
        painter.drawText(bar_rect, Qt.AlignCenter, "JBL BAR 1000 (Frontal L / C / R)")

        # Subwoofer com pulsação LFE
        p_sub = self._room_to_widget_coords(-0.95, 0.95)
        if self.sub_vu > 0.05:
            pulse_radius = 16.0 + self.sub_vu * 24.0
            pulse_alpha = int(min(220, self.sub_vu * 255))
            painter.setPen(QPen(QColor(255, 61, 0, pulse_alpha), 1.5, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(p_sub, pulse_radius, pulse_radius)
            if self.sub_vu > 0.3:
                painter.drawEllipse(p_sub, pulse_radius + 8.0, pulse_radius + 8.0)

        sub_rect = QRectF(p_sub.x() - 14, p_sub.y() - 14, 28, 28)
        painter.setPen(QPen(QColor("#E53E3E"), 1.5))
        painter.setBrush(QBrush(QColor("#2D1B1B")))
        painter.drawRoundedRect(sub_rect, 4.0, 4.0)
        painter.setPen(QColor("#FEB2B2"))
        painter.drawText(sub_rect, Qt.AlignCenter, "SUB")

        # Satélites Traseiros (BL, BR)
        for (code, label, x, y) in [("BL", "Satélite Esq", -0.7, -1.0), ("BR", "Satélite Dir", 0.7, -1.0)]:
            pt = self._room_to_widget_coords(x, y)
            rect = QRectF(pt.x() - 20, pt.y() - 10, 40, 20)
            painter.setPen(QPen(QColor("#4A5568"), 1.2))
            painter.setBrush(QBrush(self.color_surround))
            painter.drawRoundedRect(rect, 4.0, 4.0)
            painter.setPen(QColor("#A0AEC0"))
            painter.drawText(rect, Qt.AlignCenter, code)

        # Surrounds Laterais (SL, SR)
        for (code, x, y) in [("SL", -1.0, 0.0), ("SR", 1.0, 0.0)]:
            pt = self._room_to_widget_coords(x, y)
            rect = QRectF(pt.x() - 12, pt.y() - 16, 24, 32)
            painter.setPen(QPen(QColor("#4A5568"), 1.2))
            painter.setBrush(QBrush(self.color_surround))
            painter.drawRoundedRect(rect, 4.0, 4.0)
            painter.setPen(QColor("#A0AEC0"))
            painter.drawText(rect, Qt.AlignCenter, code)

        # 4 Drivers de Altura no Teto (TFL, TFR, TBL, TBR)
        painter.setPen(QPen(self.color_ceiling_ring, 1.5, Qt.DashLine))
        painter.setBrush(QBrush(QColor(66, 153, 225, 14)))
        for (code, x, y) in [("TFL", -0.6, 0.6), ("TFR", 0.6, 0.6), ("TBL", -0.6, -0.6), ("TBR", 0.6, -0.6)]:
            pt = self._room_to_widget_coords(x, y)
            painter.drawEllipse(pt, 24.0, 24.0)
            painter.setPen(QColor("#63B3ED"))
            painter.drawText(QRectF(pt.x() - 16, pt.y() - 10, 32, 20), Qt.AlignCenter, code)
            painter.setPen(QPen(self.color_ceiling_ring, 1.5, Qt.DashLine))

    def _draw_listener(self, painter: QPainter, center: QPointF):
        """Ponto de escuta central (sofá do ouvinte)."""
        painter.setPen(Qt.NoPen)
        grad = QRadialGradient(center, 28)
        grad.setColorAt(0.0, QColor(99, 179, 237, 45))
        grad.setColorAt(1.0, QColor(99, 179, 237, 0))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(center, 28, 28)

        painter.setPen(QPen(QColor("#63B3ED"), 2.0))
        painter.setBrush(QBrush(QColor("#1A202C")))
        painter.drawEllipse(center, 9, 9)

        painter.setPen(QColor("#718096"))
        painter.setFont(QFont("sans-serif", 7))
        painter.drawText(QRectF(center.x() - 30, center.y() + 11, 60, 16), Qt.AlignCenter, "OUVINTE")

    def _draw_acoustic_energy_rays(self, painter: QPainter, stem_name: str):
        """Raios acústicos VBAP 3D ligando o instrumento ativo aos alto-falantes excitados."""
        plc = self.placements.get(stem_name)
        if not plc:
            return

        if plc.is_stereo:
            dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
            gains_l = self.vbap.calculate_gains(-dist_x, plc.y, plc.z, plc.spread, plc.lfe_send)
            gains_r = self.vbap.calculate_gains(dist_x, plc.y, plc.z, plc.spread, plc.lfe_send)
            _, sphere_pt_l = self._get_node_positions(-dist_x, plc.y, plc.z)
            _, sphere_pt_r = self._get_node_positions(dist_x, plc.y, plc.z)

            # Raios do lado esquerdo
            for spk in SPEAKER_COORDINATES_714:
                gl = gains_l[spk.channel_index]
                if gl > 0.08:
                    spk_pt = self._room_to_widget_coords(spk.x, spk.y)
                    alpha = int(min(255, gl * 220))
                    color = QColor(0, 229, 255, alpha) if not spk.is_lfe else QColor(255, 61, 0, alpha)
                    painter.setPen(QPen(color, max(1.0, gl * 3.0), Qt.SolidLine))
                    painter.drawLine(sphere_pt_l, spk_pt)

            # Raios do lado direito
            for spk in SPEAKER_COORDINATES_714:
                gr = gains_r[spk.channel_index]
                if gr > 0.08:
                    spk_pt = self._room_to_widget_coords(spk.x, spk.y)
                    alpha = int(min(255, gr * 220))
                    color = QColor(0, 229, 255, alpha) if not spk.is_lfe else QColor(255, 61, 0, alpha)
                    painter.setPen(QPen(color, max(1.0, gr * 3.0), Qt.SolidLine))
                    painter.drawLine(sphere_pt_r, spk_pt)
        else:
            gains = self.vbap.calculate_gains(plc.x, plc.y, plc.z, plc.spread, plc.lfe_send)
            _, sphere_pt = self._get_node_positions(plc.x, plc.y, plc.z)

            for spk in SPEAKER_COORDINATES_714:
                gain = gains[spk.channel_index]
                if gain > 0.08:
                    spk_pt = self._room_to_widget_coords(spk.x, spk.y)
                    alpha = int(min(255, gain * 240))
                    color = QColor(0, 229, 255, alpha) if not spk.is_lfe else QColor(255, 61, 0, alpha)
                    pen = QPen(color, max(1.0, gain * 3.5), Qt.SolidLine)
                    painter.setPen(pen)
                    painter.drawLine(sphere_pt, spk_pt)

    def _draw_stem_nodes(self, painter: QPainter):
        """
        Renderiza cada instrumento ordenado por altura Z, suportando nós simples ou nós gêmeos
        espelhados (L e R) com ponte estéreo conectada.
        """
        sorted_stems = sorted(
            self.stems.items(),
            key=lambda item: self.placements.get(item[0], SpatialPlacement(item[0], 0, 0, 0, 0, 0, 1)).z
        )

        for name, stem in sorted_stems:
            plc = self.placements.get(name, SpatialPlacement(name, 0, 0, 0, 0.2, 0, 1))
            is_active = (name == self.active_stem_name)
            is_hovered = (self.hovered_stem_info is not None and self.hovered_stem_info[0] == name)
            base_color = QColor(stem.color_hex)
            vu_val = self.stems_vu.get(name, 0.0)
            radius = self.get_visual_radius(plc.z, vu_val)

            if plc.is_stereo:
                dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                ground_l, sphere_l = self._get_node_positions(-dist_x, plc.y, plc.z)
                ground_r, sphere_r = self._get_node_positions(dist_x, plc.y, plc.z)

                # Desenhar Ponte Estéreo conectando os dois lados
                self._draw_stereo_bridge(painter, sphere_l, sphere_r, base_color, is_active, is_hovered)

                # Desenhar Nós L e R
                self._draw_single_puck(painter, ground_l, sphere_l, radius, plc.z, vu_val, base_color, is_active, is_hovered, "L")
                self._draw_single_puck(painter, ground_r, sphere_r, radius, plc.z, vu_val, base_color, is_active, is_hovered, "R")

                # Badge Central e Rótulo
                center_pt = QPointF((sphere_l.x() + sphere_r.x()) / 2.0, (sphere_l.y() + sphere_r.y()) / 2.0)
                if is_active:
                    painter.setFont(QFont("sans-serif", 7, QFont.Bold))
                    badge_text = f"🪞 ESTÉREO 7.1.4 ({int(round(plc.z * 100))}%)"
                    badge_w = 115.0
                    badge_rect = QRectF(center_pt.x() - badge_w / 2.0, center_pt.y() - radius - 20.0, badge_w, 15.0)

                    painter.setPen(QPen(QColor("#00E5FF"), 1.0))
                    painter.setBrush(QBrush(QColor(15, 20, 30, 220)))
                    painter.drawRoundedRect(badge_rect, 3.0, 3.0)

                    painter.setPen(QColor("#00E5FF"))
                    painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

                # Nome do instrumento abaixo de cada lado ou centralizado
                painter.setFont(QFont("sans-serif", 8, QFont.Bold if is_active else QFont.Normal))
                painter.setPen(QColor("#FFFFFF") if is_active else QColor("#A0AEC0"))
                label_rect = QRectF(center_pt.x() - 70, center_pt.y() + radius + 4, 140, 16)
                painter.drawText(label_rect, Qt.AlignCenter, f"{stem.display_name} (L / R)")

            else:
                ground_pt, sphere_pt = self._get_node_positions(plc.x, plc.y, plc.z)
                self._draw_single_puck(painter, ground_pt, sphere_pt, radius, plc.z, vu_val, base_color, is_active, is_hovered, None)

                # Badge de Altura Ativa (quando selecionado)
                if is_active:
                    painter.setFont(QFont("sans-serif", 7, QFont.Bold))
                    badge_text = f"▲ TETO {int(round(plc.z * 100))}%" if plc.z > 0.05 else "● CHÃO (0%)"
                    badge_w = 70.0
                    badge_rect = QRectF(sphere_pt.x() - badge_w / 2.0, sphere_pt.y() - radius - 20.0, badge_w, 15.0)

                    painter.setPen(QPen(QColor("#00E5FF"), 1.0))
                    painter.setBrush(QBrush(QColor(15, 20, 30, 220)))
                    painter.drawRoundedRect(badge_rect, 3.0, 3.0)

                    painter.setPen(QColor("#00E5FF"))
                    painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

                # Rótulo com Nome do Instrumento
                painter.setFont(QFont("sans-serif", 8, QFont.Bold if is_active else QFont.Normal))
                painter.setPen(QColor("#FFFFFF") if is_active else QColor("#A0AEC0"))
                label_rect = QRectF(sphere_pt.x() - 60, sphere_pt.y() + radius + 3, 120, 16)
                painter.drawText(label_rect, Qt.AlignCenter, stem.display_name)

    def _draw_stereo_bridge(self, painter: QPainter, pt_l: QPointF, pt_r: QPointF, color: QColor, is_active: bool, is_hovered: bool):
        """Desenha a conexão de ponte estéreo cintilante entre o lado esquerdo e direito."""
        path = QPainterPath()
        path.moveTo(pt_l)
        # Curva suave para trás ou teto
        mid_x = (pt_l.x() + pt_r.x()) / 2.0
        mid_y = (pt_l.y() + pt_r.y()) / 2.0 - 12.0
        path.quadTo(mid_x, mid_y, pt_r.x(), pt_r.y())

        alpha = 180 if is_active else (120 if is_hovered else 60)
        pen = QPen(QColor(color.red(), color.green(), color.blue(), alpha), 1.8 if is_active else 1.2, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _draw_single_puck(
        self,
        painter: QPainter,
        ground_pt: QPointF,
        sphere_pt: QPointF,
        radius: float,
        z: float,
        vu_val: float,
        base_color: QColor,
        is_active: bool,
        is_hovered: bool,
        puck_side_badge: Optional[str]
    ):
        """Renderiza uma bolinha esférica individual com sombra, haste e realce de altura."""
        # 1. Projeção de Chão & Haste Vertical (Pseudo-3D)
        if z > 0.04:
            shadow_w = 12.0 + (1.0 - z) * 6.0
            shadow_h = shadow_w * 0.45
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
            painter.drawEllipse(ground_pt, shadow_w, shadow_h)

            pen_tether = QPen(QColor(255, 255, 255, int(80 + z * 120)), 1.2, Qt.DashLine)
            painter.setPen(pen_tether)
            painter.drawLine(ground_pt, sphere_pt)

        # 2. Anéis de Elevação ao Teto
        if z > 0.35:
            elev_alpha = int(z * 170)
            pen_elev = QPen(QColor(99, 179, 237, elev_alpha), 1.2, Qt.DashLine)
            painter.setPen(pen_elev)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(sphere_pt, radius + 5.0, radius + 5.0)
            if z > 0.75:
                painter.drawEllipse(sphere_pt, radius + 10.0, radius + 10.0)

        # 3. Pulsação Reativa de VU Meter no Nó
        if vu_val > 0.06:
            painter.setPen(Qt.NoPen)
            vu_halo = QRadialGradient(sphere_pt, radius + vu_val * 16.0)
            vu_halo.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), int(vu_val * 180)))
            vu_halo.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), 0))
            painter.setBrush(QBrush(vu_halo))
            painter.drawEllipse(sphere_pt, radius + vu_val * 16.0, radius + vu_val * 16.0)

        # 4. Halo de Seleção e Foco Ativo
        if is_active:
            painter.setPen(Qt.NoPen)
            halo = QRadialGradient(sphere_pt, radius + 14.0)
            halo.setColorAt(0.0, QColor(0, 229, 255, 120))
            halo.setColorAt(1.0, QColor(0, 229, 255, 0))
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(sphere_pt, radius + 14.0, radius + 14.0)

        # 5. Corpo da Esfera Sonora 3D com Gradiente de Volume
        grad_sphere = QRadialGradient(
            sphere_pt.x() - radius * 0.3,
            sphere_pt.y() - radius * 0.3,
            radius * 1.3
        )
        grad_sphere.setColorAt(0.0, base_color.lighter(135))
        grad_sphere.setColorAt(0.7, base_color)
        grad_sphere.setColorAt(1.0, base_color.darker(140))

        if is_active:
            painter.setPen(QPen(QColor("#00E5FF"), 2.5))
        elif is_hovered:
            painter.setPen(QPen(QColor("#FFFFFF"), 1.8))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 60), 1.0))

        painter.setBrush(QBrush(grad_sphere))
        painter.drawEllipse(sphere_pt, radius, radius)

        # 6. Letra de Lado (L/R) ou Porcentagem de Altura
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("sans-serif", 8, QFont.Bold))
        text_rect = QRectF(sphere_pt.x() - radius, sphere_pt.y() - radius, radius * 2, radius * 2)

        if puck_side_badge:
            painter.drawText(text_rect, Qt.AlignCenter, puck_side_badge)
        elif radius >= 16.0:
            pct_text = f"{int(round(z * 100))}%"
            painter.drawText(text_rect, Qt.AlignCenter, pct_text)

    # --- Interatividade do Mouse (Seleção, Arraste Espelhado e Scroll de Altura) ---
    def _find_stem_at_pos(self, pos: QPointF) -> Optional[Tuple[str, str]]:
        """
        Localiza o stem e o lado sob o cursor:
        Retorna (stem_name, "L"|"R"|"C") ou None.
        """
        clicked = None
        min_dist = float("inf")

        sorted_stems = sorted(
            self.stems.items(),
            key=lambda item: self.placements.get(item[0], SpatialPlacement(item[0], 0, 0, 0, 0, 0, 1)).z,
            reverse=True
        )

        for name, stem in sorted_stems:
            plc = self.placements.get(name)
            if not plc:
                continue
            vu_val = self.stems_vu.get(name, 0.0)
            radius = self.get_visual_radius(plc.z, vu_val)
            hit_bound = max(radius + 8.0, 22.0)

            if plc.is_stereo:
                dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                _, sphere_l = self._get_node_positions(-dist_x, plc.y, plc.z)
                _, sphere_r = self._get_node_positions(dist_x, plc.y, plc.z)

                d_l = math.hypot(pos.x() - sphere_l.x(), pos.y() - sphere_l.y())
                if d_l <= hit_bound and d_l < min_dist:
                    min_dist = d_l
                    clicked = (name, "L")

                d_r = math.hypot(pos.x() - sphere_r.x(), pos.y() - sphere_r.y())
                if d_r <= hit_bound and d_r < min_dist:
                    min_dist = d_r
                    clicked = (name, "R")
            else:
                _, sphere_pt = self._get_node_positions(plc.x, plc.y, plc.z)
                dist = math.hypot(pos.x() - sphere_pt.x(), pos.y() - sphere_pt.y())
                if dist <= hit_bound and dist < min_dist:
                    min_dist = dist
                    clicked = (name, "C")

        return clicked

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            target = self._find_stem_at_pos(pos)

            if target:
                stem_name, side = target
                self.active_stem_name = stem_name
                self._is_dragging = True
                self._drag_puck_side = side
                self.setCursor(Qt.ClosedHandCursor)
                self.stem_selected.emit(stem_name)
                self.update()
        elif event.button() == Qt.RightButton:
            pos = event.position()
            target = self._find_stem_at_pos(pos)
            if target:
                stem_name, _ = target
                self.toggle_stereo_mirror(stem_name)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            target = self._find_stem_at_pos(pos)
            if target:
                stem_name, _ = target
                self.toggle_stereo_mirror(stem_name)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        try:
            pos = event.position()

            if self._is_dragging and self.active_stem_name and self.active_stem_name in self.placements:
                plc = self.placements[self.active_stem_name]
                y_lift = plc.z * 18.0
                rx, ry = self._widget_to_room_coords(pos.x(), pos.y() + y_lift)

                if plc.is_stereo:
                    new_x = max(0.10, min(1.0, abs(rx)))
                    new_y = ry
                else:
                    new_x = rx
                    new_y = ry

                # Throttling inteligente: só propaga se houve deslocamento real (> 0.005)
                dx = new_x - plc.x
                dy = new_y - plc.y
                if (dx * dx + dy * dy) > 0.000025:
                    plc.x = new_x
                    plc.y = new_y
                    self.placement_changed.emit(self.active_stem_name, plc.x, plc.y, plc.z)
                    self.update()
            else:
                hovered = self._find_stem_at_pos(pos)
                if hovered != self.hovered_stem_info:
                    self.hovered_stem_info = hovered
                    if hovered:
                        self.setCursor(Qt.PointingHandCursor)
                    else:
                        self.setCursor(Qt.ArrowCursor)
                    self.update()
        except Exception as e:
            # Blindagem absoluta contra crash de mouse
            pass

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            if self.hovered_stem_info:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent):
        """
        Ajusta a ALTURA (Z) do instrumento (e o raio proporcional de visualização).
        Afeta ambos os lados no modo estéreo simultaneamente.
        """
        try:
            pos = event.position()
            target = self._find_stem_at_pos(pos)
            target_stem = target[0] if target else self.active_stem_name

            if target_stem and target_stem in self.placements:
                if target_stem != self.active_stem_name:
                    self.active_stem_name = target_stem
                    self.stem_selected.emit(target_stem)

                delta = event.angleDelta().y()
                if delta != 0:
                    step = (delta / 120.0) * 0.05
                    plc = self.placements[target_stem]
                    new_z = max(0.0, min(1.0, round(plc.z + step, 3)))
                    plc.z = new_z

                    self.placement_changed.emit(target_stem, plc.x, plc.y, plc.z)
                    self.update()
                    event.accept()
                    return
        except Exception:
            pass

        super().wheelEvent(event)
