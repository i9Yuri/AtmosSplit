"""Inspetor do objeto selecionado. A identidade de uma cópia é a instância espacial."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ..separation.stem_engine import StemTrack
from ..spatial.auto_director import SpatialPlacement


class StemControlCard(QFrame):
    changed = Signal(str)
    selected = Signal(str)
    delete_requested = Signal(str)
    duplicate_requested = Signal(str)

    def __init__(self, stem: StemTrack, placement: SpatialPlacement, parent: QWidget | None = None):
        super().__init__(parent)
        self.stem = stem
        self.placement = placement
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        self.lbl_title = QLabel(stem.display_name)
        self.lbl_title.setTextFormat(Qt.PlainText)
        self.lbl_title.setObjectName("SourceTitle")
        self.lbl_title.setWordWrap(True)
        layout.addWidget(self.lbl_title)

        switches = QHBoxLayout()
        self.btn_stereo = self._switch("Estéreo", "is_stereo", "Espelhar em L e R (D)")
        self.btn_solo = self._switch("Solo", "is_solo", "Ouvir apenas esta fonte (S)")
        self.btn_mute = self._switch("Mudo", "is_muted", "Silenciar esta fonte (M)")
        for button in (self.btn_mute, self.btn_solo, self.btn_stereo):
            switches.addWidget(button)
        layout.addLayout(switches)

        controls = QGridLayout()
        controls.setHorizontalSpacing(7)
        controls.setVerticalSpacing(7)
        self._controls = {}
        for row, (key, label, prop, low, high) in enumerate((
            ("vol", "Ganho", "volume_gain", 0, 200),
            ("pan", "Pan", "x", -100, 100),
            ("pos_y", "Frente / trás", "y", -100, 100),
            ("z", "Altura", "z", 0, 100),
            ("spread", "Difusão", "spread", 0, 100),
            ("lfe", "Envio LFE", "lfe_send", 0, 100),
        )):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(low, high)
            slider.setAccessibleName(label)
            value = QLabel()
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setMinimumWidth(57)
            value.setObjectName("Subtle")
            controls.addWidget(QLabel(label), row, 0)
            controls.addWidget(slider, row, 1)
            controls.addWidget(value, row, 2)
            self._controls[prop] = (slider, value)
            setattr(self, "slider_" + key, slider)
            setattr(self, "val_" + key, value)
            slider.valueChanged.connect(lambda n, field=prop: self._change(field, n))
        controls.setColumnStretch(1, 1)
        layout.addLayout(controls)

        snaps = QHBoxLayout()
        for label, attr, fn in (("Esq.", "left", self._snap_left), ("Centro", "center", self._snap_center),
                                ("Dir.", "right", self._snap_right), ("Fundo", "rear", self._snap_rear)):
            button = QPushButton(label)
            button.setToolTip("Posicionar a fonte: " + label)
            button.clicked.connect(fn)
            setattr(self, "btn_pos_" + attr, button)
            snaps.addWidget(button)
        layout.addLayout(snaps)
        copies = QHBoxLayout()
        self.btn_clone = QPushButton("Duplicar fonte")
        self.btn_clone.setAccessibleName("Duplicar fonte")
        self.btn_clone.clicked.connect(lambda: self.duplicate_requested.emit(self.placement.stem_name))
        copies.addWidget(self.btn_clone)
        if "::" in placement.stem_name:
            self.btn_delete = QPushButton("Excluir cópia")
            self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.placement.stem_name))
            copies.addWidget(self.btn_delete)
        copies.addStretch()
        layout.addLayout(copies)
        self.sync_from_placement()

    def _switch(self, label: str, prop: str, hint: str) -> QPushButton:
        button = QPushButton(label)
        button.setCheckable(True)
        button.setToolTip(hint)
        button.toggled.connect(lambda checked: self._toggle(prop, checked))
        return button

    def _toggle(self, field: str, value: bool) -> None:
        setattr(self.placement, field, value)
        if field == "is_stereo" and value and abs(self.placement.x) < 0.2:
            self.placement.x = 0.6
        self.sync_from_placement()
        self.changed.emit(self.placement.stem_name)

    @staticmethod
    def _format_pan_text(x: float) -> str:
        pct = round(x * 100)
        return "Centro" if abs(pct) < 3 else f"{abs(pct)}% {'Esq' if pct < 0 else 'Dir'}"

    @staticmethod
    def _format_pos_y_text(y: float) -> str:
        return "Frente" if y > 0.60 else ("Trás" if y < -0.40 else "Meio")

    def _format(self, field: str, v: float) -> str:
        if field == "x":
            return self._format_pan_text(v)
        if field == "y":
            return self._format_pos_y_text(v)
        if field == "volume_gain":
            return f"{20 * math.log10(v):+.1f} dB" if v > 0 else "−∞ dB"
        return f"{round(100 * v)}%"

    def _change(self, field: str, percent: int) -> None:
        val = percent / 100
        setattr(self.placement, field, val)
        self._controls[field][1].setText(self._format(field, val))
        self.changed.emit(self.placement.stem_name)

    def _position(self, x: float, y: float) -> None:
        self.sync_coords_from_placement(x, y, self.placement.z)
        self.changed.emit(self.placement.stem_name)

    def _snap_left(self) -> None:
        self._position(-0.7, max(-0.2, self.placement.y))

    def _snap_center(self) -> None:
        self._position(0.0, 0.95)

    def _snap_right(self) -> None:
        self._position(0.7, max(-0.2, self.placement.y))

    def _snap_rear(self) -> None:
        self._position(self.placement.x, -0.75)

    def sync_coords_from_placement(self, x: float, y: float, z: float) -> None:
        self.placement.x, self.placement.y, self.placement.z = x, y, z
        self.sync_from_placement()

    def sync_from_placement(self) -> None:
        for field, (slider, label) in self._controls.items():
            v = getattr(self.placement, field)
            with QSignalBlocker(slider):
                slider.setValue(round(100 * v))
            label.setText(self._format(field, v))
        for button, checked in ((self.btn_stereo, self.placement.is_stereo),
                                (self.btn_solo, self.placement.is_solo), (self.btn_mute, self.placement.is_muted)):
            with QSignalBlocker(button):
                button.setChecked(checked)
