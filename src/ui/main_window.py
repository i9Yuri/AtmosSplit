"""Estação de edição espacial. Os processos de estúdio nunca recebem widgets ou buffers do PortAudio."""

from __future__ import annotations

import copy
import ctypes
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import (
    QIODevice, QProcess, QProcessEnvironment, QSaveFile, QSettings, QSignalBlocker,
    QStandardPaths, Qt, QThread, QTimer,
)
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter,
    QStyle, QStyleOptionProgressBar, QStylePainter,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from ..playback.directframe_bridge import DirectFrameBridge
from ..playback.exporter import ExportFormat
from ..playback.samsung_dlna_bridge import SamsungDLNABridge
from ..separation.cache_manager import StemCacheManager
from ..separation.stem_engine import DeepStemEngine, StemTrack
from ..spatial.auto_director import DirectorPreset, SpatialPlacement
from ..spatial.live_player import LiveSpatialPlayer
from ..spatial.timeline_manager import SpatialTimelineManager
from . import theme as T
from .micro_event_lane import event_details, event_title
from .room_view_714 import RoomView714
from .stem_card import StemControlCard
from .studio_jobs import pack_sections, unpack_sections
from .timeline_widget import TimelineWidget

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
BUSY_DROP_NOTICE = "Uma operação já está em andamento. Aguarde ou cancele antes de abrir nova faixa."
PREVIEW_PROGRESS = 95
AUDIO_FILTER = "Áudio (*.flac *.wav *.alac *.aac *.mp3 *.m4a *.mp4 *.mkv *.opus *.ogg *.aif *.aiff);;Todos os arquivos (*)"
EXPORT_FORMATS = {
    "Dolby Atmos para TV e DLNA (*.mp4)": ExportFormat.MP4_ATMOS_JOC_714,
    "PCM 7.1.4 para DirectFrame (*.mkv)": ExportFormat.MKV_LPCM_714,
    "Dolby Atmos em Matroska (*.mkv)": ExportFormat.MKV_ATMOS_JOC_714,
    "Master PCM 7.1.4 (*.wav)": ExportFormat.WAV_714,
    "Fluxo E-AC-3 JOC (*.ec3)": ExportFormat.EC3_ATMOS_714,
}


def _immunize_cpython_none_refcount() -> None:
    # Shiboken 6.12 sobre CPython 3.11: nenhuma manipulação de objetos imortais em 3.12+.
    if sys.platform == "linux" and sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 11):
        refcnt = ctypes.c_ssize_t.from_address(id(None))
        if refcnt.value < 500_000_000:
            refcnt.value += 1_000_000_000


def _label(value: str, style: str = "") -> QLabel:
    label = QLabel(value)
    label.setTextFormat(Qt.PlainText)
    label.setObjectName(style)
    return label


def _clock(seconds: float) -> str:
    minutes, sec = divmod(int(max(0, seconds)), 60)
    return f"{minutes:02d}:{sec:02d}"


def _panel(name: str, margin: int = 14) -> tuple[QWidget, QVBoxLayout]:
    panel = QWidget()
    panel.setObjectName(name)
    box = QVBoxLayout(panel)
    box.setContentsMargins(margin, margin, margin, margin)
    box.setSpacing(10)
    return panel, box


