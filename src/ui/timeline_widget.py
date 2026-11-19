"""
AtmosSplit — Spatial Timeline Widget (Automação Visual por Trechos)
Widget interativo que exibe a linha do tempo da música dividida em seções
(Intro, Verso, Refrão, Ponte, Final), permitindo ao usuário criar diferentes
posicionamentos espaciais para cada momento da faixa.
Permite divisão rápida (split) no cursor, renomeação, exclusão e seleção com 1 clique.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QMouseEvent,
    QCursor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QInputDialog,
    QMessageBox,
    QFrame,
)

from ..spatial.timeline_manager import SpatialTimelineManager, SpatialSection


class TimelineTrackCanvas(QWidget):
    """Área gráfica interativa da barra de tempo com blocos de seções e playhead."""
    section_clicked = Signal(str)
    seek_clicked = Signal(float)

    def __init__(self, timeline_manager: SpatialTimelineManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.timeline_manager = timeline_manager
        self.current_time_s: float = 0.0
        self.hovered_section_id: Optional[str] = None
        self.setMinimumHeight(44)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def set_playhead_time(self, time_s: float):
        """Atualiza a posição do playhead e redesenha se houver mudança visível."""
        if abs(self.current_time_s - time_s) > 0.05:
            self.current_time_s = time_s
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        total_d = max(1.0, self.timeline_manager.total_duration_s)

        # Fundo do trilho
        painter.fillRect(0, 0, w, h, QColor("#12141A"))

        # Desenhar blocos de seções
        sections = self.timeline_manager.sections
        active_edit_id = self.timeline_manager.active_edit_section_id

        for sec in sections:
            start_ratio = sec.start_time_s / total_d
            end_ratio = sec.end_time_s / total_d

            x1 = start_ratio * w
            x2 = end_ratio * w
            block_w = max(4.0, x2 - x1)

            is_active = (sec.id == active_edit_id)
            is_hovered = (sec.id == self.hovered_section_id)

            base_color = QColor(sec.color_hex)

            # Preenchimento translúcido elegante
            fill_alpha = 95 if is_active else (65 if is_hovered else 40)
            fill_color = QColor(base_color.red(), base_color.green(), base_color.blue(), fill_alpha)
            painter.fillRect(QRectF(x1, 2, block_w - 1, h - 4), fill_color)

            # Borda do bloco
            if is_active:
                painter.setPen(QPen(QColor("#00E5FF"), 2.0))
            elif is_hovered:
                painter.setPen(QPen(QColor("#FFFFFF"), 1.2))
            else:
                painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 140), 1.0))

            painter.drawRoundedRect(QRectF(x1 + 0.5, 2.5, block_w - 2, h - 5), 3.0, 3.0)

            # Rótulo da Seção
            if block_w > 45:
                painter.setFont(QFont("sans-serif", 8, QFont.Bold if is_active else QFont.Normal))
                painter.setPen(QColor("#FFFFFF") if is_active else QColor("#CBD5E0"))

                start_m, start_s = int(sec.start_time_s // 60), int(sec.start_time_s % 60)
                end_m, end_s = int(sec.end_time_s // 60), int(sec.end_time_s % 60)

                if block_w > 90:
                    label_text = f"{sec.name} ({start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d})"
                else:
                    label_text = sec.name

                text_rect = QRectF(x1 + 6, 2, block_w - 12, h - 4)
                painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, label_text)

        # Desenhar Playhead (Agulha de reprodução em tempo real)
        play_ratio = min(1.0, max(0.0, self.current_time_s / total_d))
        play_x = play_ratio * w

        painter.setPen(QPen(QColor("#00E5FF"), 1.8))
        painter.drawLine(int(play_x), 0, int(play_x), h)

        # Cabeça do Playhead (triângulo indicador superior)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#00E5FF")))
        triangle = [
            QPointF(play_x - 5, 0),
            QPointF(play_x + 5, 0),
            QPointF(play_x, 7)
        ]
        painter.drawPolygon(triangle)

    def _get_section_at_x(self, px: float) -> Optional[SpatialSection]:
        w = max(1.0, float(self.width()))
        ratio = max(0.0, min(1.0, px / w))
        target_time = ratio * self.timeline_manager.total_duration_s
        for sec in self.timeline_manager.sections:
            if sec.start_time_s <= target_time <= sec.end_time_s:
                return sec
        return None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            sec = self._get_section_at_x(event.position().x())
            if sec:
                self.section_clicked.emit(sec.id)

            # Também efetua seek para o tempo clicado
            w = max(1.0, float(self.width()))
            ratio = max(0.0, min(1.0, event.position().x() / w))
            t = ratio * self.timeline_manager.total_duration_s
            self.seek_clicked.emit(t)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        sec = self._get_section_at_x(event.position().x())
        hover_id = sec.id if sec else None
        if hover_id != self.hovered_section_id:
            self.hovered_section_id = hover_id
            self.update()

    def leaveEvent(self, event):
        self.hovered_section_id = None
        self.update()


class TimelineWidget(QFrame):
    """Barra completa de controle de trechos com tela visual e botões de ação rápida."""
    section_selected = Signal(str)
    split_requested = Signal(float)
    section_renamed = Signal(str, str)
    section_removed = Signal(str)
    seek_requested = Signal(float)

    def __init__(self, timeline_manager: SpatialTimelineManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.timeline_manager = timeline_manager
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("TimelineWidgetFrame")
        self.setStyleSheet("""
            QFrame#TimelineWidgetFrame {
                background-color: #16181F;
                border-top: 1px solid #232734;
                border-bottom: 1px solid #232734;
                padding: 6px 12px;
            }
            QPushButton {
                background-color: #20242D;
                border: 1px solid #2E3545;
                border-radius: 4px;
                color: #CBD5E0;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #2D3547;
                color: #FFFFFF;
                border-color: #4A5568;
            }
            QPushButton#BtnSplit {
                background-color: #00E5FF;
                color: #000000;
                border: 1px solid #00B4D8;
            }
            QPushButton#BtnSplit:hover {
                background-color: #18FFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Cabeçalho da barra de seções
        bar_header = QHBoxLayout()
        bar_header.setSpacing(8)

        lbl_title = QLabel("AUTOMAÇÃO ESPACIAL POR TRECHOS")
        lbl_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #A0AEC0; letter-spacing: 1px;")
        bar_header.addWidget(lbl_title)

        self.lbl_active_info = QLabel("Editando: Música Completa")
        self.lbl_active_info.setStyleSheet("font-size: 10px; color: #00E5FF; font-weight: bold;")
        bar_header.addWidget(self.lbl_active_info)

        bar_header.addStretch(1)

        # Botão: Dividir no Tempo Atual
        self.btn_split = QPushButton("✂️ Dividir no Tempo Atual")
        self.btn_split.setObjectName("BtnSplit")
        self.btn_split.setToolTip("Divide a música no ponto atual da reprodução para criar um arranjo 3D exclusivo neste trecho.")
        self.btn_split.clicked.connect(self._on_split_clicked)
        bar_header.addWidget(self.btn_split)

        # Botão: Renomear
        self.btn_rename = QPushButton("✏️ Renomear")
        self.btn_rename.setToolTip("Altera o nome do trecho selecionado (ex: Verso, Refrão, Ponte).")
        self.btn_rename.clicked.connect(self._on_rename_clicked)
        bar_header.addWidget(self.btn_rename)

        # Botão: Excluir Trecho
        self.btn_delete = QPushButton("🗑️ Excluir")
        self.btn_delete.setToolTip("Remove o trecho e junta seu tempo com o trecho vizinho.")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        bar_header.addWidget(self.btn_delete)

        layout.addLayout(bar_header)

        # Canvas gráfico de seções e playhead
        self.canvas = TimelineTrackCanvas(self.timeline_manager)
        self.canvas.section_clicked.connect(self._on_section_clicked)
        self.canvas.seek_clicked.connect(self.seek_requested)
        layout.addWidget(self.canvas)

        self._refresh_status_labels()

    def set_current_playback_time(self, time_s: float):
        """Atualiza a posição do cursor na barra de tempo."""
        self.canvas.set_playhead_time(time_s)

    def refresh_timeline(self):
        """Força atualização visual completa após adição/remoção de seções."""
        self._refresh_status_labels()
        self.canvas.update()

    def _refresh_status_labels(self):
        active_sec = self.timeline_manager.get_active_edit_section()
        s_m, s_s = int(active_sec.start_time_s // 60), int(active_sec.start_time_s % 60)
        e_m, e_s = int(active_sec.end_time_s // 60), int(active_sec.end_time_s % 60)
        self.lbl_active_info.setText(f"Editando: <b>{active_sec.name}</b> [{s_m:02d}:{s_s:02d} - {e_m:02d}:{e_s:02d}]")

        # Habilitar/desabilitar botão excluir
        self.btn_delete.setEnabled(len(self.timeline_manager.sections) > 1)

    def _on_section_clicked(self, sec_id: str):
        self.timeline_manager.active_edit_section_id = sec_id
        self._refresh_status_labels()
        self.canvas.update()
        self.section_selected.emit(sec_id)

    def _on_split_clicked(self):
        cur_t = self.canvas.current_time_s
        new_sec = self.timeline_manager.split_section_at(cur_t)
        if new_sec:
            self.refresh_timeline()
            self.split_requested.emit(cur_t)
            self.section_selected.emit(new_sec.id)
        else:
            QMessageBox.information(
                self,
                "Divisão de Trecho",
                "O cursor de reprodução está muito próximo do início ou do fim de um trecho existente.\n"
                "Avance ou recue a música alguns segundos para dividir."
            )

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

        confirm = QMessageBox.question(
            self,
            "Excluir Trecho",
            f"Deseja realmente remover o trecho '{active_sec.name}'?\n"
            "Ele será fundido com o trecho vizinho.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            sec_id = active_sec.id
            if self.timeline_manager.remove_section(sec_id):
                self.refresh_timeline()
                self.section_removed.emit(sec_id)
                self.section_selected.emit(self.timeline_manager.get_active_edit_section().id)
