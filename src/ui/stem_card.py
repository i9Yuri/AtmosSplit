"""
AtmosSplit — Card Lateral de Controle de Instrumento (Stem Control Card)
Controles táteis simples: Volume, Altura Z, Subwoofer (LFE), Espelhamento Estéreo (L/R), Solo e Mudo.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QFrame,
)
from PySide6.QtGui import QColor

from ..separation.stem_engine import StemTrack
from ..spatial.auto_director import SpatialPlacement


class StemControlCard(QFrame):
    """Card de controle direto para um instrumento individual."""
    changed = Signal(str)  # Emite o stem_name quando qualquer parâmetro mudar
    selected = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, stem: StemTrack, placement: SpatialPlacement, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.stem = stem
        self.placement = placement
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("StemControlCard")
        self.setStyleSheet("""
            QFrame#StemControlCard {
                background-color: #16181D;
                border: 1px solid #262A34;
                border-radius: 8px;
                padding: 6px;
            }
            QFrame#StemControlCard:hover {
                border: 1px solid #3B4252;
            }
            QLabel {
                color: #CBD5E0;
                font-size: 11px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #2D3748;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00E5FF;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #20242C;
                color: #A0AEC0;
                border: 1px solid #2D3748;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                padding: 3px 6px;
            }
            QPushButton:hover {
                background-color: #2D3748;
                color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Cabeçalho do Card
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        
        # Ponto de cor
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self.stem.color_hex}; font-size: 14px;")
        header_layout.addWidget(dot)

        # Nome
        self.lbl_title = QLabel(self.stem.display_name if self.placement.source_stem_name in (None, self.stem.name) else f"{self.stem.display_name} · cópia")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFFFFF;")
        header_layout.addWidget(self.lbl_title, stretch=1)

        # Botão Espelhamento Estéreo L / R
        self.btn_stereo = QPushButton("🪞")
        self.btn_stereo.setFixedWidth(28)
        self.btn_stereo.setCheckable(True)
        self.btn_stereo.setToolTip("Espelhamento Estéreo 7.1.4 (L / R)")
        self.btn_stereo.setChecked(self.placement.is_stereo)
        self.btn_stereo.clicked.connect(self._on_stereo_toggle)
        self._update_stereo_button_style()
        header_layout.addWidget(self.btn_stereo)

        # Botão Solo
        self.btn_solo = QPushButton("S")
        self.btn_solo.setFixedWidth(24)
        self.btn_solo.setCheckable(True)
        self.btn_solo.setChecked(self.placement.is_solo)
        self.btn_solo.clicked.connect(self._on_solo_toggle)
        header_layout.addWidget(self.btn_solo)

        # Botão Mute
        self.btn_mute = QPushButton("M")
        self.btn_mute.setFixedWidth(24)
        self.btn_mute.setCheckable(True)
        self.btn_mute.setChecked(self.placement.is_muted)
        self.btn_mute.clicked.connect(self._on_mute_toggle)
        header_layout.addWidget(self.btn_mute)
        if self.placement.source_stem_name not in (None, self.stem.name):
            self.btn_delete = QPushButton("×")
            self.btn_delete.setFixedWidth(24)
            self.btn_delete.setToolTip("Excluir esta instância clonada")
            self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.placement.stem_name))
            header_layout.addWidget(self.btn_delete)

        layout.addLayout(header_layout)

        # Barra de Posicionamento Rápido (1-Clique)
        row_quick = QHBoxLayout()
        row_quick.setSpacing(4)
        
        lbl_quick = QLabel("Posição:")
        lbl_quick.setStyleSheet("font-size: 10px; color: #718096; font-weight: bold;")
        row_quick.addWidget(lbl_quick)

        self.btn_pos_left = QPushButton("⇦ Esq")
        self.btn_pos_left.setToolTip("Posicionar na Esquerda (Canal Lateral / Frontal Esquerdo)")
        self.btn_pos_left.clicked.connect(self._snap_left)
        row_quick.addWidget(self.btn_pos_left)

        self.btn_pos_center = QPushButton("⇧ Centro")
        self.btn_pos_center.setToolTip("Ancorar no Centro Frontal (Palco / TV)")
        self.btn_pos_center.clicked.connect(self._snap_center)
        row_quick.addWidget(self.btn_pos_center)

        self.btn_pos_right = QPushButton("Dir ⇨")
        self.btn_pos_right.setToolTip("Posicionar na Direita (Canal Lateral / Frontal Direito)")
        self.btn_pos_right.clicked.connect(self._snap_right)
        row_quick.addWidget(self.btn_pos_right)

        self.btn_pos_rear = QPushButton("⇩ Fundo")
        self.btn_pos_rear.setToolTip("Enviar para a Traseira (Satélites Surround)")
        self.btn_pos_rear.clicked.connect(self._snap_rear)
        row_quick.addWidget(self.btn_pos_rear)

        layout.addLayout(row_quick)

        # Slider: Pan Estéreo / Lado (Esquerda ⟵ 0 ⟶ Direita)
        row_pan = QHBoxLayout()
        lbl_pan = QLabel("Pan (L / R):")
        self.val_pan = QLabel(self._format_pan_text(self.placement.x))
        self.val_pan.setFixedWidth(52)
        self.val_pan.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_pan = QSlider(Qt.Horizontal)
        self.slider_pan.setRange(-100, 100)
        self.slider_pan.setValue(int(self.placement.x * 100))
        self.slider_pan.valueChanged.connect(self._on_pan_change)
        row_pan.addWidget(lbl_pan)
        row_pan.addWidget(self.slider_pan, stretch=1)
        row_pan.addWidget(self.val_pan)
        layout.addLayout(row_pan)

        # Slider: Posição Frente / Trás (Traseira ⟵ 0 ⟶ Frente/TV)
        row_pos_y = QHBoxLayout()
        lbl_pos_y = QLabel("Frente/Trás:")
        self.val_pos_y = QLabel(self._format_pos_y_text(self.placement.y))
        self.val_pos_y.setFixedWidth(52)
        self.val_pos_y.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_pos_y = QSlider(Qt.Horizontal)
        self.slider_pos_y.setRange(-100, 100)
        self.slider_pos_y.setValue(int(self.placement.y * 100))
        self.slider_pos_y.valueChanged.connect(self._on_pos_y_change)
        row_pos_y.addWidget(lbl_pos_y)
        row_pos_y.addWidget(self.slider_pos_y, stretch=1)
        row_pos_y.addWidget(self.val_pos_y)
        layout.addLayout(row_pos_y)

        # Slider: Altura (Teto 7.1.4)
        row_z = QHBoxLayout()
        lbl_z = QLabel("Altura (Teto):")
        self.val_z = QLabel(f"{int(self.placement.z * 100)}%")
        self.val_z.setFixedWidth(32)
        self.val_z.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_z = QSlider(Qt.Horizontal)
        self.slider_z.setRange(0, 100)
        self.slider_z.setValue(int(self.placement.z * 100))
        self.slider_z.valueChanged.connect(self._on_z_change)
        row_z.addWidget(lbl_z)
        row_z.addWidget(self.slider_z, stretch=1)
        row_z.addWidget(self.val_z)
        layout.addLayout(row_z)

        # Slider: Força no Subwoofer (LFE)
        row_lfe = QHBoxLayout()
        lbl_lfe = QLabel("Subwoofer (LFE):")
        self.val_lfe = QLabel(f"{int(self.placement.lfe_send * 100)}%")
        self.val_lfe.setFixedWidth(32)
        self.val_lfe.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_lfe = QSlider(Qt.Horizontal)
        self.slider_lfe.setRange(0, 100)
        self.slider_lfe.setValue(int(self.placement.lfe_send * 100))
        self.slider_lfe.valueChanged.connect(self._on_lfe_change)
        row_lfe.addWidget(lbl_lfe)
        row_lfe.addWidget(self.slider_lfe, stretch=1)
        row_lfe.addWidget(self.val_lfe)
        layout.addLayout(row_lfe)

        # Slider: Volume
        row_vol = QHBoxLayout()
        lbl_vol = QLabel("Volume:")
        self.val_vol = QLabel(f"{int(self.placement.volume_gain * 100)}%")
        self.val_vol.setFixedWidth(32)
        self.val_vol.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 150)
        self.slider_vol.setValue(int(self.placement.volume_gain * 100))
        self.slider_vol.valueChanged.connect(self._on_vol_change)
        row_vol.addWidget(lbl_vol)
        row_vol.addWidget(self.slider_vol, stretch=1)
        row_vol.addWidget(self.val_vol)
        layout.addLayout(row_vol)

    def mousePressEvent(self, event):
        self.selected.emit(self.stem.name)
        super().mousePressEvent(event)

    def set_selected(self, is_selected: bool):
        """Altera a borda e realce do card de forma leve e instantânea sem destruir o layout interno."""
        if getattr(self, "_is_selected_state", False) == is_selected:
            return
        self._is_selected_state = is_selected
        if is_selected:
            self.setStyleSheet("""
                QFrame#StemControlCard {
                    background-color: #1A1F2C;
                    border: 2px solid #00E5FF;
                    border-radius: 8px;
                    padding: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#StemControlCard {
                    background-color: #16181D;
                    border: 1px solid #262A34;
                    border-radius: 8px;
                    padding: 6px;
                }
            """)

    def _update_stereo_button_style(self):
        if self.placement.is_stereo:
            self.btn_stereo.setStyleSheet("background-color: #00E5FF; color: #000000; border: 1px solid #00B4D8; font-weight: bold;")
            self.btn_stereo.setToolTip("Espelhamento Estéreo Ativado (L e R)")
        else:
            self.btn_stereo.setStyleSheet("")
            self.btn_stereo.setToolTip("Espelhamento Estéreo Desativado (Mono centralizado)")

    def _on_stereo_toggle(self, checked: bool):
        self.placement.is_stereo = checked
        if checked and abs(self.placement.x) < 0.20:
            self.placement.x = 0.60
        self._update_stereo_button_style()
        self.changed.emit(self.stem.name)

    def _on_solo_toggle(self, checked: bool):
        self.placement.is_solo = checked
        if checked:
            self.btn_solo.setStyleSheet("background-color: #D69E2E; color: #000000; border: none;")
        else:
            self.btn_solo.setStyleSheet("")
        self.changed.emit(self.stem.name)

    def _on_mute_toggle(self, checked: bool):
        self.placement.is_muted = checked
        if checked:
            self.btn_mute.setStyleSheet("background-color: #E53E3E; color: #FFFFFF; border: none;")
        else:
            self.btn_mute.setStyleSheet("")
        self.changed.emit(self.stem.name)

    @staticmethod
    def _format_pan_text(x: float) -> str:
        pct = int(round(x * 100))
        if abs(pct) < 3:
            return "Centro"
        elif pct < 0:
            return f"{abs(pct)}% Esq"
        else:
            return f"{pct}% Dir"

    @staticmethod
    def _format_pos_y_text(y: float) -> str:
        pct = int(round(y * 100))
        if pct > 60:
            return "Frente"
        elif pct < -40:
            return "Trás"
        else:
            return "Meio"

    def _snap_left(self):
        """Posiciona imediatamente no lado esquerdo."""
        self.placement.x = -0.70
        self.placement.y = max(-0.20, self.placement.y)
        self.sync_coords_from_placement(self.placement.x, self.placement.y, self.placement.z)
        self.changed.emit(self.stem.name)

    def _snap_center(self):
        """Ancora imediatamente no centro frontal (palco / TV)."""
        self.placement.x = 0.0
        self.placement.y = 0.95
        self.sync_coords_from_placement(self.placement.x, self.placement.y, self.placement.z)
        self.changed.emit(self.stem.name)

    def _snap_right(self):
        """Posiciona imediatamente no lado direito."""
        self.placement.x = 0.70
        self.placement.y = max(-0.20, self.placement.y)
        self.sync_coords_from_placement(self.placement.x, self.placement.y, self.placement.z)
        self.changed.emit(self.stem.name)

    def _snap_rear(self):
        """Envia imediatamente para o fundo / surround traseiro."""
        self.placement.y = -0.75
        self.sync_coords_from_placement(self.placement.x, self.placement.y, self.placement.z)
        self.changed.emit(self.stem.name)

    def _on_pan_change(self, val: int):
        self.placement.x = float(val) / 100.0
        self.val_pan.setText(self._format_pan_text(self.placement.x))
        self.changed.emit(self.stem.name)

    def _on_pos_y_change(self, val: int):
        self.placement.y = float(val) / 100.0
        self.val_pos_y.setText(self._format_pos_y_text(self.placement.y))
        self.changed.emit(self.stem.name)

    def _on_z_change(self, val: int):
        self.placement.z = float(val) / 100.0
        self.val_z.setText(f"{val}%")
        self.changed.emit(self.stem.name)

    def _on_lfe_change(self, val: int):
        self.placement.lfe_send = float(val) / 100.0
        self.val_lfe.setText(f"{val}%")
        self.changed.emit(self.stem.name)

    def _on_vol_change(self, val: int):
        self.placement.volume_gain = float(val) / 100.0
        self.val_vol.setText(f"{val}%")
        self.changed.emit(self.stem.name)

    def sync_coords_from_placement(self, x: float, y: float, z: float):
        """Atualização rápida de coordenadas (chamada durante arraste no mouse sem redesenhar tudo)."""
        self.placement.x = x
        self.placement.y = y
        self.placement.z = z

        self.slider_pan.blockSignals(True)
        self.slider_pos_y.blockSignals(True)
        self.slider_z.blockSignals(True)

        self.slider_pan.setValue(int(x * 100))
        self.slider_pos_y.setValue(int(y * 100))
        self.slider_z.setValue(int(z * 100))

        self.val_pan.setText(self._format_pan_text(x))
        self.val_pos_y.setText(self._format_pos_y_text(y))
        self.val_z.setText(f"{int(z * 100)}%")

        self.slider_pan.blockSignals(False)
        self.slider_pos_y.blockSignals(False)
        self.slider_z.blockSignals(False)

    def sync_from_placement(self):
        """Atualiza todos os sliders e botões para refletir alterações completas."""
        self.sync_coords_from_placement(self.placement.x, self.placement.y, self.placement.z)

        self.slider_lfe.blockSignals(True)
        self.slider_vol.blockSignals(True)
        self.btn_stereo.blockSignals(True)
        self.btn_solo.blockSignals(True)
        self.btn_mute.blockSignals(True)

        lfe_pct = int(self.placement.lfe_send * 100)
        vol_pct = int(self.placement.volume_gain * 100)

        self.slider_lfe.setValue(lfe_pct)
        self.slider_vol.setValue(vol_pct)

        self.val_lfe.setText(f"{lfe_pct}%")
        self.val_vol.setText(f"{vol_pct}%")

        self.btn_stereo.setChecked(self.placement.is_stereo)
        self._update_stereo_button_style()

        self.btn_solo.setChecked(self.placement.is_solo)
        if self.placement.is_solo:
            self.btn_solo.setStyleSheet("background-color: #D69E2E; color: #000000; border: none;")
        else:
            self.btn_solo.setStyleSheet("")

        self.btn_mute.setChecked(self.placement.is_muted)
        if self.placement.is_muted:
            self.btn_mute.setStyleSheet("background-color: #E53E3E; color: #FFFFFF; border: none;")
        else:
            self.btn_mute.setStyleSheet("")

        self.slider_lfe.blockSignals(False)
        self.slider_vol.blockSignals(False)
        self.btn_stereo.blockSignals(False)
        self.btn_solo.blockSignals(False)
        self.btn_mute.blockSignals(False)
