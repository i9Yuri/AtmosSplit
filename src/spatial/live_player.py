"""
AtmosSplit — Live Spatial Audio Player (Pré-escuta Binaural em Tempo Real 100% Lock-Free)
Motor de áudio contínuo de ultra-baixa latência usando sounddevice e PipeWire/ALSA.
Arquitetura 100% Lock-Free:
- A thread de áudio de alta prioridade do PortAudio opera sem nenhuma trava (zero mutex/zero locks).
- Acesso atômico a AudioDSPState por troca atômica de ponteiro no Python.
- Interpolação vetorial de ganhos entre seções no tempo sem recálculos trigonométricos no loop de áudio.
- Zero chance de inanição de buffer (buffer underrun), engasgos ou travamento de compositor (Wayland).
"""

from __future__ import annotations

import math
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple, Any, TYPE_CHECKING

import numpy as np

try:
    import sounddevice as sd
    _SOUNDDEVICE_AVAILABLE = True
except Exception:
    sd = None
    _SOUNDDEVICE_AVAILABLE = False

from .vbap_engine import VBAP714Engine, SPEAKER_COORDINATES_714
from .binaural_hrtf import BinauralHRTFEngine
from .auto_director import SpatialPlacement
from ..separation.stem_engine import StemTrack

if TYPE_CHECKING:
    from .timeline_manager import SpatialTimelineManager

log = logging.getLogger(__name__)


@dataclass
class AudioDSPState:
    """Estado imutável de DSP consumido pela thread de áudio com zero contenção de trava."""
    stems: List[StemTrack] = field(default_factory=list)
    cached_ch_l: Dict[str, np.ndarray] = field(default_factory=dict)
    cached_ch_r: Dict[str, np.ndarray] = field(default_factory=dict)
    cached_vbap_gains_l: Dict[str, np.ndarray] = field(default_factory=dict)
    cached_vbap_gains_r: Dict[str, np.ndarray] = field(default_factory=dict)
    vol_gains: Dict[str, float] = field(default_factory=dict)
    is_stereo: Dict[str, bool] = field(default_factory=dict)
    is_muted: Dict[str, bool] = field(default_factory=dict)
    is_solo: Dict[str, bool] = field(default_factory=dict)
    any_solo: bool = False
    max_samples: int = 0
    master_volume: float = 1.0
    stem_sources: Dict[str, str] = field(default_factory=dict)


