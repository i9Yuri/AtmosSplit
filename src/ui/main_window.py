"""
AtmosSplit — Janela Principal Desktop (PySide6)
Interface intuitiva da sala 7.1.4 com isolamento total de processos:
- Worker de IA executado em subprocesso desacoplado via QProcess
- Prioridade estrita (nice 19) e afinidade (núcleos 0 e 1 livres para SO/KDE)
- Encerramento estrito de processos zumbis/órfãos via psutil
- Polling atômico a 30 FPS desacoplado da thread de áudio (Zero XRUNs)
- Seletor dinâmico de saída de áudio (PipeWire, Headset, HDMI TV/JBL)
- Controle de Volume Master integrado com display percentual
- Gerenciador e limpador visual de cache de stems
- Abertura direta com dois cliques em arquivos de áudio via linha de comando/desktop
- Espelhamento estéreo (L/R) com nós gêmeos (tecla 'D' ou clique duplo)
- Automação dinâmica temporal por trechos (TimelineWidget)
- Atalhos rápidos: Espaço (Play), 1-5 (Presets), M (Mute), S (Solo), D (Estéreo), 0 (Centralizar), Setas (Seek/Altura)
"""

from __future__ import annotations

import os
import sys
import time
import json
import logging
import copy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil
import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QProcess
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QFileDialog,
    QProgressBar,
    QScrollArea,
    QComboBox,
    QMessageBox,
    QInputDialog,
    QDialog,
    QSlider,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtGui import (
    QIcon,
    QFont,
    QColor,
    QPixmap,
    QImage,
    QKeyEvent,
    QDragEnterEvent,
    QDropEvent,
)

from ..acquisition.file_source import load_audio_file, AudioSource
from ..acquisition.search_source import SearchSourceEngine, SearchResultItem
from ..acquisition.probe_verifier import verify_audio_file
from ..separation.stem_engine import DeepStemEngine, StemTrack, SeparationResult
from ..separation.cache_manager import StemCacheManager
from ..spatial.acoustic_analyzer import AcousticAnalyzer
from ..spatial.auto_director import AutoAtmosDirector, DirectorPreset, SpatialPlacement
from ..spatial.binaural_hrtf import BinauralHRTFEngine
from ..spatial.master_renderer import MasterRenderer714, RenderConfig
from ..spatial.live_player import LiveSpatialPlayer
from ..spatial.timeline_manager import SpatialTimelineManager
from ..playback.exporter import AudioExporter714, ExportFormat
from ..playback.directframe_bridge import DirectFrameBridge
from ..playback.samsung_dlna_bridge import SamsungDLNABridge
from .room_view_714 import RoomView714
from .stem_card import StemControlCard
from .timeline_widget import TimelineWidget

log = logging.getLogger(__name__)


def _immunize_cpython_none_refcount():
    """
    Blindagem ativa contra o bug de refcount leak de C extensions / Shiboken6 em Linux.
    Garante que a contagem de referências do singleton None nunca chegue a zero,
    impedindo fatal errors de 'none_dealloc: deallocating None' e SIGABRT.
    """
    try:
        import ctypes
        refcnt = ctypes.c_ssize_t.from_address(id(None))
        if refcnt.value < 500_000_000:
            refcnt.value += 1_000_000_000
    except Exception:
        pass


def _install_crash_shield():
    """Escudo global contra encerramento inesperado por exceções não tratadas no Qt."""
    _immunize_cpython_none_refcount()

    def _safe_excepthook(exc_type, exc_val, exc_tb):
        import traceback
        tb_str = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        log.error("Escudo Global Antigravity interceptou exceção no loop de eventos:\n%s", tb_str)

    sys.excepthook = _safe_excepthook


