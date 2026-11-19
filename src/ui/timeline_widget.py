"""
AtmosSplit — Spatial Timeline Widget (Automação Visual Profissional por Trechos)
Linha do tempo gráfica estilo DAW para automação espacial 7.1.4 Dolby Atmos.
Permite divisão rápida (split) no cursor, ajuste tátil de bordas por arraste (boundary dragging),
zoom milimétrico com régua adaptativa até escala de milissegundos, mini-mapa de navegação (bird's eye)
e acionamento com 1 clique do IA Maestro (arranjo musical autônomo).
Zero scrollbars do SO cobrindo os blocos e zero pop-ups modais intrusivos.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QEvent
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QMouseEvent,
    QCursor,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QInputDialog,
    QFrame,
)

from ..spatial.timeline_manager import SpatialTimelineManager, SpatialSection


class TimelineTrackCanvas(QWidget):
    """
    Área gráfica interativa da linha do tempo estilo DAW.
    Gerencia seu próprio viewport virtual (zoom e view_start_s) com renderização
    vetorial direta, régua temporal precisa, blocos de seções coloridos com
    arraste tátil de fronteiras e mini-mapa integrado de navegação.
    """
    section_clicked = Signal(str)
    section_double_clicked = Signal(str)
    seek_clicked = Signal(float)
    boundary_adjusted = Signal(int, float)

    RULER_HEIGHT = 22
    TRACK_HEIGHT = 46
    MINIMAP_HEIGHT = 14
    TOTAL_CANVAS_HEIGHT = 86

    def __init__(self, timeline_manager: SpatialTimelineManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.timeline_manager = timeline_manager
        self.current_time_s: float = 0.0

        # Viewport virtual
        self._zoom: float = 1.0
        self.view_start_s: float = 0.0

        # Estados de interação
        self.hovered_section_id: Optional[str] = None
        self.hovered_boundary_idx: Optional[int] = None
        self.is_dragging_boundary: bool = False
        self.drag_boundary_idx: int = -1
        self.is_scrubbing_playhead: bool = False
        self.is_dragging_minimap: bool = False

        self.setMinimumHeight(self.TOTAL_CANVAS_HEIGHT)
        self.setMaximumHeight(self.TOTAL_CANVAS_HEIGHT)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, val: float):
        self.set_zoom(val)

    @property
    def visible_duration_s(self) -> float:
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        return max(0.01, tot / self._zoom)

    @property
    def current_view_start(self) -> float:
        return self.view_start_s

    def set_view(self, zoom: float, view_start_s: float):
        self._zoom = max(1.0, min(128.0, float(zoom)))
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        vis = tot / self._zoom
        max_start = max(0.0, tot - vis)
        self.view_start_s = max(0.0, min(max_start, float(view_start_s)))
        self.update()

    def set_zoom(self, zoom: float, anchor_x: Optional[float] = None):
        old_zoom = self._zoom
        new_zoom = max(1.0, min(128.0, float(zoom)))
        if abs(new_zoom - old_zoom) < 1e-5:
            return

        w = max(1, self.width())
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        target_x = w / 2.0 if anchor_x is None else float(anchor_x)

        # Tempo no ponto de ancoragem antes do zoom
        old_vis = tot / old_zoom
        anchor_time = self.view_start_s + (target_x / w) * old_vis

        # Atualizar zoom e recentralizar em torno do anchor_time
        self._zoom = new_zoom
        new_vis = tot / new_zoom
        new_start = anchor_time - (target_x / w) * new_vis
        max_start = max(0.0, tot - new_vis)
        self.view_start_s = max(0.0, min(max_start, new_start))
        self.update()

    def set_playhead_time(self, time_s: float):
        """Atualiza a posição do playhead e redesenha se houver mudança visível."""
        if abs(self.current_time_s - time_s) > 0.01:
            self.current_time_s = max(0.0, float(time_s))
            self.update()

    # --- Funções de Projeção de Coordenadas ---
    def time_to_x(self, t: float) -> float:
        w = max(1, self.width())
        vis = self.visible_duration_s
        return (float(t) - self.view_start_s) * (w / vis)

    def x_to_time(self, x: float) -> float:
        w = max(1, self.width())
        vis = self.visible_duration_s
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        t = self.view_start_s + (float(x) / w) * vis
        return max(0.0, min(tot, t))

    def time_to_mini_x(self, t: float) -> float:
        w = max(1, self.width())
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        return float(t) * (w / tot)

    def mini_x_to_time(self, x: float) -> float:
        w = max(1, self.width())
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        return max(0.0, min(tot, (float(x) / w) * tot))

    @staticmethod
    def _ruler_step(visible_duration_s: float) -> float:
        """Determina o passo ótimo das marcações da régua com base na duração visível."""
        if visible_duration_s > 60:
            return 10.0
        elif visible_duration_s > 20:
            return 5.0
        elif visible_duration_s > 8:
            return 1.0
        elif visible_duration_s > 3:
            return 0.5
        elif visible_duration_s > 1:
            return 0.2
        elif visible_duration_s > 0.4:
            return 0.05
        elif visible_duration_s > 0.1:
            return 0.01
        else:
            return 0.001

    @staticmethod
    def _format_time(t: float, step: float) -> str:
        t = max(0.0, float(t))
        m = int(t // 60)
        s = t % 60
        if step >= 1.0:
            return f"{m:02d}:{int(s):02d}"
        elif step >= 0.1:
            return f"{m:02d}:{s:04.1f}"
        elif step >= 0.01:
            return f"{m:02d}:{s:05.2f}"
        else:
            return f"{m:02d}:{s:06.3f}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        tot_d = max(1.0, float(self.timeline_manager.total_duration_s))
        vis_d = self.visible_duration_s

        # Fundo mestre estilo DAW
        painter.fillRect(0, 0, w, h, QColor("#101318"))

        # --- 1. RÉGUA TEMPORAL (RULER: y=0 a y=22) ---
        ruler_h = self.RULER_HEIGHT
        painter.fillRect(0, 0, w, ruler_h, QColor("#151821"))
        painter.setPen(QPen(QColor("#262C38"), 1))
        painter.drawLine(0, ruler_h, w, ruler_h)

        step = self._ruler_step(vis_d)
        tick_start = math.floor(self.view_start_s / step) * step
        tick_end = min(tot_d, self.view_start_s + vis_d)

        painter.setFont(QFont("monospace", 8))
        cur_tick = tick_start
        while cur_tick <= tick_end + 1e-4:
            tx = self.time_to_x(cur_tick)
            if 0 <= tx <= w:
                painter.setPen(QPen(QColor("#718096"), 1))
                painter.drawLine(int(tx), ruler_h - 7, int(tx), ruler_h)
                # Submarcações menores se passo for grande
                painter.drawText(QPointF(tx + 4, ruler_h - 8), self._format_time(cur_tick, step))
            cur_tick += step

        # --- 2. TRILHA DE SEÇÕES (TRACK: y=23 a y=68) ---
        track_y = self.RULER_HEIGHT + 1
        track_h = self.TRACK_HEIGHT
        sections = self.timeline_manager.sections
        active_edit_id = self.timeline_manager.active_edit_section_id

        # Linha inferior da trilha
        painter.setPen(QPen(QColor("#202530"), 1))
        painter.drawLine(0, track_y + track_h, w, track_y + track_h)

        for sec in sections:
            x1 = self.time_to_x(sec.start_time_s)
            x2 = self.time_to_x(sec.end_time_s)

            if x2 < 0 or x1 > w:
                continue

            block_x = max(0.0, x1)
            block_w = max(4.0, min(float(w), x2) - block_x)
            block_rect = QRectF(block_x + 1, track_y + 2, block_w - 2, track_h - 4)

            is_active = (sec.id == active_edit_id)
            is_hovered = (sec.id == self.hovered_section_id)

            base_color = QColor(sec.color_hex if sec.color_hex else "#4299E1")
            alpha = 190 if is_active else (130 if is_hovered else 80)
            fill_color = QColor(base_color.red(), base_color.green(), base_color.blue(), alpha)

            # Preencher bloco com cantos ligeiramente arredondados
            painter.setBrush(QBrush(fill_color))
            if is_active:
                painter.setPen(QPen(QColor("#00E5FF"), 2))
            elif is_hovered:
                painter.setPen(QPen(QColor("#63B3ED"), 1.5))
            else:
                painter.setPen(QPen(QColor("#2D3748"), 1))

            painter.drawRoundedRect(block_rect, 4, 4)

            # Barra de destaque superior no bloco ativo
            if is_active:
                top_strip = QRectF(block_rect.left(), block_rect.top(), block_rect.width(), 3)
                painter.fillRect(top_strip, QColor("#00E5FF"))

            # Rótulo de texto do trecho
            if block_w > 36:
                painter.setFont(QFont("sans-serif", 9, QFont.Bold if is_active else QFont.Normal))
                painter.setPen(QPen(QColor("#FFFFFF" if is_active else "#E2E8F0")))

                label_text = sec.name
                if block_w > 120:
                    dur_s = sec.end_time_s - sec.start_time_s
                    label_text = f"{sec.name} ({dur_s:.1f}s)"

                # Clipar texto para não vazar
                painter.save()
                painter.setClipRect(block_rect.adjusted(6, 4, -6, -4))
                painter.drawText(
                    block_rect.adjusted(6, 4, -6, -4),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    label_text
                )
                painter.restore()

        # Desenhar linhas de fronteira arrastáveis (Boundary handles)
        for idx in range(len(sections) - 1):
            boundary_t = sections[idx].end_time_s
            bx = self.time_to_x(boundary_t)
            if 0 <= bx <= w:
                is_dragged = (self.is_dragging_boundary and self.drag_boundary_idx == idx)
                is_b_hover = (self.hovered_boundary_idx == idx)

                if is_dragged:
                    b_color = QColor("#00E5FF")
                    b_width = 3
                elif is_b_hover:
                    b_color = QColor("#ECC94B")
                    b_width = 2
                else:
                    b_color = QColor("#4A5568")
                    b_width = 1

                painter.setPen(QPen(b_color, b_width, Qt.DashLine if not (is_dragged or is_b_hover) else Qt.SolidLine))
                painter.drawLine(int(bx), track_y, int(bx), track_y + track_h)

                # Ponto ou indicador tátil de arraste
                if is_b_hover or is_dragged:
                    painter.setBrush(QBrush(b_color))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(QPointF(bx, track_y + track_h / 2.0), 4, 4)

        # --- 3. AGULHA DO PLAYHEAD (NEEDLE) ---
        px = self.time_to_x(self.current_time_s)
        if 0 <= px <= w:
            # Marcador triangular na régua
            painter.setBrush(QBrush(QColor("#00E5FF")))
            painter.setPen(Qt.NoPen)
            tri = QPainterPath()
            tri.moveTo(px - 5, 0)
            tri.lineTo(px + 5, 0)
            tri.lineTo(px, ruler_h - 2)
            tri.closeSubpath()
            painter.drawPath(tri)

            # Linha vertical brilhante descendo até o final da trilha
            painter.setPen(QPen(QColor("#00E5FF"), 1.8))
            painter.drawLine(int(px), ruler_h - 2, int(px), track_y + track_h)

        # --- 4. MINI-MAPA DE VISÃO GERAL INTEGRADO (y=71 a y=85) ---
        mini_y = track_y + track_h + 2
        mini_h = self.MINIMAP_HEIGHT
        painter.fillRect(0, mini_y, w, mini_h, QColor("#0A0C10"))
        painter.setPen(QPen(QColor("#1A202C"), 1))
        painter.drawRect(0, mini_y, w - 1, mini_h - 1)

        # Desenhar faixas de todas as seções no mini-mapa
        for sec in sections:
            mx1 = self.time_to_mini_x(sec.start_time_s)
            mx2 = self.time_to_mini_x(sec.end_time_s)
            mw = max(2.0, mx2 - mx1)
            b_col = QColor(sec.color_hex if sec.color_hex else "#4299E1")
            painter.fillRect(QRectF(mx1, mini_y + 1, mw, mini_h - 2), QColor(b_col.red(), b_col.green(), b_col.blue(), 100))

        # Viewport visível no mini-mapa
        vx1 = self.time_to_mini_x(self.view_start_s)
        vx2 = self.time_to_mini_x(self.view_start_s + vis_d)
        vw = max(6.0, vx2 - vx1)
        viewport_rect = QRectF(vx1, mini_y, vw, mini_h)

        painter.setBrush(QBrush(QColor(0, 229, 255, 35)))
        painter.setPen(QPen(QColor("#00E5FF"), 1.5))
        painter.drawRect(viewport_rect)

        # Mini agulha do playhead no mini-mapa
        mpx = self.time_to_mini_x(self.current_time_s)
        if 0 <= mpx <= w:
            painter.setPen(QPen(QColor("#ECC94B"), 1.5))
            painter.drawLine(int(mpx), mini_y, int(mpx), mini_y + mini_h)

    # --- Tratamento de Eventos do Mouse ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        x = event.position().x()
        y = event.position().y()
        w = max(1, self.width())

        # 1. Clique na régua (y <= 22) -> Scrubbing do playhead
        if y <= self.RULER_HEIGHT:
            self.is_scrubbing_playhead = True
            seek_t = self.x_to_time(x)
            self.current_time_s = seek_t
            self.update()
            self.seek_clicked.emit(seek_t)
            return

        # 2. Clique no Mini-Mapa (y >= 71) -> Posicionar viewport
        if y >= (self.RULER_HEIGHT + self.TRACK_HEIGHT + 2):
            self.is_dragging_minimap = True
            target_t = self.mini_x_to_time(x)
            new_start = target_t - self.visible_duration_s / 2.0
            tot = max(1.0, float(self.timeline_manager.total_duration_s))
            max_start = max(0.0, tot - self.visible_duration_s)
            self.view_start_s = max(0.0, min(max_start, new_start))
            self.update()
            return

        # 3. Clique nas proximidades de uma fronteira entre seções -> Arraste tátil
        boundary_idx = self._hit_test_boundary(x)
        if boundary_idx is not None:
            self.is_dragging_boundary = True
            self.drag_boundary_idx = boundary_idx
            self.setCursor(Qt.SizeHorCursor)
            self.update()
            return

        # 4. Clique no corpo da seção -> Seleção do trecho ativo
        sec_id = self._hit_test_section(x)
        if sec_id:
            self.timeline_manager.active_edit_section_id = sec_id
            self.update()
            self.section_clicked.emit(sec_id)

    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.position().x()
        y = event.position().y()

        # Scrubbing contínuo do playhead
        if self.is_scrubbing_playhead:
            seek_t = self.x_to_time(x)
            self.current_time_s = seek_t
            self.update()
            self.seek_clicked.emit(seek_t)
            return

        # Arraste de fronteira temporal
        if self.is_dragging_boundary and self.drag_boundary_idx >= 0:
            new_t = self.x_to_time(x)
            if self.timeline_manager.adjust_boundary(self.drag_boundary_idx, new_t):
                self.update()
                self.boundary_adjusted.emit(self.drag_boundary_idx, new_t)
            return

        # Arraste no mini-mapa
        if self.is_dragging_minimap:
            target_t = self.mini_x_to_time(x)
            new_start = target_t - self.visible_duration_s / 2.0
            tot = max(1.0, float(self.timeline_manager.total_duration_s))
            max_start = max(0.0, tot - self.visible_duration_s)
            self.view_start_s = max(0.0, min(max_start, new_start))
            self.update()
            return

        # Hover states
        if y >= (self.RULER_HEIGHT + self.TRACK_HEIGHT + 2):
            self.setCursor(Qt.PointingHandCursor)
            self.hovered_boundary_idx = None
            self.hovered_section_id = None
            self.update()
            return

        b_idx = self._hit_test_boundary(x)
        if b_idx is not None:
            self.hovered_boundary_idx = b_idx
            self.setCursor(Qt.SizeHorCursor)
            self.update()
        else:
            if self.hovered_boundary_idx is not None:
                self.hovered_boundary_idx = None
                self.update()
            self.setCursor(Qt.PointingHandCursor)
            s_id = self._hit_test_section(x)
            if s_id != self.hovered_section_id:
                self.hovered_section_id = s_id
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.is_scrubbing_playhead = False
        self.is_dragging_boundary = False
        self.is_dragging_minimap = False
        self.drag_boundary_idx = -1
        self.setCursor(Qt.PointingHandCursor)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        x = event.position().x()
        s_id = self._hit_test_section(x)
        if s_id:
            self.section_double_clicked.emit(s_id)

    def wheelEvent(self, event):
        # Ctrl + Wheel: Zoom anchored no cursor do mouse
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.25 if delta > 0 else (1.0 / 1.25)
            self.set_zoom(self._zoom * factor, anchor_x=event.position().x())
            event.accept()
            return

        # Wheel normal ou Shift + Wheel: Pan horizontal da timeline
        delta = event.angleDelta().x() if event.angleDelta().x() != 0 else event.angleDelta().y()
        tot = max(1.0, float(self.timeline_manager.total_duration_s))
        pan_amount = (self.visible_duration_s * 0.15) * (-1.0 if delta > 0 else 1.0)
        max_start = max(0.0, tot - self.visible_duration_s)
        self.view_start_s = max(0.0, min(max_start, self.view_start_s + pan_amount))
        self.update()
        event.accept()

    def _hit_test_boundary(self, mouse_x: float) -> Optional[int]:
        """Verifica se mouse_x está a menos de 6 pixels de alguma fronteira entre seções."""
        tol_px = 6.0
        sections = self.timeline_manager.sections
        for idx in range(len(sections) - 1):
            boundary_t = sections[idx].end_time_s
            bx = self.time_to_x(boundary_t)
            if abs(mouse_x - bx) <= tol_px:
                return idx
        return None

    def _hit_test_section(self, mouse_x: float) -> Optional[str]:
        """Retorna o ID da seção sob a coordenada mouse_x."""
        t = self.x_to_time(mouse_x)
        sec = self.timeline_manager.get_section_at_time(t)
        return sec.id if sec else None


class TimelineWidget(QWidget):
    """
    Widget completo da linha do tempo estilo DAW profissional.
    Integra controles de Trechos, botão do IA Maestro, zoom adaptativo,
    divisão sem pop-ups bloqueantes e navegação com zero obstrução.
    """
    section_selected = Signal(str)
    split_requested = Signal(float)
    section_renamed = Signal(str, str)
    section_removed = Signal(str)
    seek_requested = Signal(float)
    reanalyze_requested = Signal()

    def __init__(self, timeline_manager: SpatialTimelineManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.timeline_manager = timeline_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Barra superior com título, badge do trecho e botões de ação rápida
        bar_header = QHBoxLayout()
        bar_header.setSpacing(6)

        title = QLabel("AUTOMAÇÃO ESPACIAL POR TRECHOS")
        title.setStyleSheet("font-size: 11px; font-weight: bold; color: #00E5FF; letter-spacing: 0.5px;")
        bar_header.addWidget(title)

        self.lbl_active_info = QLabel("")
        self.lbl_active_info.setStyleSheet("font-size: 11px; color: #A0AEC0;")
        bar_header.addWidget(self.lbl_active_info)

        bar_header.addStretch()

        # Botão ✨ IA Maestro (Arranjo Musical Autônomo de Estúdio)
        self.btn_maestro = QPushButton("✨ IA Maestro")
        self.btn_maestro.setToolTip(
            "Analisa automaticamente a estrutura musical da faixa (intro, versos, build-ups, refrão e final)\n"
            "e aplica arranjo de estúdio Dolby Atmos 7.1.4 com vozes dinâmicas e envolvimento 360°."
        )
        self.btn_maestro.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1A365D, stop:1 #2B6CB0);
                color: #FFFFFF;
                border: 1px solid #4299E1;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2B6CB0, stop:1 #3182CE);
                border: 1px solid #63B3ED;
            }
        """)
        self.btn_maestro.clicked.connect(self.reanalyze_requested.emit)
        bar_header.addWidget(self.btn_maestro)

        # Botão Dividir no cursor (Split)
        self.btn_split = QPushButton("Dividir no Tempo Atual")
        self.btn_split.setObjectName("BtnPrimary")
        self.btn_split.setToolTip("Divide o trecho na posição atual do cursor de reprodução (Zero pop-ups).")
        self.btn_split.clicked.connect(self._on_split_clicked)
        bar_header.addWidget(self.btn_split)

        # Botão Renomear
        self.btn_rename = QPushButton("Renomear")
        self.btn_rename.setToolTip("Altera o nome do trecho selecionado (ex: Refrão, Verso 1, Ponte).")
        self.btn_rename.clicked.connect(self._on_rename_clicked)
        bar_header.addWidget(self.btn_rename)

        # Botão Excluir
        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setToolTip("Remove o trecho selecionado fundindo seu tempo com o trecho vizinho.")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        bar_header.addWidget(self.btn_delete)

        # Controles de Zoom
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedWidth(24)
        self.btn_zoom_out.setToolTip("Diminuir zoom (ver faixa mais ampla)")
        self.btn_zoom_out.clicked.connect(lambda: self._set_zoom(self.zoom / 1.5))
        bar_header.addWidget(self.btn_zoom_out)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(24)
        self.btn_zoom_in.setToolTip("Aumentar zoom (precisão até milissegundos)")
        self.btn_zoom_in.clicked.connect(lambda: self._set_zoom(self.zoom * 1.5))
        bar_header.addWidget(self.btn_zoom_in)

        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.setToolTip("Redefinir zoom para visualização completa da música")
        self.btn_zoom_reset.clicked.connect(lambda: self._set_zoom(1.0))
        bar_header.addWidget(self.btn_zoom_reset)

        layout.addLayout(bar_header)

        # Canvas gráfico profissional (Zero QScrollArea para eliminar bugs de escala e sobreposição)
        self.canvas = TimelineTrackCanvas(self.timeline_manager)
        self.canvas.section_clicked.connect(self._on_section_clicked)
        self.canvas.section_double_clicked.connect(self._on_rename_clicked)
        self.canvas.seek_clicked.connect(self.seek_requested)
        self.canvas.boundary_adjusted.connect(self._on_boundary_adjusted)
        layout.addWidget(self.canvas)

        self.setFocusPolicy(Qt.StrongFocus)
        self._refresh_status_labels()

    def set_current_playback_time(self, time_s: float):
        """Atualiza a posição do cursor na barra de tempo."""
        self.canvas.set_playhead_time(time_s)

    def _set_zoom(self, zoom: float, anchor_x: Optional[float] = None):
        self.canvas.set_zoom(zoom, anchor_x)

    @property
    def zoom(self) -> float:
        return self.canvas.zoom

    @zoom.setter
    def zoom(self, value: float):
        self.canvas.set_zoom(value)

    def refresh_timeline(self):
        """Força atualização visual completa após adição/remoção de seções."""
        self._refresh_status_labels()
        self.canvas.update()

    def _refresh_status_labels(self):
        active_sec = self.timeline_manager.get_active_edit_section()
        s_m, s_s = int(active_sec.start_time_s // 60), int(active_sec.start_time_s % 60)
        e_m, e_s = int(active_sec.end_time_s // 60), int(active_sec.end_time_s % 60)
        self.lbl_active_info.setText(f"Editando: <b>{active_sec.name}</b> [{s_m:02d}:{s_s:02d} - {e_m:02d}:{e_s:02d}]")
        self.btn_delete.setEnabled(len(self.timeline_manager.sections) > 1)

    def _on_section_clicked(self, sec_id: str):
        self.timeline_manager.active_edit_section_id = sec_id
        self._refresh_status_labels()
        self.section_selected.emit(sec_id)

    def _on_boundary_adjusted(self, boundary_idx: int, new_time_s: float):
        self._refresh_status_labels()
        active_sec = self.timeline_manager.get_active_edit_section()
        self.section_selected.emit(active_sec.id)

    def _on_split_clicked(self):
        cur_t = self.canvas.current_time_s
        new_sec = self.timeline_manager.split_section_at(cur_t)
        if new_sec:
            self.refresh_timeline()
            self.split_requested.emit(cur_t)
            self.section_selected.emit(new_sec.id)

    def _on_rename_clicked(self):
        active_sec = self.timeline_manager.get_active_edit_section()
        new_name, ok = QInputDialog.getText(
            self,
            "Renomear Trecho",
            "Nome do Trecho (ex: Verso 1, Refrão, Solo de Guitarra, Ponte):",
            text=active_sec.name
        )
        if ok and new_name.strip():
            self.timeline_manager.rename_section(active_sec.id, new_name.strip())
            self.refresh_timeline()
            self.section_renamed.emit(active_sec.id, new_name.strip())

    def _on_delete_clicked(self):
        active_sec = self.timeline_manager.get_active_edit_section()
        if len(self.timeline_manager.sections) <= 1:
            return

        sec_id = active_sec.id
        if self.timeline_manager.remove_section(sec_id):
            self.refresh_timeline()
            self.section_removed.emit(sec_id)
            self.section_selected.emit(self.timeline_manager.get_active_edit_section().id)