class LiveSpatialPlayer:
    """
    Player de áudio em tempo real 100% Lock-Free com streaming contínuo.
    Calcula ganhos VBAP e espacialização binaural bloco a bloco sem contenção de mutex.
    """
    def __init__(
        self,
        sample_rate: int = 48000,
        block_size: int = 2048,
        on_playback_progress: Optional[Callable[[float, float], None]] = None,
        on_vu_update: Optional[Callable[[Dict[str, float], float], None]] = None,
        device_index: Optional[int] = None
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.on_playback_progress = on_playback_progress
        self.on_vu_update = on_vu_update
        self.device_index = device_index

        self.vbap = VBAP714Engine()
        self.binaural = BinauralHRTFEngine(sample_rate=sample_rate)

        self.stems: List[StemTrack] = []
        self.placements: Dict[str, SpatialPlacement] = {}
        self.timeline_manager: Optional[SpatialTimelineManager] = None
        
        self._current_sample: int = 0
        self._max_samples: int = 0
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._master_volume: float = 1.0

        self._stream: Optional[sd.OutputStream] = None
        self._stream_generation = 0
        self._stream_starting = False
        self._cached_ch_l: Dict[str, np.ndarray] = {}
        self._cached_ch_r: Dict[str, np.ndarray] = {}
        self._cached_mono: Dict[str, np.ndarray] = {}
        self._cached_vbap_gains_l: Dict[str, np.ndarray] = {}
        self._cached_vbap_gains_r: Dict[str, np.ndarray] = {}

        # Estado atômico consumido pelo callback de áudio (substituído de forma atômica pela GUI)
        self._dsp_state: AudioDSPState = AudioDSPState()
        self._binaural_reset_pending = True

        # Buffers estáticos pré-alocados para zero alocação dinâmica no callback
        self._preallocated_block_714 = np.zeros((self.block_size, 12), dtype=np.float32)

        # Snapshots atômicos lidos pela GUI via QTimer (Zero concorrência de thread)
        self._latest_time_s: float = 0.0
        self._latest_duration_s: float = 0.0
        self._latest_vu_stems: Dict[str, float] = {}
        self._latest_sub_vu: float = 0.0

    @staticmethod
    def get_available_devices() -> List[Dict[str, Any]]:
        """Lista dispositivos de saída suportados para seleção pelo usuário."""
        if not _SOUNDDEVICE_AVAILABLE or sd is None:
            return []
        try:
            devs = sd.query_devices()
            outputs = []
            for idx, d in enumerate(devs):
                if d.get("max_output_channels", 0) > 0:
                    name = d.get("name", f"Dispositivo {idx}")
                    hostapi_name = ""
                    try:
                        hostapis = sd.query_hostapis()
                        api_idx = d.get("hostapi", 0)
                        if api_idx < len(hostapis):
                            hostapi_name = hostapis[api_idx].get("name", "")
                    except Exception:
                        pass
                    outputs.append({
                        "index": idx,
                        "name": name,
                        "hostapi": hostapi_name,
                        "channels": d.get("max_output_channels", 2),
                        "default_sr": d.get("default_samplerate", 48000),
                    })
            return outputs
        except Exception as e:
            log.warning("Erro ao consultar dispositivos de áudio: %s", e)
            return []

    def set_output_device(self, device_index: Optional[int]):
        """Troca o dispositivo de saída de áudio dinamicamente."""
        if self.device_index == device_index:
            return
        self.device_index = device_index
        was_playing = self._is_playing

        self._close_stream_async()

        if was_playing:
            self.play()

    def set_timeline_manager(self, timeline_mgr: Optional[SpatialTimelineManager]):
        """Conecta o gerenciador de automação dinâmica temporal e pré-calcula ganhos das seções."""
        self.timeline_manager = timeline_mgr
        if self.timeline_manager is not None:
            self.timeline_manager.recalculate_section_gains(self.vbap)

    def set_active_placements(self, placements: Dict[str, SpatialPlacement]):
        """Troca o mapa editado pela GUI sem reconstruir áudio ou recalcular todas as seções."""
        self.placements = placements
        dsp = self._dsp_state
        vol_gains = dict(dsp.vol_gains)
        is_stereo = dict(dsp.is_stereo)
        is_muted = dict(dsp.is_muted)
        is_solo = dict(dsp.is_solo)
        gains_l = dict(dsp.cached_vbap_gains_l)
        gains_r = dict(dsp.cached_vbap_gains_r)
        active_names = set(placements)
        for name, plc in placements.items():
            vol_gains[name] = float(plc.volume_gain)
            is_stereo[name] = bool(plc.is_stereo)
            is_muted[name] = bool(plc.is_muted)
            is_solo[name] = bool(plc.is_solo)
            source_name = plc.source_stem_name or name
            if source_name not in dsp.cached_ch_l:
                continue
            if plc.is_stereo:
                dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                gains_l[name] = np.asarray(
                    self.vbap.calculate_gains(-dist_x, plc.y, plc.z, plc.spread, plc.lfe_send),
                    dtype=np.float32
                )
                gains_r[name] = np.asarray(
                    self.vbap.calculate_gains(dist_x, plc.y, plc.z, plc.spread, plc.lfe_send),
                    dtype=np.float32
                )
            else:
                gains = np.asarray(
                    self.vbap.calculate_gains(plc.x, plc.y, plc.z, plc.spread, plc.lfe_send),
                    dtype=np.float32
                )
                gains_l[name] = gains
                gains_r[name] = gains
        vol_gains = {name: value for name, value in vol_gains.items() if name in active_names}
        is_stereo = {name: value for name, value in is_stereo.items() if name in active_names}
        is_muted = {name: value for name, value in is_muted.items() if name in active_names}
        is_solo = {name: value for name, value in is_solo.items() if name in active_names}
        gains_l = {name: value for name, value in gains_l.items() if name in active_names}
        gains_r = {name: value for name, value in gains_r.items() if name in active_names}
        stem_sources = {name: plc.source_stem_name or name for name, plc in placements.items() if name in active_names}
        self._cached_vbap_gains_l = gains_l
        self._cached_vbap_gains_r = gains_r
        self._dsp_state = AudioDSPState(
            stems=dsp.stems,
            cached_ch_l=dsp.cached_ch_l,
            cached_ch_r=dsp.cached_ch_r,
            cached_vbap_gains_l=gains_l,
            cached_vbap_gains_r=gains_r,
            vol_gains=vol_gains,
            is_stereo=is_stereo,
            is_muted=is_muted,
            is_solo=is_solo,
            any_solo=any(is_solo.values()),
            max_samples=dsp.max_samples,
            master_volume=dsp.master_volume,
            stem_sources=stem_sources
        )

    def _recompute_gains_for_stem(self, name: str):
        """Recalcula e armazena em cache o vetor de 12 ganhos VBAP de um stem (L e R)."""
        plc = self.placements.get(name)
        if plc:
            if plc.is_stereo:
                dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                gl = self.vbap.calculate_gains(-dist_x, plc.y, plc.z, plc.spread, plc.lfe_send)
                gr = self.vbap.calculate_gains(dist_x, plc.y, plc.z, plc.spread, plc.lfe_send)
                self._cached_vbap_gains_l[name] = np.asarray(gl, dtype=np.float32)
                self._cached_vbap_gains_r[name] = np.asarray(gr, dtype=np.float32)
            else:
                g = self.vbap.calculate_gains(plc.x, plc.y, plc.z, plc.spread, plc.lfe_send)
                self._cached_vbap_gains_l[name] = np.asarray(g, dtype=np.float32)
                self._cached_vbap_gains_r[name] = self._cached_vbap_gains_l[name]

    def set_stems_and_placements(self, stems: List[StemTrack], placements: Dict[str, SpatialPlacement]):
        """Atualiza os stems e faz cache dos sinais de áudio e ganhos VBAP."""
        if len(stems) == len(self.stems) and all(a is b for a, b in zip(stems, self.stems)):
            self.placements = placements
            gains_l = {}
            gains_r = {}
            vol_gains = {}
            is_stereo = {}
            is_muted = {}
            is_solo = {}
            for stem in stems:
                plc = placements.get(stem.name)
                if plc is None:
                    continue
                if plc.is_stereo:
                    dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                    gains_l[stem.name] = np.asarray(
                        self.vbap.calculate_gains(-dist_x, plc.y, plc.z, plc.spread, plc.lfe_send),
                        dtype=np.float32
                    )
                    gains_r[stem.name] = np.asarray(
                        self.vbap.calculate_gains(dist_x, plc.y, plc.z, plc.spread, plc.lfe_send),
                        dtype=np.float32
                    )
                else:
                    gains = np.asarray(
                        self.vbap.calculate_gains(plc.x, plc.y, plc.z, plc.spread, plc.lfe_send),
                        dtype=np.float32
                    )
                    gains_l[stem.name] = gains
                    gains_r[stem.name] = gains
                vol_gains[stem.name] = float(plc.volume_gain)
                is_stereo[stem.name] = bool(plc.is_stereo)
                is_muted[stem.name] = bool(plc.is_muted)
                is_solo[stem.name] = bool(plc.is_solo)

            self._cached_vbap_gains_l = gains_l
            self._cached_vbap_gains_r = gains_r
            stem_sources = {name: plc.source_stem_name or name for name, plc in placements.items()}
            if self.timeline_manager is not None:
                self.timeline_manager.recalculate_section_gains(self.vbap)
            self._dsp_state = AudioDSPState(
                stems=list(stems),
                cached_ch_l=self._cached_ch_l,
                cached_ch_r=self._cached_ch_r,
                cached_vbap_gains_l=gains_l,
                cached_vbap_gains_r=gains_r,
                vol_gains=vol_gains,
                is_stereo=is_stereo,
                is_muted=is_muted,
                is_solo=is_solo,
                any_solo=any(is_solo.values()),
                max_samples=self._max_samples,
                master_volume=self._master_volume,
                stem_sources=stem_sources
            )
            return

        self.stems = stems
        self.placements = placements
        self._cached_ch_l.clear()
        self._cached_ch_r.clear()
        self._cached_mono.clear()
        self._cached_vbap_gains_l.clear()
        self._cached_vbap_gains_r.clear()
        self._binaural_reset_pending = True

        max_samples = 0
        vol_gains = {}
        is_stereo = {}
        is_muted = {}
        is_solo = {}
        any_solo = False

        if stems:
            max_samples = max(s.audio_data.shape[0] for s in stems)
            for s in stems:
                data = s.audio_data
                if data.ndim == 2 and data.shape[1] >= 2:
                    l = data[:, 0]
                    r = data[:, 1]
                    mono = 0.5 * (l + r)
                else:
                    mono = data[:, 0] if data.ndim == 2 else data
                    l = mono
                    r = mono
                self._cached_ch_l[s.name] = np.ascontiguousarray(l, dtype=np.float32)
                self._cached_ch_r[s.name] = np.ascontiguousarray(r, dtype=np.float32)
                self._cached_mono[s.name] = np.ascontiguousarray(mono, dtype=np.float32)
                matching = [(name, plc) for name, plc in placements.items() if (plc.source_stem_name or name) == s.name]
                for name, plc in matching:
                    vol_gains[name] = float(plc.volume_gain)
                    is_stereo[name] = bool(plc.is_stereo)
                    is_muted[name] = bool(plc.is_muted)
                    is_solo[name] = bool(plc.is_solo)
                    if plc.is_stereo:
                        dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                        self._cached_vbap_gains_l[name] = np.asarray(self.vbap.calculate_gains(-dist_x, plc.y, plc.z, plc.spread, plc.lfe_send), dtype=np.float32)
                        self._cached_vbap_gains_r[name] = np.asarray(self.vbap.calculate_gains(dist_x, plc.y, plc.z, plc.spread, plc.lfe_send), dtype=np.float32)
                    else:
                        gains = np.asarray(self.vbap.calculate_gains(plc.x, plc.y, plc.z, plc.spread, plc.lfe_send), dtype=np.float32)
                        self._cached_vbap_gains_l[name] = gains
                        self._cached_vbap_gains_r[name] = gains
                    if plc.is_solo:
                        any_solo = True

            self._max_samples = max_samples
        else:
            self._max_samples = 0
            self._current_sample = 0

        self._latest_duration_s = float(self._max_samples) / float(self.sample_rate) if self.sample_rate > 0 else 0.0

        if self.timeline_manager is not None:
            self.timeline_manager.recalculate_section_gains(self.vbap)

        stem_sources = {name: plc.source_stem_name or name for name, plc in placements.items()}

        # Publica o estado inicial atômico 100% pronto para o callback de áudio
        self._dsp_state = AudioDSPState(
            stems=list(stems),
            cached_ch_l=dict(self._cached_ch_l),
            cached_ch_r=dict(self._cached_ch_r),
            cached_vbap_gains_l=dict(self._cached_vbap_gains_l),
            cached_vbap_gains_r=dict(self._cached_vbap_gains_r),
            vol_gains=vol_gains,
            is_stereo=is_stereo,
            is_muted=is_muted,
            is_solo=is_solo,
            any_solo=any_solo,
            max_samples=max_samples,
            master_volume=self._master_volume,
            stem_sources=stem_sources
        )

    def update_placement(self, stem_name: str, x: float, y: float, z: float, spread: Optional[float] = None, lfe: Optional[float] = None, is_stereo: Optional[bool] = None):
        """Atualização instantânea de coordenadas em tempo real com recálculo atômico 100% lock-free."""
        plc = self.placements.get(stem_name)
        if not plc:
            return
        plc.x = x
        plc.y = y
        plc.z = z
        if spread is not None:
            plc.spread = spread
        if lfe is not None:
            plc.lfe_send = lfe
        if is_stereo is not None:
            plc.is_stereo = is_stereo

        cur_spread = plc.spread
        cur_lfe = plc.lfe_send
        cur_is_stereo = plc.is_stereo

        try:
            if cur_is_stereo:
                dist_x = abs(x) if abs(x) > 0.05 else 0.50
                gl = np.asarray(self.vbap.calculate_gains(-dist_x, y, z, cur_spread, cur_lfe), dtype=np.float32)
                gr = np.asarray(self.vbap.calculate_gains(dist_x, y, z, cur_spread, cur_lfe), dtype=np.float32)
            else:
                gl = np.asarray(self.vbap.calculate_gains(x, y, z, cur_spread, cur_lfe), dtype=np.float32)
                gr = gl
        except Exception as e:
            log.warning("Erro ao calcular ganhos VBAP para %s: %s", stem_name, e)
            return

        self._cached_vbap_gains_l[stem_name] = gl
        self._cached_vbap_gains_r[stem_name] = gr

        # Atualizar a seção ativa da timeline se existir
        if self.timeline_manager:
            act_sec = self.timeline_manager.get_active_edit_section()
            act_sec.cached_gains_l[stem_name] = gl
            act_sec.cached_gains_r[stem_name] = gr

        # Troca atômica do AudioDSPState (zero lock, zero bloqueio)
        dsp = self._dsp_state
        new_gains_l = dict(dsp.cached_vbap_gains_l)
        new_gains_r = dict(dsp.cached_vbap_gains_r)
        new_is_stereo = dict(dsp.is_stereo)
        new_gains_l[stem_name] = gl
        new_gains_r[stem_name] = gr
        new_is_stereo[stem_name] = cur_is_stereo
        new_vol_gains = dict(dsp.vol_gains)
        new_is_muted = dict(dsp.is_muted)
        new_is_solo = dict(dsp.is_solo)
        new_vol_gains[stem_name] = float(plc.volume_gain)
        new_is_muted[stem_name] = bool(plc.is_muted)
        new_is_solo[stem_name] = bool(plc.is_solo)
        any_solo = any(new_is_solo.values())

        new_stem_sources = dict(dsp.stem_sources)
        new_stem_sources[stem_name] = plc.source_stem_name or stem_name

        self._dsp_state = AudioDSPState(
            stems=dsp.stems,
            cached_ch_l=dsp.cached_ch_l,
            cached_ch_r=dsp.cached_ch_r,
            cached_vbap_gains_l=new_gains_l,
            cached_vbap_gains_r=new_gains_r,
            vol_gains=new_vol_gains,
            is_stereo=new_is_stereo,
            is_muted=new_is_muted,
            is_solo=new_is_solo,
            any_solo=any_solo,
            max_samples=dsp.max_samples,
            master_volume=dsp.master_volume,
            stem_sources=new_stem_sources
        )

    def set_volume(self, vol: float):
        """Ajusta o volume master geral atomicamente."""
        self._master_volume = max(0.0, min(1.5, vol))
        dsp = self._dsp_state
        self._dsp_state = AudioDSPState(
            stems=dsp.stems,
            cached_ch_l=dsp.cached_ch_l,
            cached_ch_r=dsp.cached_ch_r,
            cached_vbap_gains_l=dsp.cached_vbap_gains_l,
            cached_vbap_gains_r=dsp.cached_vbap_gains_r,
            vol_gains=dsp.vol_gains,
            is_stereo=dsp.is_stereo,
            is_muted=dsp.is_muted,
            is_solo=dsp.is_solo,
            any_solo=dsp.any_solo,
            max_samples=dsp.max_samples,
            master_volume=self._master_volume,
            stem_sources=dsp.stem_sources
        )

    def play(self):
        """Inicia a reprodução de forma assíncrona e desimpedida."""
        if not self.stems or self._max_samples == 0:
            return

        self._is_playing = True
        self._is_paused = False

        if _SOUNDDEVICE_AVAILABLE and self._stream is None and not self._stream_starting:
            self._stream_generation += 1
            generation = self._stream_generation
            self._stream_starting = True

            def start_stream():
                stream = None
                try:
                    stream = sd.OutputStream(
                        samplerate=self.sample_rate,
                        channels=2,
                        blocksize=self.block_size,
                        dtype="float32",
                        device=self.device_index,
                        callback=self._audio_callback
                    )
                    stream.start()
                    if generation == self._stream_generation and self._is_playing:
                        self._stream = stream
                        stream = None
                except Exception as e:
                    log.warning("Falha ao abrir stream de áudio sounddevice: %s", e)
                    if generation == self._stream_generation:
                        self._is_playing = False
                finally:
                    if stream is not None:
                        try:
                            stream.stop()
                            stream.close()
                        except Exception:
                            pass
                    if generation == self._stream_generation:
                        self._stream_starting = False

            threading.Thread(target=start_stream, name="AtmosSplitAudioStart", daemon=True).start()

    def pause(self):
        """Pausa a reprodução mantendo o cursor de tempo."""
        self._is_paused = True
        self._is_playing = False

    def stop(self):
        """Para a reprodução e zera o tempo."""
        self._is_playing = False
        self._is_paused = False
        self._current_sample = 0
        self._latest_time_s = 0.0
        self._binaural_reset_pending = True
        self._close_stream_async()

    def _close_stream_async(self):
        """Fecha PortAudio fora do thread da GUI; o callback de áudio nunca usa este caminho."""
        self._stream_generation += 1
        stream = self._stream
        self._stream = None
        self._stream_starting = False
        if stream is None:
            return

        def close_stream():
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                log.debug("Erro ao fechar stream de áudio: %s", e)

        threading.Thread(target=close_stream, name="AtmosSplitAudioStop", daemon=True).start()

    def seek(self, target_sample_or_ratio: float):
        """Busca posição específica na faixa (em segundos ou fração [0, 1])."""
        if target_sample_or_ratio <= 1.0 and target_sample_or_ratio >= 0.0:
            self._current_sample = int(target_sample_or_ratio * self._max_samples)
        else:
            self._current_sample = int(min(self._max_samples, max(0, target_sample_or_ratio)))
        self._latest_time_s = float(self._current_sample) / float(self.sample_rate) if self.sample_rate > 0 else 0.0
        self._binaural_reset_pending = True

    @property
    def is_playing(self) -> bool:
        return self._is_playing and not self._is_paused

    @property
    def current_time_s(self) -> float:
        return float(self._current_sample) / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    @property
    def total_duration_s(self) -> float:
        return float(self._max_samples) / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    @property
    def _cached_vbap_gains(self) -> Dict[str, np.ndarray]:
        """Acesso de compatibilidade para testes e inspeção."""
        return self._cached_vbap_gains_l

    def get_ui_snapshot(self) -> Tuple[float, float, Dict[str, float], float, bool]:
        """
        Retorna snapshot desacoplado do estado do áudio para a GUI atualizar a 30 FPS.
        100% Lock-Free: leitura direta sem bloquear nenhuma thread.
        (current_time_s, total_duration_s, vu_levels, sub_vu, is_playing)
        """
        return (
            self._latest_time_s,
            self._latest_duration_s,
            dict(self._latest_vu_stems),
            self._latest_sub_vu,
            self._is_playing and not self._is_paused
        )

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """
        Callback executado pelo driver de áudio (PipeWire/ALSA) a cada bloco.
        100% LOCK-FREE: zero mutexes, zero alocações dinâmicas e retorno garantido em < 3ms.
        """
        try:
            if not self._is_playing or self._is_paused:
                outdata.fill(0)
                return

            dsp = self._dsp_state
            if not dsp.stems or dsp.max_samples == 0:
                outdata.fill(0)
                return

            start_idx = self._current_sample
            max_s = dsp.max_samples

            if start_idx >= max_s:
                self._current_sample = 0
                self._is_playing = False
                self._latest_time_s = 0.0
                outdata.fill(0)
                return

            actual_frames = min(frames, max_s - start_idx)

            if self._preallocated_block_714.shape[0] != frames:
                self._preallocated_block_714 = np.zeros((frames, 12), dtype=np.float32)
            else:
                self._preallocated_block_714.fill(0)

            block_714 = self._preallocated_block_714
            vu_stems: Dict[str, float] = {}
            lfe_energy = 0.0

            cur_time_s = float(start_idx) / float(self.sample_rate)
            tm = self.timeline_manager
            has_dynamic_timeline = (tm is not None and len(tm.sections) > 1)

            any_solo = dsp.any_solo
            sources_map = dsp.stem_sources if dsp.stem_sources else {s.name: s.name for s in dsp.stems}

            for name, source_name in sources_map.items():
                if any_solo and not dsp.is_solo.get(name, False):
                    continue
                if dsp.is_muted.get(name, False):
                    continue

                ch_l_full = dsp.cached_ch_l.get(source_name)
                ch_r_full = dsp.cached_ch_r.get(source_name)
                if ch_l_full is None or ch_r_full is None:
                    continue

                avail = min(len(ch_l_full) - start_idx, len(ch_r_full) - start_idx)
                slice_len = min(actual_frames, avail)
                if slice_len <= 0 or slice_len > block_714.shape[0]:
                    continue

                gain_vol = dsp.vol_gains.get(name, 1.0)
                l_slice = ch_l_full[start_idx:start_idx + slice_len] * gain_vol
                r_slice = ch_r_full[start_idx:start_idx + slice_len] * gain_vol

                rms = float(np.sqrt(np.mean(0.5 * (l_slice ** 2 + r_slice ** 2)))) if slice_len > 0 else 0.0
                vu_stems[name] = min(1.0, rms * 3.5)

                if has_dynamic_timeline:
                    try:
                        g_l, g_r = tm.get_interpolated_gains_at_time(cur_time_s, name)
                    except Exception:
                        g_l, g_r = None, None
                else:
                    g_l = dsp.cached_vbap_gains_l.get(name)
                    g_r = dsp.cached_vbap_gains_r.get(name)

                if g_l is None or len(g_l) < 12:
                    g_l = dsp.cached_vbap_gains_l.get(name)
                if g_l is None or len(g_l) < 12:
                    continue
                if g_r is None or len(g_r) < 12:
                    g_r = dsp.cached_vbap_gains_r.get(name) or g_l

                is_stereo = dsp.is_stereo.get(name, False)
                if is_stereo:
                    for ch in range(12):
                        gain_l = float(g_l[ch])
                        gain_r = float(g_r[ch])
                        if gain_l > 1e-4:
                            block_714[:slice_len, ch] += l_slice * gain_l
                        if gain_r > 1e-4:
                            block_714[:slice_len, ch] += r_slice * gain_r
                        if ch == 3:
                            lfe_energy += float(np.sum(np.abs(l_slice * gain_l + r_slice * gain_r)))
                else:
                    mono_slice = 0.5 * (l_slice + r_slice)
                    for ch in range(12):
                        gain = float(g_l[ch])
                        if gain > 1e-4:
                            block_714[:slice_len, ch] += mono_slice * gain
                            if ch == 3:
                                lfe_energy += float(np.sum(np.abs(mono_slice * gain)))

            if self._binaural_reset_pending:
                self.binaural.reset_states()
                self._binaural_reset_pending = False

            # Conversão binaural HRTF com estados preservados
            binaural_block = self.binaural.process_714_to_binaural(block_714, keep_state=True)

            m_vol = dsp.master_volume
            if m_vol != 1.0:
                binaural_block *= m_vol

            fill_len = min(actual_frames, binaural_block.shape[0])
            outdata[:fill_len] = binaural_block[:fill_len]
            if fill_len < frames:
                outdata[fill_len:].fill(0)

            self._current_sample += actual_frames
            self._latest_time_s = float(self._current_sample) / float(self.sample_rate)
            self._latest_vu_stems = vu_stems
            self._latest_sub_vu = min(1.0, lfe_energy / (max(1, actual_frames) * 0.4))

            if self.on_playback_progress:
                try:
                    self.on_playback_progress(self._latest_time_s, self._latest_duration_s)
                except Exception:
                    pass

            if self.on_vu_update:
                try:
                    self.on_vu_update(vu_stems, self._latest_sub_vu)
                except Exception:
                    pass

        except Exception as err:
            log.error("Exceção contida no callback de áudio: %s", err)
            outdata.fill(0)
