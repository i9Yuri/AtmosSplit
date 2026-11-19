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
        self.lbl_title = QLabel(self.stem.display_name)
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

        layout.addLayout(header_layout)

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

    def sync_from_placement(self):
        """Atualiza os sliders e botões para refletir alterações vindas do mouse/sala/timeline."""
        self.slider_z.blockSignals(True)
        self.slider_lfe.blockSignals(True)
        self.slider_vol.blockSignals(True)
        self.btn_stereo.blockSignals(True)
        self.btn_solo.blockSignals(True)
        self.btn_mute.blockSignals(True)

        z_pct = int(self.placement.z * 100)
        lfe_pct = int(self.placement.lfe_send * 100)
        vol_pct = int(self.placement.volume_gain * 100)

        self.slider_z.setValue(z_pct)
        self.slider_lfe.setValue(lfe_pct)
        self.slider_vol.setValue(vol_pct)

        self.val_z.setText(f"{z_pct}%")
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

        self.slider_z.blockSignals(False)
        self.slider_lfe.blockSignals(False)
        self.slider_vol.blockSignals(False)
        self.btn_stereo.blockSignals(False)
        self.btn_solo.blockSignals(False)
        self.btn_mute.blockSignals(False)