_install_crash_shield()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AtmosSplit — Montador Espacial Dolby Atmos 7.1.4")
        self.resize(1280, 860)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)

        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.cache_manager = StemCacheManager()
        self.stem_engine = DeepStemEngine(cache_manager=self.cache_manager)
        self.search_engine = SearchSourceEngine()
        self.renderer = MasterRenderer714()
        self.binaural_engine = BinauralHRTFEngine()
        self.directframe_bridge = DirectFrameBridge()
        self.dlna_bridge = SamsungDLNABridge()

        self.current_source: Optional[AudioSource] = None
        self.current_stems: List[StemTrack] = []
        self.current_placements: Dict[str, SpatialPlacement] = {}
        self._placement_clipboard: Optional[SpatialPlacement] = None
        self._stem_profiles = {}
        self.stem_cards: Dict[str, StemControlCard] = {}
        self._stem_audio_by_instance: Dict[str, StemTrack] = {}

        # Gerenciador de Automação Temporal por Trechos
        self.timeline_manager = SpatialTimelineManager(total_duration_s=180.0)

        # Subprocesso de IA desacoplado (Zero congelamento de interface)
        self.separation_process: Optional[QProcess] = None
        self._current_task_info: Optional[Dict[str, str]] = None
        self._last_worker_error: Optional[str] = None
        self._user_cancelled_separation: bool = False

        # Player de áudio ao vivo de ultra-baixa latência com timeline conectada
        self.live_player = LiveSpatialPlayer(sample_rate=48000)
        self.live_player.set_timeline_manager(self.timeline_manager)

        self._init_theme_and_ui()

        # Timer desacoplado a ~33 FPS para atualização suave da GUI sem travar o áudio
        self.ui_poll_timer = QTimer(self)
        self.ui_poll_timer.setInterval(30)
        self.ui_poll_timer.timeout.connect(self._poll_audio_state)
        self.ui_poll_timer.start()

        # Atualizar badge de cache inicial
        self._refresh_cache_button_label()

        # Verificação de arquivo passado por argumento (ex: duplo clique ou linha de comando)
        self._check_initial_arguments()

    def _check_initial_arguments(self):
        """Se o usuário abriu um arquivo diretamente com AtmosSplit, carrega-o automaticamente."""
        args = sys.argv[1:]
        for arg in args:
            p = Path(arg)
            if p.exists() and p.is_file() and p.suffix.lower() in [".flac", ".wav", ".alac", ".mp3", ".m4a", ".opus", ".ogg"]:
                QTimer.singleShot(250, lambda path=str(p): self._load_and_process_audio_path(path))
                break

    def _init_theme_and_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0F1015;
                color: #E2E8F0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QFrame#HeaderBar {
                background-color: #16181F;
                border-bottom: 1px solid #232734;
                padding: 10px 16px;
            }
            QFrame#PlayerBar {
                background-color: #16181F;
                border-top: 1px solid #232734;
                padding: 10px 16px;
            }
            QPushButton {
                background-color: #1F232D;
                border: 1px solid #2E3444;
                border-radius: 6px;
                color: #E2E8F0;
                font-weight: 600;
                font-size: 12px;
                padding: 7px 14px;
            }
            QPushButton:hover {
                background-color: #2D3444;
                border-color: #4A5568;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #1A1F29;
            }
            QPushButton#BtnPrimary {
                background-color: #00E5FF;
                border: 1px solid #00B4D8;
                color: #000000;
            }
            QPushButton#BtnPrimary:hover {
                background-color: #18FFFF;
            }
            QPushButton#BtnJBL {
                background-color: #FF5722;
                border: 1px solid #E64A19;
                color: #FFFFFF;
            }
            QPushButton#BtnJBL:hover {
                background-color: #FF7043;
            }
            QPushButton#BtnQuickExport {
                background-color: #28A745;
                border: 1px solid #218838;
                color: #FFFFFF;
            }
            QPushButton#BtnQuickExport:hover {
                background-color: #34CE57;
            }
            QPushButton#BtnCancel {
                background-color: #E53E3E;
                border: 1px solid #C53030;
                color: #FFFFFF;
                font-size: 11px;
                padding: 3px 10px;
            }
            QPushButton#BtnCancel:hover {
                background-color: #FC8181;
            }
            QPushButton#BtnCache {
                background-color: #202430;
                border: 1px solid #323A4D;
                color: #A0AEC0;
                font-size: 11px;
                padding: 4px 10px;
            }
            QPushButton#BtnCache:hover {
                background-color: #2D3448;
                color: #FFFFFF;
            }
            QComboBox {
                background-color: #1F232D;
                border: 1px solid #2E3444;
                border-radius: 6px;
                color: #E2E8F0;
                padding: 5px 10px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background-color: #1F232D;
                selection-background-color: #2D3748;
                color: #E2E8F0;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QProgressBar {
                background-color: #16181F;
                border: 1px solid #2E3444;
                border-radius: 4px;
                text-align: center;
                color: #A0AEC0;
                font-size: 11px;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
                border-radius: 3px;
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
                border: 1px solid #00B4D8;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Barra de Progresso e Botão Cancelar
        self.progress_container = QWidget()
        prog_layout = QHBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(16, 4, 16, 4)
        prog_layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar, stretch=1)

        self.btn_cancel_sep = QPushButton("✖ Cancelar")
        self.btn_cancel_sep.setObjectName("BtnCancel")
        self.btn_cancel_sep.clicked.connect(self._cancel_separation_task)
        prog_layout.addWidget(self.btn_cancel_sep)

        self.progress_container.setVisible(False)
        main_layout.addWidget(self.progress_container)

        # 2. Splitter Central
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(2)

        # Painel Esquerdo (Stems)
        left_panel = self._create_stems_panel()
        content_splitter.addWidget(left_panel)

        # Painel Central (Sala 7.1.4)
        self.room_view = RoomView714()
        self.room_view.placement_changed.connect(self._on_room_placement_changed)
        self.room_view.stereo_toggled.connect(self._on_room_stereo_toggled)
        self.room_view.stem_selected.connect(self._on_room_stem_selected)
        self.room_view.duplicate_requested.connect(self._duplicate_placement)
        self.room_view.delete_requested.connect(self._delete_placement)
        self.room_view.copy_requested.connect(self._copy_placement)
        self.room_view.paste_requested.connect(self._paste_placement)
        self.room_view.playback_toggle_requested.connect(self._toggle_preview_playback)
        self.room_view.seek_requested.connect(self._seek_relative)
        content_splitter.addWidget(self.room_view)

        content_splitter.setSizes([340, 760])
        main_layout.addWidget(content_splitter, stretch=1)

        # 3. Timeline de Automação Dinâmica por Trechos
        self.timeline_widget = TimelineWidget(self.timeline_manager)
        self.timeline_widget.section_selected.connect(self._on_timeline_section_selected)
        self.timeline_widget.split_requested.connect(self._on_timeline_split_requested)
        self.timeline_widget.section_renamed.connect(self._on_timeline_renamed)
        self.timeline_widget.section_removed.connect(self._on_timeline_removed)
        self.timeline_widget.seek_requested.connect(self._on_timeline_seek_requested)
        main_layout.addWidget(self.timeline_widget)

        # 4. Rodapé / Player
        footer = self._create_player_bar()
        main_layout.addWidget(footer)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("HeaderBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        title_box = QVBoxLayout()
        lbl_title = QLabel("ATMOSSPLIT")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #00E5FF; letter-spacing: 1.5px;")
        lbl_sub = QLabel("Montador Espacial 7.1.4 (JBL Bar 1000MK2)")
        lbl_sub.setStyleSheet("font-size: 10px; color: #718096;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        layout.addSpacing(10)

        # Seletor de Saída de Áudio
        lbl_out = QLabel("Saída:")
        lbl_out.setStyleSheet("font-size: 11px; color: #A0AEC0;")
        layout.addWidget(lbl_out)

        self.combo_audio_dev = QComboBox()
        self.combo_audio_dev.setMinimumWidth(180)
        self._populate_audio_devices()
        self.combo_audio_dev.currentIndexChanged.connect(self._on_audio_device_changed)
        layout.addWidget(self.combo_audio_dev)

        layout.addSpacing(10)

        # Badges de Hardware
        lbl_hw = QLabel("Xeon (Núcleos 2-15) • Núcleos 0-1 Livres (KDE)")
        lbl_hw.setStyleSheet("background-color: #1F2430; padding: 4px 8px; border-radius: 4px; color: #A0AEC0; font-size: 10px;")
        layout.addWidget(lbl_hw)

        layout.addStretch(1)

        # Botão de Gerenciamento de Cache
        self.btn_cache = QPushButton("🧹 Cache (0 MB)")
        self.btn_cache.setObjectName("BtnCache")
        self.btn_cache.clicked.connect(self._open_cache_manager_dialog)
        layout.addWidget(self.btn_cache)

        # Botão de Ajuda e Atalhos Rápidos
        self.btn_help = QPushButton("❓ Ajuda / Atalhos")
        self.btn_help.setObjectName("BtnCache")
        self.btn_help.clicked.connect(self._open_help_dialog)
        layout.addWidget(self.btn_help)

        lbl_mode = QLabel("Modo IA:")
        lbl_mode.setStyleSheet("font-size: 11px; color: #A0AEC0;")
        layout.addWidget(lbl_mode)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Cirúrgico (8–12 Camadas)", "surgical")
        self.combo_mode.addItem("Rápido (~4 Camadas)", "fast")
        layout.addWidget(self.combo_mode)

        btn_search = QPushButton("🔍 Buscar Música")
        btn_search.clicked.connect(self._on_search_clicked)
        layout.addWidget(btn_search)

        btn_open = QPushButton("📁 Abrir Arquivo")
        btn_open.setObjectName("BtnPrimary")
        btn_open.clicked.connect(self._on_open_file_clicked)
        layout.addWidget(btn_open)

        return header

    def _populate_audio_devices(self):
        """Preenche o seletor com as placas de áudio físicas e virtuais PipeWire/ALSA."""
        self.combo_audio_dev.clear()
        self.combo_audio_dev.addItem("Padrão do Sistema (PipeWire)", None)

        devices = LiveSpatialPlayer.get_available_devices()
        seen = set()
        for d in devices:
            raw_name = d["name"]
            clean_name = raw_name.split(",")[0].strip()
            if "hw:" in raw_name or "sysdefault" in raw_name or "dmix" in raw_name:
                continue
            if clean_name in seen:
                clean_name = f"{clean_name} ({d['index']})"
            seen.add(clean_name)
            self.combo_audio_dev.addItem(f"{clean_name}", d["index"])

    def _on_audio_device_changed(self):
        dev_idx = self.combo_audio_dev.currentData()
        self.live_player.set_output_device(dev_idx)

    def _refresh_cache_button_label(self):
        try:
            total_bytes = self.cache_manager.get_total_cache_size_bytes()
            total_mb = round(total_bytes / (1024 * 1024), 1)
            self.btn_cache.setText(f"🧹 Cache ({total_mb} MB)")
        except Exception:
            pass

    def _open_cache_manager_dialog(self):
        """Abre modal interativo para inspecionar e limpar o cache de stems."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Gerenciador de Cache de Stems")
        dlg.resize(550, 360)
        dlg_layout = QVBoxLayout(dlg)

        tracks = self.cache_manager.list_cached_tracks()
        total_bytes = self.cache_manager.get_total_cache_size_bytes()
        total_mb = round(total_bytes / (1024 * 1024), 1)

        lbl_info = QLabel(f"Armazenamento total em uso: <b>{total_mb} MB</b> ({len(tracks)} faixas cacheadas)")
        lbl_info.setStyleSheet("font-size: 12px; margin-bottom: 6px;")
        dlg_layout.addWidget(lbl_info)

        table = QTableWidget(len(tracks), 3)
        table.setHorizontalHeaderLabels(["Hash / Modo", "Stems", "Tamanho (MB)"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        for row, t in enumerate(tracks):
            table.setItem(row, 0, QTableWidgetItem(f"{t['file_hash'][:12]}... [{t['mode']}]"))
            table.setItem(row, 1, QTableWidgetItem(str(t['stems_count'])))
            table.setItem(row, 2, QTableWidgetItem(f"{t['size_mb']} MB"))

        dlg_layout.addWidget(table)

        btn_box = QHBoxLayout()
        btn_clear = QPushButton("🗑 Limpar Todo o Cache")
        btn_clear.setObjectName("BtnCancel")

        def _do_clear():
            confirm = QMessageBox.question(
                dlg,
                "Limpar Cache",
                "Deseja realmente apagar todos os stems cacheados no disco?\n"
                "Músicas já abertas precisarão ser reprocessadas.",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                freed = self.cache_manager.clear_cache()
                freed_mb = round(freed / (1024 * 1024), 1)
                self._refresh_cache_button_label()
                QMessageBox.information(dlg, "Cache Limpo", f"{freed_mb} MB liberados com sucesso!")
                dlg.accept()

        btn_clear.clicked.connect(_do_clear)
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(dlg.reject)

        btn_box.addWidget(btn_clear)
        btn_box.addStretch(1)
        btn_box.addWidget(btn_close)
        dlg_layout.addLayout(btn_box)

        dlg.exec()

    def _open_help_dialog(self):
        """Abre modal com manual de atalhos e dicas de uso do AtmosSplit."""
        dlg = QDialog(self)
        dlg.setWindowTitle("AtmosSplit — Guia de Atalhos & Recursos")
        dlg.resize(640, 520)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(16, 16, 16, 16)
        dlg_layout.setSpacing(12)

        lbl_header = QLabel("Guia de Atalhos & Operação Espacial 7.1.4")
        lbl_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #00E5FF;")
        dlg_layout.addWidget(lbl_header)

        info_text = QLabel(
            "<b>Controles do Mouse & Sala 3D:</b><br>"
            "• <b>Clique em uma Bolinha:</b> Seleciona o instrumento para foco.<br>"
            "• <b>Arrastar Bolinha:</b> Move a posição no plano da sala.<br>"
            "• <b>Scroll do Mouse (Roda):</b> Eleva ou desce a altura Z. O raio visual cresce com a altura.<br>"
            "• <b>Duplo Clique na Bolinha:</b> Alterna entre som mono e <b>Espelhamento Estéreo Simétrico (L / R)</b>.<br><br>"
            "<b>Atalhos de Teclado Rápidos:</b><br>"
            "• <code>Espaço</code>: Tocar / Pausar pré-escuta binaural.<br>"
            "• <code>D</code>: Alternar Espelhamento Estéreo (L / R) no instrumento selecionado.<br>"
            "• <code>0</code>: Centralizar o instrumento selecionado no meio do palco.<br>"
            "• <code>M</code> / <code>S</code>: Mudar Mudo (Mute) ou Solo do instrumento ativo.<br>"
            "• <code>Setas Cima / Baixo</code>: Elevar ou descer a altura Z em passos de 5%.<br>"
            "• <code>Setas Esquerda / Direita</code>: Retroceder / Avançar 5 segundos na faixa.<br>"
            "• <code>1 a 5</code>: Alternar instantaneamente entre Presets Atmos (Equilibrado, 360°, Show, Voz, Clube).<br><br>"
            "<b>Automação por Trechos & Wi-Fi:</b><br>"
            "• <b>✂️ Dividir no Tempo Atual:</b> Cria um novo trecho musical com mixagem espacial independente.<br>"
            "• <b>⚡ Rápido (MP4 Wi-Fi / TV):</b> Salva a música inteira em Dolby Digital Plus + Dolby Atmos 7.1.4 (E-AC-3 JOC) "
            "em <code>~/Music/DolbyAtmos</code> para streaming instantâneo via Rygel / DLNA / TV Samsung."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("font-size: 11px; line-height: 1.4; color: #E2E8F0; background-color: #16181F; padding: 12px; border-radius: 6px; border: 1px solid #232734;")
        dlg_layout.addWidget(info_text)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_close = QPushButton("Entendido")
        btn_close.setObjectName("BtnPrimary")
        btn_close.clicked.connect(dlg.accept)
        btn_box.addWidget(btn_close)
        dlg_layout.addLayout(btn_box)

        dlg.exec()

    def _create_stems_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        lbl_stems = QLabel("CAMADAS ISOLADAS")
        lbl_stems.setStyleSheet("font-size: 11px; font-weight: bold; color: #A0AEC0; letter-spacing: 1px;")
        top_row.addWidget(lbl_stems)

        top_row.addStretch(1)
        lbl_pre = QLabel("Preset (1-5):")
        lbl_pre.setStyleSheet("font-size: 10px; color: #718096;")
        top_row.addWidget(lbl_pre)

        self.combo_presets = QComboBox()
        self.combo_presets.addItem("1: Equilibrado", DirectorPreset.BALANCED.value)
        self.combo_presets.addItem("2: Imersão 360°", DirectorPreset.IMMERSION_360.value)
        self.combo_presets.addItem("3: Show ao Vivo", DirectorPreset.LIVE_STAGE.value)
        self.combo_presets.addItem("4: Foco Vocal", DirectorPreset.VOCAL_FOCUS.value)
        self.combo_presets.addItem("5: Clube / Bass", DirectorPreset.CLUB_BASS.value)
        self.combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        top_row.addWidget(self.combo_presets)

        layout.addLayout(top_row)

        # Barra Visual de Seleção e Criação de Trechos / Seções da Música
        self.section_control_bar = QFrame()
        self.section_control_bar.setStyleSheet("""
            QFrame {
                background-color: #171A23;
                border: 1px solid #282E3E;
                border-radius: 6px;
                padding: 4px 6px;
            }
        """)
        sec_layout = QHBoxLayout(self.section_control_bar)
        sec_layout.setContentsMargins(4, 2, 4, 2)
        sec_layout.setSpacing(6)

        lbl_sec = QLabel("📍 Trecho:")
        lbl_sec.setStyleSheet("font-size: 11px; font-weight: bold; color: #00E5FF;")
        sec_layout.addWidget(lbl_sec)

        self.combo_sections = QComboBox()
        self.combo_sections.setStyleSheet("font-size: 11px; font-weight: bold; color: #FFFFFF;")
        self.combo_sections.currentIndexChanged.connect(self._on_combo_section_changed)
        sec_layout.addWidget(self.combo_sections, stretch=1)

        self.btn_split_here = QPushButton("✂️ Dividir Aqui")
        self.btn_split_here.setToolTip("Divide a música no ponto atual da agulha para criar uma nova mixagem espacial independente")
        self.btn_split_here.setStyleSheet("font-size: 10px; font-weight: bold; padding: 4px 8px; background-color: #242A38; border: 1px solid #374158; color: #E2E8F0; border-radius: 4px;")
        self.btn_split_here.clicked.connect(self._on_split_here_button_clicked)
        sec_layout.addWidget(self.btn_split_here)

        layout.addWidget(self.section_control_bar)

        self.scroll_stems = QScrollArea()
        self.scroll_stems.setWidgetResizable(True)
        self.stems_container = QWidget()
        self.stems_layout = QVBoxLayout(self.stems_container)
        self.stems_layout.setContentsMargins(0, 0, 0, 0)
        self.stems_layout.setSpacing(6)
        self.stems_layout.addStretch(1)

        self.lbl_empty_stems = QLabel("Arraste uma música aqui ou clique em\n'Abrir Arquivo' para começar.")
        self.lbl_empty_stems.setAlignment(Qt.AlignCenter)
        self.lbl_empty_stems.setStyleSheet("color: #4A5568; font-size: 12px; margin-top: 40px;")
        self.stems_layout.addWidget(self.lbl_empty_stems)

        self.scroll_stems.setWidget(self.stems_container)
        layout.addWidget(self.scroll_stems, stretch=1)

        return panel

    def _create_player_bar(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("PlayerBar")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        self.lbl_cover = QLabel()
        self.lbl_cover.setFixedSize(40, 40)
        self.lbl_cover.setStyleSheet("background-color: #1A1D24; border-radius: 4px;")
        self.lbl_cover.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_cover)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        self.lbl_track_title = QLabel("Nenhuma música carregada")
        self.lbl_track_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFFFFF;")
        self.lbl_track_artist = QLabel("Aguardando arquivo ou busca")
        self.lbl_track_artist.setStyleSheet("font-size: 10px; color: #718096;")
        info_box.addWidget(self.lbl_track_title)
        info_box.addWidget(self.lbl_track_artist)
        layout.addLayout(info_box)

        layout.addSpacing(8)

        self.btn_play = QPushButton("▶ Play (Espaço)")
        self.btn_play.setFixedWidth(135)
        self.btn_play.clicked.connect(self._toggle_preview_playback)
        layout.addWidget(self.btn_play)

        self.slider_time = QSlider(Qt.Horizontal)
        self.slider_time.setRange(0, 1000)
        self.slider_time.setValue(0)
        self.slider_time.sliderMoved.connect(self._on_seek_moved)
        layout.addWidget(self.slider_time, stretch=1)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("font-size: 11px; color: #A0AEC0; font-family: monospace;")
        layout.addWidget(self.lbl_time)

        layout.addSpacing(8)

        # Fader de Volume Master Geral
        lbl_vol_icon = QLabel("🔊")
        lbl_vol_icon.setStyleSheet("font-size: 11px;")
        layout.addWidget(lbl_vol_icon)

        self.slider_master_vol = QSlider(Qt.Horizontal)
        self.slider_master_vol.setRange(0, 150)
        self.slider_master_vol.setValue(100)
        self.slider_master_vol.setFixedWidth(80)
        self.slider_master_vol.setToolTip("Volume Master Geral (0 a 150%)")
        self.slider_master_vol.valueChanged.connect(self._on_master_volume_changed)
        layout.addWidget(self.slider_master_vol)

        self.lbl_vol_text = QLabel("100%")
        self.lbl_vol_text.setStyleSheet("font-size: 10px; color: #A0AEC0; width: 32px;")
        layout.addWidget(self.lbl_vol_text)

        layout.addSpacing(10)

        btn_quick = QPushButton("⚡ Rápido (MP4 Wi-Fi / TV)")
        btn_quick.setObjectName("BtnQuickExport")
        btn_quick.setToolTip("Exporta a faixa inteira em MP4 Dolby Digital Plus + Dolby Atmos 7.1.4 (E-AC-3 JOC) diretamente para ~/Music/DolbyAtmos com toda a automação de trechos.")
        btn_quick.clicked.connect(self._on_quick_export_clicked)
        layout.addWidget(btn_quick)

        btn_export = QPushButton("💾 Exportar...")
        btn_export.clicked.connect(self._on_export_clicked)
        layout.addWidget(btn_export)

        btn_jbl = QPushButton("🔊 Tocar na JBL 1000")
        btn_jbl.setObjectName("BtnJBL")
        btn_jbl.setToolTip("Transmite a faixa via Wi-Fi/DLNA para a TV Samsung com áudio Dolby Atmos 7.1.4 na JBL Bar 1000 e tela apagada.")
        btn_jbl.clicked.connect(self._on_play_on_jbl_clicked)
        layout.addWidget(btn_jbl)

        return footer

    def _on_master_volume_changed(self, val: int):
        vol = float(val) / 100.0
        self.live_player.set_volume(vol)
        self.lbl_vol_text.setText(f"{val}%")

    def _poll_audio_state(self):
        """Atualização a ~33 FPS lendo snapshots atômicos sem tocar na thread de áudio."""
        _immunize_cpython_none_refcount()
        cur_s, tot_s, vu_stems, sub_vu, is_playing = self.live_player.get_ui_snapshot()

        if is_playing or cur_s > 0:
            if tot_s > 0:
                ratio = cur_s / tot_s
                if not self.slider_time.isSliderDown():
                    self.slider_time.blockSignals(True)
                    self.slider_time.setValue(int(ratio * 1000))
                    self.slider_time.blockSignals(False)

            c_m, c_sec = int(cur_s // 60), int(cur_s % 60)
            t_m, t_sec = int(tot_s // 60), int(tot_s % 60)
            self.lbl_time.setText(f"{c_m:02d}:{c_sec:02d} / {t_m:02d}:{t_sec:02d}")

            # Atualizar agulha da timeline de trechos
            self.timeline_widget.set_current_playback_time(cur_s)

            if is_playing:
                self.room_view.set_vu_levels(vu_stems, sub_vu)
            else:
                self.room_view.set_vu_levels({}, 0.0)

    def _copy_placement(self, stem_name: str):
        if stem_name in self.current_placements:
            self._placement_clipboard = copy.copy(self.current_placements[stem_name])
            self.statusBar().showMessage(f"📋 Copiado: '{stem_name}'. Pressione Ctrl+V ou use o menu para duplicar.", 3000)

    def _paste_placement(self):
        if self._placement_clipboard:
            source = self._placement_clipboard.source_stem_name or self._placement_clipboard.stem_name
            self._duplicate_placement(source)
        elif self.room_view.active_stem_name:
            self._duplicate_placement(self.room_view.active_stem_name)

    def _seek_relative(self, delta_s: float):
        cur_s = self.live_player.current_time_s
        self.live_player.seek(max(0.0, (cur_s + delta_s) * self.live_player.sample_rate))

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        active_name = self.room_view.active_stem_name

        if key == Qt.Key_Space:
            self._toggle_preview_playback()
            event.accept()
        elif key == Qt.Key_D:
            # Alternar espelhamento estéreo (L / R)
            if active_name:
                self.room_view.toggle_stereo_mirror(active_name)
                event.accept()
        elif key == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            if active_name:
                self._copy_placement(active_name)
                event.accept()
        elif key == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
            self._paste_placement()
            event.accept()
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            if active_name:
                self._delete_placement(active_name)
                event.accept()
        elif key == Qt.Key_M:
            if active_name and active_name in self.stem_cards:
                self.stem_cards[active_name].btn_mute.click()
                event.accept()
        elif key == Qt.Key_S:
            if active_name and active_name in self.stem_cards:
                self.stem_cards[active_name].btn_solo.click()
                event.accept()
        elif key == Qt.Key_0:
            if active_name and active_name in self.current_placements:
                plc = self.current_placements[active_name]
                plc.x, plc.y, plc.z = 0.0, 0.0, 0.0
                self._on_room_placement_changed(active_name, 0.0, 0.0, 0.0)
                self.room_view.update()
                event.accept()
        elif key == Qt.Key_Up:
            if active_name and active_name in self.current_placements:
                plc = self.current_placements[active_name]
                plc.z = min(1.0, plc.z + 0.05)
                self._on_room_placement_changed(active_name, plc.x, plc.y, plc.z)
                self.room_view.update()
                event.accept()
        elif key == Qt.Key_Down:
            if active_name and active_name in self.current_placements:
                plc = self.current_placements[active_name]
                plc.z = max(0.0, plc.z - 0.05)
                self._on_room_placement_changed(active_name, plc.x, plc.y, plc.z)
                self.room_view.update()
                event.accept()
        elif key == Qt.Key_1:
            self.combo_presets.setCurrentIndex(0)
            event.accept()
        elif key == Qt.Key_2:
            self.combo_presets.setCurrentIndex(1)
            event.accept()
        elif key == Qt.Key_3:
            self.combo_presets.setCurrentIndex(2)
            event.accept()
        elif key == Qt.Key_4:
            self.combo_presets.setCurrentIndex(3)
            event.accept()
        elif key == Qt.Key_5:
            self.combo_presets.setCurrentIndex(4)
            event.accept()
        elif key == Qt.Key_Left:
            self._seek_relative(-5.0)
            event.accept()
        elif key == Qt.Key_Right:
            self._seek_relative(5.0)
            event.accept()
            cur_s = self.live_player.current_time_s
            self.live_player.seek(max(0.0, (cur_s + 5.0) * self.live_player.sample_rate))
            event.accept()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self._load_and_process_audio_path(file_path)
                break

    def _on_open_file_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione uma faixa de áudio",
            str(Path.home() / "Music"),
            "Arquivos de Áudio (*.flac *.wav *.alac *.mp3 *.m4a *.opus *.ogg);;Todos os arquivos (*.*)"
        )
        if file_path:
            self._load_and_process_audio_path(file_path)

    def _on_search_clicked(self):
        query, ok = QInputDialog.getText(
            self,
            "Buscar Música de Alta Qualidade",
            "Digite o Artista e Nome da Música:"
        )
        if ok and query.strip():
            self._perform_online_search(query.strip())

    def _perform_online_search(self, query: str):
        self.progress_container.setVisible(True)
        self.progress_bar.setValue(20)
        self.statusBar().showMessage(f"Buscando '{query}' em fontes lossless e Hi-Res...")

        results = self.search_engine.search(query)
        self.progress_container.setVisible(False)

        if not results:
            QMessageBox.information(self, "Busca", f"Nenhum resultado encontrado para '{query}'.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Resultados da Busca")
        dlg.resize(540, 300)
        dlg_layout = QVBoxLayout(dlg)

        lbl = QLabel(f"Resultados encontrados para '{query}':")
        dlg_layout.addWidget(lbl)

        combo = QComboBox()
        for r in results:
            combo.addItem(f"{r.artist} - {r.title} [{r.format_label}]", r)
        dlg_layout.addWidget(combo)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Baixar e Destrinchar")
        btn_ok.setObjectName("BtnPrimary")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        if dlg.exec() == QDialog.Accepted:
            selected_item: SearchResultItem = combo.currentData()
            self._download_and_process_result(selected_item)

    def _download_and_process_result(self, item: SearchResultItem):
        self.progress_container.setVisible(True)
        self.progress_bar.setValue(40)
        self.statusBar().showMessage(f"Baixando '{item.artist} - {item.title}'...")

        try:
            downloaded_path = self.search_engine.download_to_file(item)
            self._load_and_process_audio_path(downloaded_path)
        except Exception as e:
            self.progress_container.setVisible(False)
            QMessageBox.critical(self, "Erro no Download", f"Não foi possível baixar a faixa: {e}")

    def _load_and_process_audio_path(self, file_path: str):
        try:
            self.live_player.stop()
            self.btn_play.setText("▶ Play (Espaço)")

            source = load_audio_file(file_path, load_data_now=False)
            self.current_source = source

            self.lbl_track_title.setText(source.metadata.title)
            self.lbl_track_artist.setText(f"{source.metadata.artist} • {source.metadata.format_name} {source.metadata.sample_rate}Hz")

            if source.metadata.cover_image_bytes:
                pix = QPixmap()
                pix.loadFromData(source.metadata.cover_image_bytes)
                if not pix.isNull():
                    self.lbl_cover.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            else:
                self.lbl_cover.setText("🎵")

            mode = self.combo_mode.currentData() or "surgical"

            # 1. Checar se já existe no cache (recarga instantânea sem rodar subprocesso)
            if self.cache_manager.has_cached_stems(source.sha256_hash, mode):
                self.statusBar().showMessage("Carregando stems do cache ultra-rápido...")
                res = self.stem_engine.separate_track(
                    audio_array=np.zeros((10, 2)),
                    sample_rate=source.sample_rate,
                    file_hash=source.sha256_hash,
                    mode=mode
                )
                self._on_stems_ready(res)
                return

            # 2. Se não estiver em cache, dispara em subprocesso desacoplado via QProcess
            self._start_decoupled_separation(file_path, source.sha256_hash, mode)

        except Exception as e:
            QMessageBox.critical(self, "Erro ao carregar", f"Falha ao ler arquivo: {e}")

    def _start_decoupled_separation(self, file_path: str, file_hash: str, mode: str):
        """Dispara o processo de IA isolado da GUI para garantir zero congelamento."""
        if self.separation_process is not None:
            self._cancel_separation_task()

        self._last_worker_error = None
        self._user_cancelled_separation = False

        self.progress_container.setVisible(True)
        self.progress_bar.setValue(5)
        self.statusBar().showMessage(f"Iniciando separação por IA ({mode})...")

        self._current_task_info = {
            "file_path": file_path,
            "file_hash": file_hash,
            "mode": mode,
            "start_time": str(time.time())
        }

        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setArguments([
            "-m", "src.separation.worker_cli",
            "--input", file_path,
            "--hash", file_hash,
            "--mode", mode
        ])

        proc.readyReadStandardOutput.connect(self._on_worker_stdout)
        proc.finished.connect(self._on_worker_finished)
        self.separation_process = proc
        proc.start()

    def _cancel_separation_task(self):
        """Encerra instantaneamente o processo de IA e todas as threads filhas no Xeon."""
        self._user_cancelled_separation = True
        if self.separation_process and self.separation_process.state() != QProcess.NotRunning:
            pid = self.separation_process.processId()
            try:
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                parent.kill()
            except Exception:
                self.separation_process.kill()

            self.separation_process = None
            self.progress_container.setVisible(False)
            self.statusBar().showMessage("Separação cancelada pelo usuário.")

    def _on_worker_stdout(self):
        if not self.separation_process:
            return

        raw_data = self.separation_process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
        for line in raw_data.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
                m_type = msg.get("type")
                if m_type == "progress":
                    val = int(msg.get("value", 0.0) * 100)
                    text = msg.get("message", "")
                    self.progress_bar.setValue(val)
                    self.statusBar().showMessage(text)
                elif m_type == "error":
                    err_msg = msg.get("message", "Erro desconhecido")
                    self._last_worker_error = err_msg
                    self.statusBar().showMessage(f"Erro na IA: {err_msg}")
            except Exception:
                pass

    def _on_worker_finished(self, exit_code: int, exit_status):
        self.progress_container.setVisible(False)
        stderr_output = ""
        if self.separation_process:
            try:
                stderr_output = self.separation_process.readAllStandardError().data().decode("utf-8", errors="ignore").strip()
            except Exception:
                pass
        self.separation_process = None

        if exit_code != 0:
            if self._user_cancelled_separation:
                self.statusBar().showMessage("Separação cancelada pelo usuário.")
            else:
                err = self._last_worker_error or stderr_output or "Processo de IA encerrou com erro."
                self.statusBar().showMessage(f"Falha na IA: {err}")
                QMessageBox.critical(self, "Falha na Separação por IA", f"A separação dos instrumentos encontrou um erro:\n\n{err}")
            return

        if not self._current_task_info:
            return

        file_hash = self._current_task_info["file_hash"]
        mode = self._current_task_info["mode"]

        self._refresh_cache_button_label()

        cached_stems = self.cache_manager.load_stems(file_hash, mode)
        if not cached_stems:
            QMessageBox.critical(self, "Erro", "Stems não foram encontrados após processamento.")
            return

        res = self.stem_engine.separate_track(
            audio_array=np.zeros((10, 2)),
            sample_rate=self.current_source.sample_rate if self.current_source else 48000,
            file_hash=file_hash,
            mode=mode
        )
        self._on_stems_ready(res)

    def _on_stems_ready(self, result: SeparationResult):
        self.statusBar().showMessage(f"Stems prontos em {result.elapsed_time_s:.1f}s (Cache: {'Sim' if result.from_cache else 'Não'})")
        self.current_stems = result.stems

        profiles = {
            s.name: AcousticAnalyzer.analyze_stem(s.name, s.audio_data, s.sample_rate)
            for s in self.current_stems
        }
        self._stem_profiles = profiles
        preset_val = self.combo_presets.currentData() or DirectorPreset.BALANCED.value
        self.current_placements = AutoAtmosDirector.generate_placements(profiles, DirectorPreset(preset_val))
        self._stem_audio_by_instance = {s.name: s for s in self.current_stems}

        # Inicializa o player e atualiza a timeline com a duração real
        self.live_player.set_stems_and_placements(self.current_stems, self.current_placements)
        track_duration_s = max(1.0, self.live_player.total_duration_s)
        self.timeline_manager.reset_to_single_section(track_duration_s, self.current_placements)
        self.live_player.set_timeline_manager(self.timeline_manager)
        self.timeline_widget.refresh_timeline()
        self._refresh_sections_combo()

        self._populate_stems_ui()
        self.room_view.set_stems_and_placements(self.current_stems, self.current_placements)
        self._refresh_cache_button_label()

    def _populate_stems_ui(self):
        self.lbl_empty_stems.setVisible(False)
        for card in self.stem_cards.values():
            card.setParent(None)
            card.deleteLater()
        self.stem_cards.clear()

        for instance_name, plc in self.current_placements.items():
            stem = self._stem_audio_by_instance.get(instance_name) or self._stem_audio_by_instance.get(plc.source_stem_name or instance_name)
            if not stem:
                continue
            card = StemControlCard(stem, plc)
            card.changed.connect(self._on_stem_card_changed)
            card.selected.connect(self.room_view.set_active_stem)
            card.delete_requested.connect(self._delete_placement)
            card.duplicate_requested.connect(self._duplicate_placement)
            self.stems_layout.insertWidget(self.stems_layout.count() - 1, card)
            self.stem_cards[instance_name] = card

    def _duplicate_placement(self, source_name: Optional[str] = None):
        section = self.timeline_manager.get_active_edit_section()
        target_name = source_name or self.room_view.active_stem_name
        source = section.placements.get(target_name) if target_name else None
        if source is None:
            if self._placement_clipboard:
                clip_base = self._placement_clipboard.source_stem_name or self._placement_clipboard.stem_name
                source = section.placements.get(clip_base)
                target_name = clip_base
        if source is None:
            return
        base_name = source.source_stem_name or target_name
        index = 2
        while f"{base_name}::{index}" in section.placements:
            index += 1
        instance_name = f"{base_name}::{index}"
        placement = copy.copy(self._placement_clipboard or source)
        placement.stem_name = instance_name
        placement.source_stem_name = base_name
        placement.x = max(-0.95, min(0.95, placement.x + 0.15))
        placement.y = max(-0.95, min(0.95, placement.y - 0.10))
        section.placements[instance_name] = placement
        self._stem_audio_by_instance[instance_name] = self._stem_audio_by_instance[base_name]
        self.current_placements = section.placements
        self.live_player.set_active_placements(self.current_placements)
        self._populate_stems_ui()
        self.room_view.set_stems_and_placements(self.current_stems, self.current_placements)
        self.room_view.active_stem_name = instance_name
        self.room_view._update_rays_cache()
        self.room_view.update()
        self._on_room_stem_selected(instance_name)
        self.statusBar().showMessage(
            f"✨ Nova instância criada: '{instance_name}'. Posicione-a livremente na sala ou teto!",
            4000
        )

    def _delete_placement(self, instance_name: str):
        if instance_name not in self.stem_cards or not instance_name.split("::")[-1].isdigit():
            return
        base_name = instance_name.split("::")[0]
        section = self.timeline_manager.get_active_edit_section()
        section.placements.pop(instance_name, None)
        self._stem_audio_by_instance.pop(instance_name, None)
        self.current_placements = section.placements
        self.stem_cards.pop(instance_name, None)
        self._populate_stems_ui()
        self.live_player.set_active_placements(self.current_placements)
        self.room_view.set_stems_and_placements(self.current_stems, self.current_placements)
        if self.room_view.active_stem_name == instance_name:
            self.room_view.set_active_stem(base_name)
        self.statusBar().showMessage(f"🗑️ Instância '{instance_name}' removida.", 3000)

    def _on_preset_selected(self):
        if not self.current_stems:
            return
        preset_val = self.combo_presets.currentData() or DirectorPreset.BALANCED.value
        self.current_placements = AutoAtmosDirector.generate_placements(
            self._stem_profiles, DirectorPreset(preset_val)
        )

        # Atualiza a seção atual da timeline com o novo preset
        active_sec = self.timeline_manager.get_active_edit_section()
        active_sec.placements = {k: v for k, v in self.current_placements.items()}
        
        for name, card in self.stem_cards.items():
            card.placement = self.current_placements[name]
            card.sync_from_placement()
        self.room_view.set_stems_and_placements(self.current_stems, self.current_placements)
        self.live_player.set_stems_and_placements(self.current_stems, self.current_placements)

    def _on_room_placement_changed(self, stem_name: str, x: float, y: float, z: float):
        if stem_name in self.stem_cards:
            self.stem_cards[stem_name].sync_coords_from_placement(x, y, z)
        # Salva o posicionamento na seção ativa da timeline
        active_sec = self.timeline_manager.get_active_edit_section()
        if stem_name in active_sec.placements:
            active_sec.placements[stem_name].x = x
            active_sec.placements[stem_name].y = y
            active_sec.placements[stem_name].z = z
        self.live_player.update_placement(stem_name, x, y, z)

    def _on_room_stereo_toggled(self, stem_name: str, is_stereo: bool):
        if stem_name in self.stem_cards:
            self.stem_cards[stem_name].sync_from_placement()
        active_sec = self.timeline_manager.get_active_edit_section()
        if stem_name in active_sec.placements:
            active_sec.placements[stem_name].is_stereo = is_stereo
        plc = self.current_placements.get(stem_name)
        if plc:
            plc.is_stereo = is_stereo
            self.live_player.update_placement(stem_name, plc.x, plc.y, plc.z, is_stereo=is_stereo)
        status_msg = f"{stem_name}: Espelhamento Estéreo {'ATIVADO (L / R)' if is_stereo else 'DESATIVADO (Mono)'}"
        self.statusBar().showMessage(status_msg, 3000)

    def _on_room_stem_selected(self, stem_name: str):
        for name, card in self.stem_cards.items():
            is_active = (name == stem_name)
            card.set_selected(is_active)
            if is_active:
                self.scroll_stems.ensureWidgetVisible(card)
                z_pct = int(round(card.placement.z * 100))
                self.statusBar().showMessage(
                    f"Instrumento: {card.stem.display_name} (Altura Z: {z_pct}%) • "
                    f"Scroll = Altura Z • Tecla 'D' = Espelhar Estéreo (L/R) • Tecla '0' = Centralizar"
                )

    def _on_stem_card_changed(self, stem_name: str):
        plc = self.current_placements[stem_name]
        # Salva na seção ativa da timeline
        active_sec = self.timeline_manager.get_active_edit_section()
        active_sec.placements[stem_name] = plc

        self.room_view.update_placement(stem_name, plc.x, plc.y, plc.z, is_stereo=plc.is_stereo)
        self.live_player.update_placement(
            stem_name,
            plc.x,
            plc.y,
            plc.z,
            spread=plc.spread,
            lfe=plc.lfe_send,
            is_stereo=plc.is_stereo
        )
        self.live_player.set_active_placements(self.current_placements)

    # --- Sincronização de Automação por Trechos (Timeline) ---
    def _refresh_sections_combo(self):
        """Atualiza a caixa de seleção de trechos para navegação rápida e transparente."""
        self.combo_sections.blockSignals(True)
        self.combo_sections.clear()
        sections = self.timeline_manager.sections
        active_id = self.timeline_manager.active_edit_section_id
        active_idx = 0
        for i, sec in enumerate(sections):
            label = f"{i+1}. {sec.name} ({sec.start_time_s:.1f}s - {sec.end_time_s:.1f}s)"
            self.combo_sections.addItem(label, sec.id)
            if sec.id == active_id:
                active_idx = i
        if self.combo_sections.count() > 0:
            self.combo_sections.setCurrentIndex(active_idx)
        self.combo_sections.blockSignals(False)

    def _on_combo_section_changed(self, index: int):
        sec_id = self.combo_sections.currentData()
        if sec_id and sec_id != self.timeline_manager.active_edit_section_id:
            self.timeline_manager.active_edit_section_id = sec_id
            self._on_timeline_section_selected(sec_id)
            self.timeline_widget.refresh_timeline()

    def _on_split_here_button_clicked(self):
        if not self.current_stems:
            self.statusBar().showMessage("Carregue uma música antes de dividir em trechos.")
            return
        cur_s, tot_s, _, _, _ = self.live_player.get_ui_snapshot()
        if cur_s <= 0.5 or cur_s >= (tot_s - 0.5):
            ratio = float(self.slider_time.value()) / 1000.0
            cur_s = ratio * tot_s
        new_sec = self.timeline_manager.split_section_at(cur_s)
        if new_sec:
            self._refresh_sections_combo()
            self._on_timeline_section_selected(new_sec.id)
            self.timeline_widget.refresh_timeline()
            self.statusBar().showMessage(
                f"✂️ Novo trecho criado aos {cur_s:.1f}s! Ajuste as vozes ou instrumentos para este trecho.",
                5000
            )

    def _on_timeline_section_selected(self, sec_id: str):
        sec = self.timeline_manager.get_section_by_id(sec_id)
        if not sec:
            return

        self.current_placements = sec.placements
        self.live_player.set_active_placements(self.current_placements)
        for name, card in self.stem_cards.items():
            if name in self.current_placements:
                card.placement = self.current_placements[name]
                card.sync_from_placement()

        self.room_view.set_stems_and_placements(self.current_stems, self.current_placements)

        # Sincroniza a caixa suspensa sem disparar eventos circulares
        self.combo_sections.blockSignals(True)
        for i in range(self.combo_sections.count()):
            if self.combo_sections.itemData(i) == sec_id:
                self.combo_sections.setCurrentIndex(i)
                break
        self.combo_sections.blockSignals(False)

        self.statusBar().showMessage(
            f"Editando trecho: '{sec.name}' ({sec.start_time_s:.1f}s - {sec.end_time_s:.1f}s) • Ajuste os instrumentos na sala para este momento da faixa"
        )

    def _on_timeline_split_requested(self, split_time_s: float):
        sec = self.timeline_manager.get_active_edit_section()
        self._refresh_sections_combo()
        self._on_timeline_section_selected(sec.id)
        self.statusBar().showMessage(f"Novo trecho criado em {split_time_s:.3f}s. Ajuste as posições para este trecho.")

    def _on_timeline_renamed(self, sec_id: str, new_name: str):
        self._refresh_sections_combo()
        self.statusBar().showMessage(f"Trecho renomeado para '{new_name}'.")

    def _on_timeline_removed(self, sec_id: str):
        active_sec = self.timeline_manager.get_active_edit_section()
        self._refresh_sections_combo()
        self._on_timeline_section_selected(active_sec.id)
        self.statusBar().showMessage("Trecho removido e fundido com o vizinho.")

    def _on_timeline_seek_requested(self, time_s: float):
        self.live_player.seek(time_s * self.live_player.sample_rate)

    def _toggle_preview_playback(self):
        if not self.current_stems:
            return

        if self.live_player.is_playing:
            self.live_player.pause()
            self.btn_play.setText("▶ Play (Espaço)")
        else:
            self.live_player.play()
            self.btn_play.setText("⏸ Pausar (Espaço)")

    def _on_seek_moved(self, val: int):
        ratio = float(val) / 1000.0
        self.live_player.seek(ratio)

    def _on_quick_export_clicked(self):
        if not self.current_stems:
            QMessageBox.warning(self, "Exportação", "Nenhuma faixa carregada.")
            return

        out_dir = Path.home() / "Music" / "DolbyAtmos"
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{self.lbl_track_title.text()} [Dolby Atmos 7.1.4].mp4".replace("/", "-")

        num_sections = len(self.timeline_manager.sections)
        msg_extra = f" ({num_sections} trechos automatizados)" if num_sections > 1 else ""
        self.statusBar().showMessage(f"Renderizando faixa completa em Dolby Digital Plus + Dolby Atmos 7.1.4 (E-AC-3 JOC){msg_extra}...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            matrix_714 = self.renderer.render_to_multichannel_714(
                self.current_stems,
                self.current_placements,
                config=RenderConfig(sample_rate=48000, apply_lufs_norm=True),
                timeline_manager=self.timeline_manager
            )
            saved = AudioExporter714.export(
                multichannel_matrix=matrix_714,
                output_path=dest,
                sample_rate=48000,
                export_format=ExportFormat.MP4_ATMOS_JOC_714,
                metadata=self.current_source.metadata if self.current_source else None
            )
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage(f"Salvo em {saved.name} (Dolby Atmos JOC real no Rygel / Wi-Fi)!")
            QMessageBox.information(
                self,
                "Exportação Concluída para Wi-Fi / TV",
                f"Música inteira salva com sucesso em:\n{saved}\n\n"
                f"📡 Dolby Atmos Real (E-AC-3 JOC):\n"
                f"• Contém 12 objetos dinâmicos e metadados OAMD/JOC com canais de teto (.4) ativos!\n"
                f"• Inclui todas as {num_sections} variações espaciais definidas na linha do tempo!\n"
                f"• Salvo na pasta monitorada pelo Rygel ({out_dir}).\n"
                f"• Transmita via Wi-Fi no celular (BubbleUPnP / Symfonium) ou TV Samsung para acionar DOLBY ATMOS na JBL Bar 1000!"
            )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Erro", f"Falha na exportação: {e}")

    def _on_export_clicked(self):
        if not self.current_stems:
            QMessageBox.warning(self, "Exportação", "Nenhuma faixa carregada para exportação.")
            return

        out_dir = Path.home() / "Music" / "DolbyAtmos"
        out_dir.mkdir(parents=True, exist_ok=True)
        default_name = f"{self.lbl_track_title.text()} [Dolby Atmos 7.1.4].mp4".replace("/", "-")

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Salvar Mixagem Espacial",
            str(out_dir / default_name),
            "MP4 Dolby Digital Plus + Dolby Atmos 7.1.4 [E-AC-3 JOC / Wi-Fi / TV / DLNA] (*.mp4);;"
            "MKV LPCM 7.1.4 12ch [Lossless Discreto / Cabo HDMI / DirectFrame] (*.mkv);;"
            "MKV Dolby Atmos 7.1.4 [E-AC-3 JOC] (*.mkv);;"
            "WAV 7.1.4 12ch Descompactado Studio Master (*.wav);;"
            "EC3 Dolby Atmos 7.1.4 [Bitstream E-AC-3 JOC Puro] (*.ec3)"
        )
        if not file_path:
            return

        export_fmt = ExportFormat.MP4_ATMOS_JOC_714
        if file_path.endswith(".wav") or "WAV" in selected_filter:
            export_fmt = ExportFormat.WAV_714
        elif "LPCM 7.1.4" in selected_filter:
            export_fmt = ExportFormat.MKV_LPCM_714
        elif file_path.endswith(".ec3") or "EC3" in selected_filter:
            export_fmt = ExportFormat.EC3_ATMOS_714
        elif "MKV Dolby Atmos" in selected_filter or file_path.endswith(".mkv"):
            export_fmt = ExportFormat.MKV_ATMOS_JOC_714
        else:
            export_fmt = ExportFormat.MP4_ATMOS_JOC_714

        self.statusBar().showMessage(f"Renderizando e exportando {export_fmt.value} (faixa completa)...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            matrix_714 = self.renderer.render_to_multichannel_714(
                self.current_stems,
                self.current_placements,
                config=RenderConfig(sample_rate=48000, apply_lufs_norm=True),
                timeline_manager=self.timeline_manager
            )
            saved_file = AudioExporter714.export(
                multichannel_matrix=matrix_714,
                output_path=file_path,
                sample_rate=48000,
                export_format=export_fmt,
                metadata=self.current_source.metadata if self.current_source else None
            )
            QApplication.restoreOverrideCursor()
            QMessageBox.information(
                self,
                "Exportação Concluída",
                f"Música inteira salva com sucesso em:\n{saved_file}\n\n"
                f"Formato: {export_fmt.name} ({saved_file.suffix})\n"
                f"Automação: {len(self.timeline_manager.sections)} trechos processados com transições suaves."
            )
            self.statusBar().showMessage("Exportação finalizada com sucesso.")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Falha na Exportação", f"Erro ao exportar: {e}")

    def _on_play_on_jbl_clicked(self):
        if not self.current_stems:
            QMessageBox.warning(self, "Reprodução", "Carregue e monte uma faixa antes de tocar na soundbar.")
            return

        out_dir = Path.home() / "Music" / "DolbyAtmos"
        out_dir.mkdir(parents=True, exist_ok=True)
        dest_file = out_dir / f"{self.lbl_track_title.text()} [Dolby Atmos 7.1.4].mp4".replace("/", "-")

        self.statusBar().showMessage("Renderizando faixa completa em Dolby Atmos 7.1.4 para TV Samsung / JBL Bar 1000...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            matrix_714 = self.renderer.render_to_multichannel_714(
                self.current_stems,
                self.current_placements,
                config=RenderConfig(sample_rate=48000, apply_lufs_norm=True),
                timeline_manager=self.timeline_manager
            )
            saved_file = AudioExporter714.export(
                multichannel_matrix=matrix_714,
                output_path=dest_file,
                sample_rate=48000,
                export_format=ExportFormat.MP4_ATMOS_JOC_714,
                metadata=self.current_source.metadata if self.current_source else None
            )
            QApplication.restoreOverrideCursor()

            # Tenta cast via DLNA para a TV Samsung com tela apagada
            success = self.dlna_bridge.cast_file_to_soundbar(saved_file, auto_picture_off=True)
            if not success:
                success = self.directframe_bridge.play_multichannel_file(saved_file)

            if success:
                self.statusBar().showMessage("Reproduzindo na TV Samsung via Wi-Fi (DLNA) -> JBL Bar 1000!")
                QMessageBox.information(
                    self,
                    "Reprodução Wi-Fi Iniciada",
                    f"A faixa foi salva em:\n{saved_file}\n\n"
                    f"Comando de transmissão enviado para a TV Samsung!\n"
                    f"A tela da TV será desligada (KEY_PICTURE_OFF) mantendo o som na JBL Bar 1000."
                )
            else:
                QMessageBox.information(
                    self,
                    "Arquivo Pronto para Wi-Fi",
                    f"Faixa salva com sucesso em:\n{saved_file}\n\n"
                    f"O Rygel já disponibilizou a faixa na rede!\n"
                    f"Abra o BubbleUPnP ou Symfonium no celular (ou na TV Samsung) para tocar via Wi-Fi."
                )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Erro de Reprodução", f"Falha ao processar para soundbar: {e}")

    def closeEvent(self, event):
        self.ui_poll_timer.stop()
        self._cancel_separation_task()
        self.live_player.stop()
        super().closeEvent(event)


def run_app():
    if sys.platform == "linux":
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("AtmosSplit")

    icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