class StudioProgressBar(QProgressBar):
    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        option = QStyleOptionProgressBar()
        self.initStyleOption(option)
        # A porcentagem fica ao lado da trilha, com contraste constante.
        label_width = painter.fontMetrics().horizontalAdvance("100%") + 12
        bounds = option.rect
        option.rect = bounds.adjusted(0, (bounds.height() - 12) // 2, -label_width, 0)
        option.rect.setHeight(12)
        option.textVisible = False
        painter.drawControl(QStyle.CE_ProgressBar, option)
        if self.isTextVisible():
            painter.setPen(QColor(T.INK))
            painter.drawText(bounds.adjusted(bounds.width() - label_width, 0, 0, 0),
                             Qt.AlignRight | Qt.AlignVCenter, option.text)


class SessionThread(QThread):
    """I/O local e preparação de um novo monitor ainda desconectado da reprodução."""

    def __init__(self, fn, parent: QWidget):
        super().__init__(parent)
        self.fn = fn
        self.result = None
        self.error = ""

    def run(self) -> None:
        try:
            self.result = self.fn()
        except Exception as exc:
            self.error = str(exc)
            log.exception("Falha no trabalho de sessão")


class MainWindow(QMainWindow):
    def __init__(self, cache_manager: StemCacheManager | None = None, settings: QSettings | None = None,
                 session_dir: Path | None = None):
        super().__init__()
        _immunize_cpython_none_refcount()
        self.setWindowTitle("AtmosSplit — Estúdio espacial 7.1.4")
        self.setWindowIcon(QIcon(str(ROOT / "assets/icon.png")))
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.cache_manager = cache_manager or StemCacheManager()
        self.settings = settings or QSettings("AtmosSplit", "AtmosSplit")
        self.session_dir = session_dir or Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / "sessions"
        self.current_stems: list[StemTrack] = []
        self.session: dict = {}
        self._sources: dict[str, StemTrack] = {}
        self._clipboard: SpatialPlacement | None = None
        self._inspector: StemControlCard | None = None
        self._dirty = False
        self._manual = False
        self._proc: QProcess | None = None
        self._thread: SessionThread | None = None
        self._device_scan: SessionThread | None = None
        self._task: str | None = None
        self._closing = self._cancelled = False
        self._preview_ui: tuple | None = None
        self._caption_events: tuple = ()
        self._caption_recent = False
        self._export_stage = None
        self._profile = self.settings.value("monitor/profile", "jbl")
        if self._profile not in ("jbl", "studio"):
            self._profile = "jbl"
        self._current_theme = str(self.settings.value("ui/theme", "amoled"))
        if self._current_theme not in T.THEMES:
            self._current_theme = "amoled"
        T.set_active_theme(self._current_theme)
        self.timeline_manager = SpatialTimelineManager(1)
        self.live_player = LiveSpatialPlayer(sample_rate=48000, profile=self._profile)
        self.setStyleSheet(T.style_sheet(self._current_theme))
        self._build()
        self.ui_poll_timer = QTimer(self)
        self.ui_poll_timer.setTimerType(Qt.PreciseTimer)
        self.ui_poll_timer.setInterval(100 if self.reduced_motion.isChecked() else 16)
        self.ui_poll_timer.timeout.connect(self._poll_audio_state)
        self.ui_poll_timer.start()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(480)
        self.save_timer.timeout.connect(self._save_arrangement)
        self._sync_enabled()
        size = self.screen().availableGeometry().size()
        self.resize(min(1630, size.width()-16), min(950, size.height()-58))
        QTimer.singleShot(0, self._discover_devices)

    @property
    def current_placements(self) -> dict[str, SpatialPlacement]:
        return self.timeline_manager.get_active_edit_section().placements

    def _build(self) -> None:
        central, layout = _panel("Studio", 0)
        self.setCentralWidget(central)
        layout.setSpacing(0)
        header, top = _panel("SessionHeader", 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 12, 16, 10)
        bar.setSpacing(12)
        bar.addWidget(_label("AtmosSplit", "Brand"))
        bar.addWidget(_label("Estúdio espacial 7.1.4", "Subtle"))
        bar.addSpacing(16)
        self.track_label = _label("Sessão sem faixa", "Heading")
        self.track_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        bar.addWidget(self.track_label, 1)

        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("ThemeToggle")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setFocusPolicy(Qt.NoFocus)
        self.btn_theme.clicked.connect(self._toggle_theme)
        self._update_theme_button()
        bar.addWidget(self.btn_theme)

        self.options = QToolButton()
        self.options.setText("Sessão")
        self.options.setPopupMode(QToolButton.InstantPopup)
        option_menu = QMenu(self.options)
        self.search_action = option_menu.addAction("Buscar música online…", self._on_search_clicked)
        self.cache_action = option_menu.addAction("Gerenciar cache…", self._cache_dialog)
        option_menu.addSeparator()
        self.theme_action = option_menu.addAction("Alternar tema (Claro / AMOLED)", self._toggle_theme)
        self.reanalyze_action = option_menu.addAction("Analisar a estrutura novamente", self._reanalyze)
        self.reduced_motion = option_menu.addAction("Reduzir movimento")
        self.reduced_motion.setCheckable(True)
        self.reduced_motion.setChecked(self.settings.value("ui/reducedMotion", False, type=bool))
        self.reduced_motion.toggled.connect(self._set_reduced_motion)
        option_menu.addAction("Atalhos de teclado", self._help)
        self.options.setMenu(option_menu)
        bar.addWidget(self.options)
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Separação detalhada", "surgical")
        self.combo_mode.addItem("Separação rápida", "fast")
        self.combo_mode.setCurrentIndex(max(0, self.combo_mode.findData(self.settings.value("separation/mode", "surgical"))))
        self.combo_mode.currentIndexChanged.connect(
            lambda: self.settings.setValue("separation/mode", self.combo_mode.currentData()))
        self.combo_mode.setAccessibleName("Modo de separação para a próxima faixa")
        bar.addWidget(self.combo_mode)
        self.btn_open = QPushButton("Abrir faixa")
        self.btn_open.setObjectName("Primary")
        self.btn_open.setShortcut(QKeySequence.Open)
        self.btn_open.clicked.connect(self._open)
        bar.addWidget(self.btn_open)
        top.addLayout(bar)
        layout.addWidget(header)

        self.workspace = QSplitter(Qt.Horizontal)
        self.workspace.setChildrenCollapsible(False)
        self.workspace.setHandleWidth(3)
        sources, left = _panel("SourcePanel")
        left.addWidget(_label("Fontes", "Heading"))
        self.source_list = QListWidget()
        self.source_list.setAccessibleName("Fontes da seção")
        self.source_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.source_list.currentItemChanged.connect(self._select_list_source)
        self.empty_sources = _label("Arraste um arquivo de áudio para a janela ou use Abrir faixa.", "Subtle")
        self.empty_sources.setWordWrap(True)
        self.empty_sources.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        left.addWidget(self.empty_sources, 1)
        left.addWidget(self.source_list, 1)
        self.source_count = _label("", "Subtle")
        left.addWidget(self.source_count)
        sources.setMinimumWidth(160)
        self.workspace.addWidget(sources)
        center, scene_layout = _panel("Studio", 12)
        scene_top = QHBoxLayout()
        scene_top.addWidget(_label("Sala 7.1.4", "Heading"))
        self.event_caption = _label("", "SectionInfo")
        self.event_caption.setAccessibleName("Microeventos ativos na sala")
        self.event_caption.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        scene_top.addWidget(self.event_caption, 1)
        scene_top.addWidget(_label("Tracejado: teto   ·   Losango: projeção", "Subtle"))
        scene_layout.addLayout(scene_top)
        self.room_view = RoomView714()
        self.room_view.reduced_motion = self.reduced_motion.isChecked()
        self.room_view.stem_selected.connect(self._choose_source)
        self.room_view.placement_changed.connect(self._room_changed)
        self.room_view.stereo_toggled.connect(self._stereo_changed)
        self.room_view.copy_requested.connect(self._copy)
        self.room_view.paste_requested.connect(self._paste)
        self.room_view.duplicate_requested.connect(self._duplicate)
        self.room_view.delete_requested.connect(self._delete)
        self.room_view.seek_requested.connect(self._seek_relative)
        self.room_view.playback_toggle_requested.connect(self._toggle_preview)
        scene_layout.addWidget(self.room_view, 1)
        self.workspace.addWidget(center)

        inspector, right = _panel("Inspector")
        self.inspector_heading = _label("Inspetor de fonte", "Heading")
        right.addWidget(self.inspector_heading)
        self.inspector_hint = _label("Selecione uma fonte na lista ou na sala.", "Subtle")
        self.inspector_hint.setWordWrap(True)
        right.addWidget(self.inspector_hint)
        self.inspector_slot = QVBoxLayout()
        right.addLayout(self.inspector_slot)
        right.addStretch()
        rule = QFrame()
        rule.setObjectName("Line")
        rule.setFixedHeight(1)
        right.addWidget(rule)
        right.addWidget(_label("Direção espacial", "Heading"))
        self.combo_presets = QComboBox()
        for name, preset in (("Equilibrado", DirectorPreset.BALANCED), ("Imersão 360°", DirectorPreset.IMMERSION_360),
                             ("Palco ao vivo", DirectorPreset.LIVE_STAGE), ("Foco vocal", DirectorPreset.VOCAL_FOCUS),
                             ("Clube", DirectorPreset.CLUB_BASS)):
            self.combo_presets.addItem(name, preset.value)
        self.combo_presets.setAccessibleName("Estilo da direção automática")
        right.addWidget(self.combo_presets)
        strength = QHBoxLayout()
        strength.addWidget(_label("Intensidade"))
        self.intensity = QSlider(Qt.Horizontal)
        self.intensity.setAccessibleName("Intensidade da direção automática")
        self.intensity.setToolTip("Ajusta a abertura dos trechos, a seleção e o ganho dos microeventos ao aplicar a direção.")
        self.intensity.setRange(0, 100)
        self.intensity.setValue(70)
        self.intensity_value = _label("70%", "Clock")
        self.intensity_value.setMinimumWidth(self.intensity_value.fontMetrics().horizontalAdvance("100%") + 4)
        self.intensity_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.intensity.valueChanged.connect(lambda v: self.intensity_value.setText(f"{v}%"))
        strength.addWidget(self.intensity, 1)
        strength.addWidget(self.intensity_value)
        right.addLayout(strength)
        self.btn_direct = QPushButton("Aplicar direção aos trechos")
        self.btn_direct.clicked.connect(self._redirect)
        right.addWidget(self.btn_direct)

        self.combo_profile = QComboBox()
        self.combo_profile.addItem("JBL Bar 1000 MK2", "jbl")
        self.combo_profile.addItem("Referência de estúdio", "studio")
        self.combo_profile.setCurrentIndex(max(0, self.combo_profile.findData(self._profile)))
        self.combo_profile.setAccessibleName("Calibração da pré-escuta e da exportação")
        self.combo_profile.currentIndexChanged.connect(self._change_profile)
        right.addWidget(_label("Calibração do master", "Heading"))
        right.addWidget(self.combo_profile)
        scroll = QScrollArea()
        scroll.setAccessibleName("Inspetor e direção")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inspector)
        scroll.setMinimumWidth(296)
        self.workspace.addWidget(scroll)
        self.workspace.setStretchFactor(1, 1)
        self.workspace.setSizes([208, 884, 308])
        layout.addWidget(self.workspace, 1)

        self.timeline_widget = TimelineWidget(self.timeline_manager)
        self.timeline_widget.canvas.has_session = False
        self.timeline_widget.refresh_timeline()
        self.timeline_widget.section_selected.connect(self._select_section)
        self.timeline_widget.timeline_edited.connect(self._edited)
        self.timeline_widget.seek_requested.connect(self._seek)
        self.timeline_widget.micro_toggled.connect(self._set_micro_enabled)
        layout.addWidget(self.timeline_widget)
        transport, foot = _panel("Transport", 0)
        row = QHBoxLayout()
        row.setContentsMargins(16, 9, 16, 9)
        row.setSpacing(10)
        self.btn_play = QPushButton("Ouvir")
        self.btn_play.setObjectName("Primary")
        self.btn_play.setAccessibleName("Ouvir ou pausar a pré-escuta binaural")
        self.btn_play.clicked.connect(self._toggle_preview)
        row.addWidget(self.btn_play)
        self.time_label = _label("00:00 / 00:00", "Clock")
        row.addWidget(self.time_label)
        self.seek_bar = QSlider(Qt.Horizontal)
        self.seek_bar.setRange(0, 10000)
        self.seek_bar.setAccessibleName("Posição de reprodução")
        self.seek_bar.valueChanged.connect(lambda v: self._seek(self.live_player.total_duration_s*v/10000))
        row.addWidget(self.seek_bar, 2)
        self.combo_audio_dev = QComboBox()
        self.combo_audio_dev.setAccessibleName("Saída binaural")
        self.combo_audio_dev.addItem("Binaural  /  Padrão PipeWire", None)
        self.combo_audio_dev.setMaximumWidth(215)
        self.combo_audio_dev.currentIndexChanged.connect(
            lambda: self.live_player.set_output_device(self.combo_audio_dev.currentData()))
        row.addWidget(self.combo_audio_dev)
        row.addWidget(_label("Monitor", "Subtle"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setAccessibleName("Volume da pré-escuta")
        self.volume.setRange(0, 150)
        self.volume.setValue(100)
        self.volume.setMaximumWidth(78)
        self.volume.valueChanged.connect(lambda v: self.live_player.set_volume(v/100))
        row.addWidget(self.volume)
        self.export_btn = QToolButton()
        self.export_btn.setText("Exportar")
        self.export_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.export_btn.clicked.connect(self._export_dialog)
        delivery = QMenu(self.export_btn)
        delivery.addAction("Exportar arquivo…", self._export_dialog)
        delivery.addAction("Salvar MP4 para Rygel", self._quick_export)
        delivery.addAction("Enviar MP4 para a TV via DLNA", lambda: self._quick_export(True))
        delivery.addAction("Abrir master LPCM no DirectFrame", self._directframe_export)
        self.export_btn.setMenu(delivery)
        row.addWidget(self.export_btn)
        foot.addLayout(row)
        layout.addWidget(transport)

        self.status_label = _label("Pronto para abrir uma faixa.", "Status")
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.statusBar().addWidget(self.status_label, 1)
        self.progress = StudioProgressBar()
        self.progress.setMinimumWidth(240)
        self.progress.setMaximumWidth(320)
        self.progress.setFixedHeight(22)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setAccessibleName("Progresso da operação")
        self.statusBar().addPermanentWidget(self.progress, 1)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel)
        self.statusBar().addPermanentWidget(self.cancel_btn)
        self.statusBar().setSizeGripEnabled(False)

    def _discover_devices(self) -> None:
        if self._closing:
            return
        scan = SessionThread(LiveSpatialPlayer.get_available_devices, self)
        self._device_scan = scan
        def finished() -> None:
            self._device_scan = None
            if not self._closing:
                with QSignalBlocker(self.combo_audio_dev):
                    for dev in scan.result or []:
                        if dev["channels"] >= 2:
                            self.combo_audio_dev.addItem(dev["name"], dev["index"])
            else:
                QTimer.singleShot(0, self.close)
            scan.deleteLater()
        scan.finished.connect(finished, Qt.QueuedConnection)
        scan.start(QThread.LowPriority)

    def _notice(self, text: str, error: bool = False, *, success: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(text)
        self.status_label.setProperty("error", error)
        self.status_label.setProperty("success", success)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_reduced_motion(self, on: bool) -> None:
        self.settings.setValue("ui/reducedMotion", on)
        self.room_view.reduced_motion = on
        self.ui_poll_timer.setInterval(100 if on else 16)
        self._preview_ui = None
        self._poll_audio_state()

    def _update_theme_button(self) -> None:
        if self._current_theme == "light":
            self.btn_theme.setText("☀️ Claro")
            self.btn_theme.setToolTip("Tema visual: Claro. Clique para alternar para Escuro AMOLED.")
        else:
            self.btn_theme.setText("🌙 AMOLED")
            self.btn_theme.setToolTip("Tema visual: Escuro AMOLED. Clique para alternar para Claro.")

    def _toggle_theme(self) -> None:
        target = "light" if self._current_theme == "amoled" else "amoled"
        self._set_theme(target)

    def _set_theme(self, theme_name: str) -> None:
        if theme_name not in T.THEMES:
            theme_name = "amoled"
        self._current_theme = theme_name
        self.settings.setValue("ui/theme", theme_name)
        T.set_active_theme(theme_name)
        self.setStyleSheet(T.style_sheet(theme_name))
        self._update_theme_button()
        for idx in range(self.source_list.count()):
            item = self.source_list.item(idx)
            item.setForeground(QColor(T.INK))
        self.room_view.update()
        self.timeline_widget.refresh_timeline()

    def _sync_enabled(self) -> None:
        busy = self._task is not None
        ready = bool(self.current_stems)
        self.btn_open.setEnabled(not busy)
        self.combo_mode.setEnabled(not busy)
        self.cache_action.setEnabled(not busy)
        self.search_action.setEnabled(not busy)
        self.reanalyze_action.setEnabled(ready and not busy)
        self.btn_play.setEnabled(ready)
        self.seek_bar.setEnabled(ready)
        self.workspace.setEnabled(not busy)
        self.timeline_widget.setEnabled(ready and not busy)
        self.export_btn.setEnabled(ready and not busy)
        self.btn_direct.setEnabled(ready and not busy)
        self.progress.setVisible(busy)
        self.cancel_btn.setVisible(busy and self._task not in ("delivery", "clear-cache"))
        self.empty_sources.setVisible(not ready)
        self.source_list.setVisible(ready)

    def _base_request(self, action: str) -> dict:
        return {"action": action, "mode": self.session.get("mode", self.combo_mode.currentData()),
                "cache": str(self.cache_manager.base_dir), "preset": self.combo_presets.currentData(),
                "profile": self._profile, "intensity": self.intensity.value()/100}

    def _start(self, request: dict, message: str) -> bool:
        if self._task is not None:
            return False
        self._task = request["action"]
        self._cancelled = False
        self._result = None
        self._failure = ""
        self._stdout = b""
        self._stderr = b""
        self._request = request
        self._notice(message)
        self.progress.setRange(0, 0)
        self._sync_enabled()
        proc = QProcess(self)
        self._proc = proc
        env = QProcessEnvironment.systemEnvironment()
        # Os pools BLAS são criados ao importar NumPy, antes do main do processo.
        from ..separation.process_shield import get_shielded_thread_count
        threads = str(get_shielded_thread_count())
        for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
            env.insert(key, threads)
        env.insert("HF_HUB_OFFLINE", "1")
        for key in ("CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES"):
            env.insert(key, "")
        env.insert("ATMOSSPLIT_PARENT_PID", str(os.getpid()))
        proc.setProcessEnvironment(env)
        if sys.platform == "linux":
            proc.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        proc.setWorkingDirectory(str(ROOT))
        proc.setProgram(sys.executable)
        proc.setArguments(["-m", "src.separation.supervisor", "-m", "src.ui.studio_jobs"])
        payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
        def send_request() -> None:
            if self._cancelled or self._closing:
                proc.closeWriteChannel()
                proc.terminate()
                return
            proc.write(payload)
            proc.closeWriteChannel()
        proc.started.connect(send_request)
        proc.readyReadStandardOutput.connect(lambda: self._read_events(proc))
        proc.readyReadStandardError.connect(lambda: self._read_stderr(proc))
        proc.errorOccurred.connect(lambda error: self._process_error(proc, error))
        proc.finished.connect(lambda code, status: self._process_finished(proc, code))
        proc.start()
        return True

    def _read_events(self, proc: QProcess) -> None:
        if proc is not self._proc:
            return
        self._stdout += bytes(proc.readAllStandardOutput())
        lines = self._stdout.split(b"\n")
        self._stdout = lines.pop()
        for line in lines:
            try:
                data = json.loads(line)
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            kind = data.get("type")
            if kind == "done":
                self._result = data.get("result")
            elif kind == "error":
                self._failure = data["text"]
            elif kind == "progress" and not self._cancelled:
                value = data.get("value", -1)
                self.progress.setRange(0, 100 if value >= 0 else 0)
                if value >= 0:
                    percent = round(value * 100)
                    if self._task == "prepare":
                        # A etapa do worker termina antes da montagem local do monitor.
                        percent = min(percent, PREVIEW_PROGRESS - 1)
                    self.progress.setValue(percent)
                self._notice(data["text"])

    def _read_stderr(self, proc: QProcess) -> None:
        if proc is self._proc:
            self._stderr = (self._stderr + bytes(proc.readAllStandardError()))[-6000:]

    def _process_error(self, proc: QProcess, error) -> None:
        if error == QProcess.FailedToStart and proc is self._proc:
            self._failure = proc.errorString()
            self._process_finished(proc, -1)

    def _process_finished(self, proc: QProcess, code: int) -> None:
        if proc is not self._proc:
            return
        self._read_events(proc)
        self._read_stderr(proc)
        proc.deleteLater()
        self._proc = None
        if self._cancelled:
            self._end_task("Operação cancelada.")
            return
        if code != 0 or self._result is None:
            error = self._failure or self._stderr.decode("utf8", errors="replace").strip() or "O processo encerrou sem resultado."
            self._end_task(error, error=True)
            return
        result, action = self._result, self._task
        try:
            if action == "prepare":
                self._prepare_preview(result)
            elif action == "redirect":
                self.timeline_manager.set_sections(unpack_sections(result["sections"]))
                self.session["preset"] = self.combo_presets.currentData()
                self.session["intensity"] = self.intensity.value()
                self._manual = False
                self._activate_section(self.timeline_manager.get_section_at_time(self.live_player.current_time_s).id)
                self._publish()
                self._preview_ui = None
                self._poll_audio_state()
                self._queue_save()
                self._end_task("Direção aplicada às seções.")
            elif action == "export":
                self._export_complete(result)
            elif action == "search":
                self._end_task("")
                self._show_search_results(result["results"])
            elif action == "download":
                self._end_task("")
                self._load_and_process_audio_path(result["path"])
        except Exception as exc:
            log.exception("Falha ao concluir %s", action)
            self._end_task(str(exc), error=True)

    def _end_task(self, text: str, error: bool = False, *, success: bool = False) -> None:
        self._task = None
        if self._export_stage:
            self._export_stage.cleanup()
            self._export_stage = None
        self._sync_enabled()
        if text:
            self._notice(text, error, success=success)
        if self._closing:
            QTimer.singleShot(0, self.close)

    def _thread_job(self, fn, on_done) -> None:
        thread = SessionThread(fn, self)
        self._thread = thread
        def finished() -> None:
            self._thread = None
            try:
                if self._cancelled:
                    self._end_task("Operação cancelada.")
                elif thread.error:
                    self._end_task(thread.error, error=True)
                else:
                    on_done(thread.result)
            except Exception as exc:
                log.exception("Falha ao instalar a sessão")
                self._end_task(str(exc), error=True)
            finally:
                thread.deleteLater()
        thread.finished.connect(finished, Qt.QueuedConnection)
        thread.start(QThread.LowPriority)

    def _cancel(self) -> None:
        self._cancelled = True
        self._notice("Encerrando a operação…")
        proc = self._proc
        if proc and proc.state() != QProcess.NotRunning:
            # O supervisor permanece vivo até recolher o último descendente.
            proc.terminate()
        if self._thread:
            self._thread.requestInterruption()

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir faixa", str(Path.home() / "Music"), AUDIO_FILTER)
        if path:
            self._load_and_process_audio_path(path)

    def _load_and_process_audio_path(self, path: str, restore: bool = True) -> None:
        self._save_arrangement()
        request = self._base_request("prepare")
        request.update(path=str(path), mode=self.combo_mode.currentData(), restore=restore, session_dir=str(self.session_dir))
        if not restore and path == self.session.get("path"):
            request["micro_enabled"] = self.timeline_widget.btn_micro.isChecked()
        self._start(request, "Preparando a faixa…")

    def _prepare_preview(self, result: dict) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(PREVIEW_PROGRESS)
        self._notice("Montando o monitor binaural e preparando palco 7.1.4…")
        mode = self._request["mode"]
        result["mode"] = mode
        timeline = SpatialTimelineManager()
        sections = unpack_sections(result.pop("sections"))
        timeline.set_sections(sections)
        restored = result["restored"]
        profile, cache = self._profile, self.cache_manager
        def load():
            stems = DeepStemEngine(cache).load_cached_result(result["hash"], mode)
            if not stems:
                raise RuntimeError("O cache ficou indisponível. Abra a faixa novamente.")
            player = LiveSpatialPlayer(sample_rate=48000, profile=profile)
            if not QThread.currentThread().isInterruptionRequested():
                player.set_timeline_manager(timeline)
                player.set_stems_and_placements(stems.stems, timeline.get_active_edit_section().placements)
            return stems.stems, player
        def install(data):
            stems, player = data
            self.live_player.stop()
            self.live_player = player
            self.live_player.set_output_device(self.combo_audio_dev.currentData())
            self.live_player.set_volume(self.volume.value()/100)
            self.current_stems = stems
            self._sources = {s.name: s for s in stems}
            self.session = result
            self._clipboard = None
            self._manual = bool(restored and result.get("manual"))
            self._dirty = False
            self.timeline_manager = timeline
            self.timeline_widget.timeline_manager = timeline
            self.timeline_widget.canvas.timeline_manager = timeline
            self.timeline_widget.canvas.has_session = True
            self.timeline_widget.canvas.set_view(1.0, 0.0)
            self.track_label.setText(f"{result['artist']}   /   {result['title']}")
            self.track_label.setToolTip(str(result["path"]))
            self.combo_presets.setCurrentIndex(max(0, self.combo_presets.findData(result["preset"])))
            self.intensity.setValue(result["intensity"])
            self._activate_section(timeline.get_active_edit_section().id)
            self._preview_ui = None
            self._poll_audio_state()
            self.progress.setValue(100)
            warning = result.get("warning")
            self._end_task(warning or ("Concluído · Automação restaurada." if restored else
                           "Concluído · Faixa pronta para ouvir e editar."), success=not warning)
            if not restored or result.get("micro_migrated"):
                self._queue_save()
        self._thread_job(load, install)

    def _activate_section(self, section_id: str) -> None:
        sec = self.timeline_manager.get_section_by_id(section_id)
        if sec is None:
            return
        self.timeline_manager.active_edit_section_id = section_id
        previous = self.room_view.active_stem_name
        self.room_view.set_stems_and_placements(self.current_stems, sec.placements)
        with QSignalBlocker(self.source_list):
            self.source_list.clear()
            for name, stem in self.room_view.stems.items():
                item = QListWidgetItem(stem.display_name)
                item.setData(Qt.UserRole, name)
                item.setForeground(QColor(T.INK))
                item.setToolTip(stem.display_name)
                swatch = self._source_swatch(stem.color_hex)
                item.setIcon(swatch)
                self.source_list.addItem(item)
            self.source_list.setCurrentRow(-1)
        name = previous if previous in self.room_view.stems else self.room_view.active_stem_name
        self._choose_source(name)
        self.timeline_widget.refresh_timeline()
        self.source_count.setText(f"{len(sec.placements)} fontes neste trecho")
        self._update_item_states()

    def _source_swatch(self, color: str) -> QIcon:
        swatch = QPixmap(5, 16)
        swatch.fill(QColor(color))
        return QIcon(swatch)

    def _update_item_states(self) -> None:
        plcs = self.current_placements
        for idx in range(self.source_list.count()):
            item = self.source_list.item(idx)
            name = item.data(Qt.UserRole)
            plc = plcs[name]
            stem = self.room_view.stems.get(name) or self._sources.get(plc.source_stem_name or name)
            if stem:
                suffix = "   [Mudo]" if plc.is_muted else ("   [Solo]" if plc.is_solo else "")
                item.setText(stem.display_name + suffix)

    def _choose_source(self, name: str | None) -> None:
        if self._inspector:
            self.inspector_slot.removeWidget(self._inspector)
            self._inspector.hide()
            self._inspector.deleteLater()
            self._inspector = None
        self.inspector_hint.setVisible(name is None)
        if not name or name not in self.current_placements or name not in self.room_view.stems:
            return
        # A seleção pelo mapa e pela lista compartilha a mesma identidade da instância.
        with QSignalBlocker(self.room_view):
            self.room_view.set_active_stem(name)
        with QSignalBlocker(self.source_list):
            for i in range(self.source_list.count()):
                if self.source_list.item(i).data(Qt.UserRole) == name:
                    self.source_list.setCurrentRow(i)
                    break
        card = StemControlCard(self.room_view.stems[name], self.current_placements[name])
        card.changed.connect(self._card_changed)
        card.duplicate_requested.connect(self._duplicate)
        card.delete_requested.connect(self._delete)
        self.inspector_slot.addWidget(card)
        self._inspector = card

    def _select_list_source(self, item, previous) -> None:
        if item:
            self._choose_source(item.data(Qt.UserRole))

    def _card_changed(self, name: str) -> None:
        p = self.current_placements[name]
        self.room_view.update_placement(name, p.x, p.y, p.z, p.is_stereo)
        self._update_item_states()
        self._edited()

    def _stereo_changed(self, name: str, stereo: bool) -> None:
        if name in self.current_placements:
            self.current_placements[name].is_stereo = stereo

    def _room_changed(self, name: str, x: float, y: float, z: float) -> None:
        if name in self.current_placements:
            p = self.current_placements[name]
            p.x, p.y, p.z = x, y, z
            if self._inspector and self._inspector.placement is p:
                self._inspector.sync_from_placement()
            self._edited()

    def _publish(self) -> None:
        self.live_player.set_active_placements(self.current_placements)

    def _edited(self) -> None:
        self._manual = True
        self._publish()
        self._preview_ui = None
        self._queue_save()

    def _set_micro_enabled(self, enabled: bool) -> None:
        if not self.session:
            return
        for section in self.timeline_manager.sections:
            section.micro_enabled = enabled
        self.timeline_widget.refresh_timeline()
        self._publish()
        self._preview_ui = None
        self._poll_audio_state()
        self._queue_save()

    def _queue_save(self) -> None:
        self._dirty = True
        self.save_timer.start()

    def _copy(self, name: str) -> None:
        if name in self.current_placements:
            self._clipboard = copy.copy(self.current_placements[name])
            self._notice(f"Posição copiada de {self.room_view.stems[name].display_name}.")

    def _paste(self) -> None:
        if self._clipboard:
            self._duplicate(self._clipboard.stem_name, self._clipboard)
        elif self.room_view.active_stem_name:
            self._duplicate(self.room_view.active_stem_name)

    def _duplicate(self, name: str, copied: SpatialPlacement | None = None) -> None:
        original = copied or self.current_placements.get(name)
        if original is None:
            return
        base = original.source_stem_name or name.split("::")[0]
        if base not in self._sources:
            return
        i = 2
        while f"{base}::{i}" in self.current_placements:
            i += 1
        p = copy.copy(original)
        p.stem_name, p.source_stem_name = f"{base}::{i}", base
        if copied is None:
            p.x = min(1.0, p.x+0.1)
        self.current_placements[p.stem_name] = p
        self._activate_section(self.timeline_manager.active_edit_section_id)
        self._choose_source(p.stem_name)
        self._edited()

    def _delete(self, name: str) -> None:
        if name in self.current_placements and "::" in name:
            del self.current_placements[name]
            self._activate_section(self.timeline_manager.active_edit_section_id)
            self._edited()

    def _select_section(self, section_id: str) -> None:
        self._activate_section(section_id)
        sec = self.timeline_manager.get_active_edit_section()
        self._seek(sec.start_time_s)
        self._notice(sec.description or sec.name)

    def _poll_audio_state(self) -> None:
        _immunize_cpython_none_refcount()
        cur, duration, vu, sub, playing = self.live_player.get_ui_snapshot()
        state = (cur, duration, playing, self.live_player.last_error, self.live_player.underruns)
        if state == self._preview_ui:
            return
        previous = self._preview_ui
        self._preview_ui = state
        if previous is None or (int(cur), int(duration)) != (int(previous[0]), int(previous[1])):
            self.time_label.setText(f"{_clock(cur)} / {_clock(duration)}")
        if not self.seek_bar.isSliderDown():
            with QSignalBlocker(self.seek_bar):
                self.seek_bar.setValue(round(cur/max(0.001, duration)*10000))
        self.timeline_widget.set_current_playback_time(cur)
        if self.current_stems and not self.room_view._is_dragging and (
                playing or previous is None or cur != previous[0] or playing != previous[2]):
            sec = self.timeline_manager.get_section_at_time(cur)
            if sec.id != self.timeline_manager.active_edit_section_id:
                self._activate_section(sec.id)
            poses = self.timeline_manager.get_interpolated_placements(cur)
            events = tuple(ev for ev in self.timeline_widget.canvas.micro_lane.active_at(cur)
                           if f"{ev.stem}::micro" in poses)
            if self.reduced_motion.isChecked() and playing:
                # Mostra um ponto estável por evento, sem animar trajetórias ou medidores.
                if previous is None or events != self.room_view.micro_events:
                    self.room_view.set_playback_placements({**sec.placements,
                        **{key: p for key, p in poses.items() if key.endswith("::micro")}})
            else:
                self.room_view.set_playback_placements(poses)
            self.room_view.set_micro_events(events)
            # Uma sílaba pode durar menos que o tempo de leitura do nome.
            # Na pausa ou no seek, a legenda volta a corresponder exatamente ao cursor.
            recent = (not events and playing and previous is not None and sec.micro_enabled
                      and 0 <= cur-previous[0] < .25 and bool(self._caption_events)
                      and 0 <= cur-max(ev.end_s for ev in self._caption_events) < .9)
            self._show_event_caption(self._caption_events if recent else events, recent)
        self.room_view.set_vu_levels(vu if playing else {}, sub if playing else 0)
        if previous is None or playing != previous[2]:
            self.btn_play.setText("Pausar" if playing else "Ouvir")
        if state[3] and (previous is None or state[3] != previous[3]):
            self._notice(f"Saída de áudio indisponível. {state[3]}", error=True)
        if previous is None or state[4] != previous[4]:
            self.combo_audio_dev.setToolTip(f"Monitor binaural em dois canais. Falhas de buffer: {state[4]}.")

    def _show_event_caption(self, events: tuple, recent: bool) -> None:
        if events == self._caption_events and recent == self._caption_recent:
            return
        self._caption_events, self._caption_recent = events, recent
        caption = "   /   ".join(event_title(ev) for ev in events)
        if recent:
            caption = f"Anterior  ·  {caption}"
        self.event_caption.setText(caption)
        detail = "\n\n".join(event_details(ev) for ev in events)
        self.event_caption.setToolTip(detail)
        self.event_caption.setAccessibleDescription(detail)

    def _toggle_preview(self) -> None:
        if not self.current_stems:
            return
        if self.live_player.is_playing:
            self.live_player.pause()
        else:
            if self.live_player.current_time_s >= self.live_player.total_duration_s - 0.001:
                self.live_player.seek_seconds(0.0)
            self.live_player.play()
        self._poll_audio_state()

    def _seek(self, time_s: float) -> None:
        if self.current_stems:
            self.live_player.seek_seconds(time_s)
            self._preview_ui = None
            self._poll_audio_state()

    def _seek_relative(self, seconds: float) -> None:
        self._seek(max(0.0, min(self.live_player.total_duration_s, self.live_player.current_time_s + seconds)))

    def _confirm_direction(self) -> bool:
        if not self._manual:
            return True
        return QMessageBox.question(self, "Substituir ajustes manuais?",
                                    "A direção vai recalcular as posições e os volumes que você editou.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def _redirect(self) -> None:
        if self.session and self._confirm_direction():
            req = self._base_request("redirect")
            req.update(hash=self.session["hash"], sections=pack_sections(self.timeline_manager.sections))
            self._start(req, "Aplicando o estilo às seções musicais…")

    def _reanalyze(self) -> None:
        if self.session and self._confirm_direction():
            self._load_and_process_audio_path(self.session["path"], restore=False)

    def _change_profile(self) -> None:
        requested = self.combo_profile.currentData()
        if self._profile == requested:
            return
        if self.current_stems:
            if self._task is not None:
                return
            self._task = "profile"
            self._cancelled = False
            self._sync_enabled()
            self._notice("Preparando a monitoração com a calibração selecionada…")
            self.progress.setRange(0, 0)
            with QSignalBlocker(self.combo_profile):
                self.combo_profile.setCurrentIndex(self.combo_profile.findData(self._profile))
            stems = self.current_stems
            timeline = self.timeline_manager
            plcs = self.current_placements
            def build():
                player = LiveSpatialPlayer(sample_rate=48000, profile=requested)
                player.set_timeline_manager(timeline)
                player.set_stems_and_placements(stems, plcs)
                return player
            def install(player):
                cur, playing = self.live_player.current_time_s, self.live_player.is_playing
                self.live_player.stop()
                self.live_player = player
                player.set_output_device(self.combo_audio_dev.currentData())
                player.set_volume(self.volume.value()/100)
                player.seek_seconds(cur)
                if playing:
                    player.play()
                self._profile = requested
                with QSignalBlocker(self.combo_profile):
                    self.combo_profile.setCurrentIndex(self.combo_profile.findData(requested))
                self.settings.setValue("monitor/profile", requested)
                self._preview_ui = None
                self._end_task("Calibração aplicada ao monitor e à exportação.")
            self._thread_job(build, install)
        else:
            self._profile = requested
            self.settings.setValue("monitor/profile", requested)

    def _save_arrangement(self) -> None:
        if not self._dirty or not self.session:
            return
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            path = self.session_dir / f"{self.session['hash']}_{self.session['mode']}.json"
            payload = {"version": 1, "sections": pack_sections(self.timeline_manager.sections),
                       "preset": self.session["preset"], "intensity": self.session["intensity"], "manual": self._manual}
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf8")
            save = QSaveFile(str(path))
            if not save.open(QIODevice.WriteOnly) or save.write(data) != len(data) or not save.commit():
                raise OSError(save.errorString())
            self._dirty = False
        except (OSError, ValueError) as exc:
            self._notice(f"Falha ao salvar a automação local. {exc}", error=True)

    def _on_search_clicked(self) -> None:
        query, ok = QInputDialog.getText(self, "Buscar música online", "Artista ou faixa")
        if ok and query.strip():
            self._start({"action": "search", "query": query.strip()}, "Buscando música online…")

    def _show_search_results(self, results: list[dict]) -> None:
        if not results:
            self._notice("A busca online não trouxe resultados. Você também pode abrir um arquivo local.")
            return
        labels = [f"{i+1}. {r['artist']} — {r['title']} ({r['format_label']})" for i, r in enumerate(results)]
        label, ok = QInputDialog.getItem(self, "Resultados da busca", "Selecione uma faixa para baixar",
                                         labels, 0, False)
        if ok:
            self._start({"action": "download", "item": results[labels.index(label)]}, "Baixando a faixa…")

    def _default_dest(self, suffix: str) -> Path:
        root = Path.home() / "Music" / "DolbyAtmos"
        base = self.session.get("title", "Mixagem").replace("/", "-").strip() or "Mixagem"
        return root / f"{base[:120]} [7.1.4]{suffix}"

    def _export_dialog(self) -> None:
        if not self.session:
            return
        path, selected = QFileDialog.getSaveFileName(self, "Exportar mixagem", str(self._default_dest(".mp4")),
                                                     ";;".join(EXPORT_FORMATS))
        if path and selected in EXPORT_FORMATS:
            suffix = selected.rsplit("*", 1)[1].rstrip(")")
            dest = Path(path)
            if dest.suffix.lower() != suffix:
                dest = dest.with_suffix(suffix)
                if dest.exists() and not self._confirm_overwrite(dest):
                    return
            self._export(dest, EXPORT_FORMATS[selected])

    def _confirm_overwrite(self, path: Path) -> bool:
        return QMessageBox.question(self, "Substituir exportação?", f"Já existe um arquivo em {path}. Substituir?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def _quick_export(self, dlna: bool = False) -> None:
        dest = self._default_dest(".mp4")
        if not dest.exists() or self._confirm_overwrite(dest):
            self._export(dest, ExportFormat.MP4_ATMOS_JOC_714, "dlna" if dlna else "")

    def _directframe_export(self) -> None:
        dest = self._default_dest(".mkv")
        if not dest.exists() or self._confirm_overwrite(dest):
            self._export(dest, ExportFormat.MKV_LPCM_714, "hdmi")

    def _export(self, dest: Path, fmt: ExportFormat, delivery: str = "") -> None:
        if not self.session or self._task:
            return
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            self._export_stage = tempfile.TemporaryDirectory(prefix=".atmossplit-", dir=dest.parent)
        except OSError as exc:
            self._notice(f"Não foi possível criar o arquivo de entrega. {exc}", error=True)
            return
        req = self._base_request("export")
        req.update(hash=self.session["hash"], path=self.session["path"], format=fmt.value, dest=str(dest),
                   delivery=delivery, staging=str(Path(self._export_stage.name)/dest.name),
                   sections=pack_sections(self.timeline_manager.sections))
        self._start(req, "Preparando o render da faixa…")

    def _export_complete(self, result: dict) -> None:
        dest = Path(self._request["dest"])
        os.replace(self._request["staging"], dest)
        delivery = self._request["delivery"]
        report = result["report"]
        def measure(key: str, unit: str) -> str:
            v = report.get(key)
            return f"{v:.1f} {unit}" if v is not None else "indisponível"
        summary = (f"Master PCM {measure('integrated_lufs', 'LUFS')}, pico {measure('true_peak_dbtp', 'dBTP')}. "
                   f"Voz/instrumental {measure('vocal_balance_db', 'dB')}, presença {measure('presence_balance_db', 'dB')}.")
        if "trim_db" in result["report"]:
            summary += f" JOC decodificado {measure('decoded_true_peak_dbtp', 'dBTP')}, ajuste {measure('trim_db', 'dB')}."
        if not delivery:
            self._end_task(f"Salvo em {dest}. {summary}")
            return
        self._task = "delivery"
        self._sync_enabled()
        self._notice(f"Arquivo salvo. Conectando o reprodutor… {summary}")
        def deliver():
            return (SamsungDLNABridge().cast_file_to_soundbar(dest, auto_picture_off=True)
                    if delivery == "dlna" else DirectFrameBridge().play_multichannel_file(dest))
        def delivered(ok: bool):
            device = "TV via DLNA" if delivery == "dlna" else "DirectFrame / mpv"
            text = f"Reprodução solicitada em {device}." if ok else f"Não foi possível iniciar {device}."
            self._end_task(f"{text} Arquivo salvo em {dest}. {summary}", error=not ok)
        self._thread_job(deliver, delivered)

    def _cache_dialog(self) -> None:
        if self._task is not None:
            return
        self._task = "list-cache"
        self._cancelled = False
        self._sync_enabled()
        self.progress.setRange(0, 0)
        self._notice("Consultando o cache de stems…")
        self._thread_job(self.cache_manager.list_cached_tracks, self._show_cache)

    def _show_cache(self, tracks: list[dict]) -> None:
        self._end_task("Cache de stems disponível.")
        dlg = QDialog(self)
        dlg.setWindowTitle("Cache de stems")
        dlg.resize(520, 330)
        box = QVBoxLayout(dlg)
        total = sum(t["size_bytes"] for t in tracks) / 1048576
        box.addWidget(_label(f"{len(tracks)} entradas   /   {total:.1f} MiB", "Heading"))
        table = QTableWidget(len(tracks), 3)
        table.setHorizontalHeaderLabels(["Faixa e modo", "Stems", "MiB"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, track in enumerate(tracks):
            for col, text in enumerate((f"{track['file_hash'][:12]} / {track['mode']}",
                                        str(track["stems_count"]), str(track["size_mb"]))):
                table.setItem(i, col, QTableWidgetItem(text))
        box.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        clear = buttons.addButton("Limpar faixas fora da sessão" if self.session else "Limpar cache", QDialogButtonBox.DestructiveRole)
        clear.setEnabled(bool(tracks))
        clear.clicked.connect(lambda: self._clear_cache(dlg))
        buttons.rejected.connect(dlg.reject)
        box.addWidget(buttons)
        dlg.exec()

    def _clear_cache(self, dlg: QDialog) -> None:
        if QMessageBox.question(dlg, "Limpar o cache de stems?",
                                "As próximas aberturas precisarão de uma nova separação. As automações serão mantidas.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            keep = (self.session["hash"], self.session["mode"]) if self.session else None
            dlg.accept()
            self._task = "clear-cache"
            self._cancelled = False
            self._sync_enabled()
            self._notice("Liberando espaço no cache…")
            self._thread_job(lambda: self.cache_manager.clear_cache(keep=keep),
                             lambda freed: self._end_task(f"{freed/1048576:.1f} MiB liberados no cache."))

    def _help(self) -> None:
        QMessageBox.information(self, "Atalhos do estúdio",
                                "Ctrl+O   Abrir faixa\nEspaço   Ouvir ou pausar\n← / →   Mover cinco segundos\n"
                                "↑ / ↓   Ajustar altura da fonte\nM / S   Mudo ou solo\nD   Espelhar em estéreo\n"
                                "0   Centralizar\n1–5   Escolher o estilo da direção\nCtrl+C / Ctrl+V   Copiar e colar fonte\n"
                                "← / → na trilha de microeventos   Ir ao evento anterior ou seguinte\n"
                                "Delete   Remover cópia\nCtrl+roda   Zoom na timeline\nRoda na sala   Ajustar altura")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_Space:
            self._toggle_preview()
        elif key in (Qt.Key_Right, Qt.Key_Left):
            self._seek_relative(5.0 if key == Qt.Key_Right else -5.0)
        elif self._task or not self.current_stems:
            super().keyPressEvent(event)
            return
        elif Qt.Key_1 <= key <= Qt.Key_5:
            self.combo_presets.setCurrentIndex(int(key)-int(Qt.Key_1))
            self._redirect()
        elif self._inspector and key in (Qt.Key_M, Qt.Key_S):
            (self._inspector.btn_mute if key == Qt.Key_M else self._inspector.btn_solo).click()
        elif key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_0, Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_D) or (
                key in (Qt.Key_C, Qt.Key_V) and event.modifiers() & Qt.ControlModifier):
            self.room_view.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def dragEnterEvent(self, event) -> None:
        if not any(url.isLocalFile() for url in event.mimeData().urls()):
            event.ignore()
        elif self._task is not None:
            self._notice(BUSY_DROP_NOTICE, error=True)
            event.ignore()
        else:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self._task is not None:
            self._notice(BUSY_DROP_NOTICE, error=True)
            event.ignore()
            return
        for url in event.mimeData().urls():
            if url.isLocalFile() and Path(url.toLocalFile()).is_file():
                self._load_and_process_audio_path(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()

    def closeEvent(self, event) -> None:
        self.ui_poll_timer.stop()
        self.save_timer.stop()
        self._save_arrangement()
        self.live_player.stop()
        self._closing = True
        if self._proc or self._thread or self._device_scan:
            self._cancel()
            event.ignore()
            return
        super().closeEvent(event)


def run_app() -> int:
    if sys.platform == "linux":
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")
    app = QApplication(sys.argv)
    app.setApplicationName("AtmosSplit")
    _immunize_cpython_none_refcount()
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        path = next((Path(a) for a in sys.argv[1:] if Path(a).is_file()), None)
        if path:
            QTimer.singleShot(0, lambda: window._load_and_process_audio_path(str(path)))
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
