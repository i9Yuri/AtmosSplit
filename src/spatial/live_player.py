"""
AtmosSplit — Live Spatial Audio Player (Pré-escuta Binaural em Tempo Real)
Motor de áudio contínuo de ultra-baixa latência usando sounddevice e PipeWire/ALSA.
Renderiza os blocos sob demanda aplicando VBAP 3D otimizado com suporte a:
- Espelhamento estéreo (is_stereo) para pratos, sintetizadores e ambiências
- Automação dinâmica temporal por trechos via SpatialTimelineManager
- Filtros HRTF contínuos com preservação de fase, sem estalos e sem engasgos
Isola totalmente a thread de áudio de callbacks GUI pesados via snapshot atômico.
"""

from __future__ import annotations

import math
import time
import logging
import threading
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


class LiveSpatialPlayer:
    """
    Player de áudio em tempo real com streaming contínuo.
    Calcula ganhos VBAP e espacialização binaural bloco a bloco.
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
        
        self._lock = threading.Lock()
        self._current_sample: int = 0
        self._max_samples: int = 0
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._master_volume: float = 1.0

        self._stream: Optional[sd.OutputStream] = None
        self._cached_ch_l: Dict[str, np.ndarray] = {}
        self._cached_ch_r: Dict[str, np.ndarray] = {}
        self._cached_mono: Dict[str, np.ndarray] = {}
        self._cached_vbap_gains_l: Dict[str, np.ndarray] = {}
        self._cached_vbap_gains_r: Dict[str, np.ndarray] = {}

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
        with self._lock:
            if self.device_index == device_index:
                return
            self.device_index = device_index
            was_playing = self._is_playing

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if was_playing:
            self.play()

    def set_timeline_manager(self, timeline_mgr: Optional[SpatialTimelineManager]):
        """Conecta o gerenciador de automação dinâmica temporal."""
        with self._lock:
            self.timeline_manager = timeline_mgr

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
        with self._lock:
            self.stems = stems
            self.placements = placements
            self._cached_ch_l.clear()
            self._cached_ch_r.clear()
            self._cached_mono.clear()
            self._cached_vbap_gains_l.clear()
            self._cached_vbap_gains_r.clear()
            self.binaural.reset_states()

            if stems:
                self._max_samples = max(s.audio_data.shape[0] for s in stems)
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
                    self._recompute_gains_for_stem(s.name)
            else:
                self._max_samples = 0
                self._current_sample = 0

            self._latest_duration_s = float(self._max_samples) / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    def update_placement(self, stem_name: str, x: float, y: float, z: float, spread: Optional[float] = None, lfe: Optional[float] = None, is_stereo: Optional[bool] = None):
        """Atualização instantânea de coordenadas em tempo real com recálculo atômico de ganhos."""
        with self._lock:
            if stem_name in self.placements:
                plc = self.placements[stem_name]
                plc.x = x
                plc.y = y
                plc.z = z
                if spread is not None:
                    plc.spread = spread
                if lfe is not None:
                    plc.lfe_send = lfe
                if is_stereo is not None:
                    plc.is_stereo = is_stereo
                self._recompute_gains_for_stem(stem_name)

    def set_volume(self, vol: float):
        self._master_volume = max(0.0, min(1.5, vol))

    def play(self):
        if not self.stems or self._max_samples == 0:
            return

        with self._lock:
            self._is_playing = True
            self._is_paused = False

        if _SOUNDDEVICE_AVAILABLE and (self._stream is None or not self._stream.active):
            try:
                self._stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=2,
                    blocksize=self.block_size,
                    dtype="float32",
                    device=self.device_index,
                    callback=self._audio_callback
                )
                self._stream.start()
            except Exception as e:
                log.warning("Falha ao abrir stream de áudio sounddevice: %s", e)
                self._stream = None

    def pause(self):
        with self._lock:
            self._is_paused = True
            self._is_playing = False
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass

    def stop(self):
        with self._lock:
            self._is_playing = False
            self._is_paused = False
            self._current_sample = 0
            self._latest_time_s = 0.0
            self.binaural.reset_states()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def seek(self, target_sample_or_ratio: float):
        """Busca posição específica na faixa (em segundos ou fração [0, 1])."""
        with self._lock:
            if target_sample_or_ratio <= 1.0 and target_sample_or_ratio >= 0.0:
                self._current_sample = int(target_sample_or_ratio * self._max_samples)
            else:
                self._current_sample = int(min(self._max_samples, max(0, target_sample_or_ratio)))
            self._latest_time_s = float(self._current_sample) / float(self.sample_rate) if self.sample_rate > 0 else 0.0
            self.binaural.reset_states()

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
        (current_time_s, total_duration_s, vu_levels, sub_vu, is_playing)
        """
        with self._lock:
            return (
                self._latest_time_s,
                self._latest_duration_s,
                dict(self._latest_vu_stems),
                self._latest_sub_vu,
                self._is_playing and not self._is_paused
            )

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """Callback executado pelo driver de áudio (PipeWire/ALSA) a cada bloco."""
        if not self._is_playing or self._is_paused:
            outdata.fill(0)
            return

        with self._lock:
            start_idx = self._current_sample
            max_s = self._max_samples

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
            use_dynamic_timeline = (
                self.timeline_manager is not None
                and hasattr(self.timeline_manager, "sections")
                and len(self.timeline_manager.sections) > 1
            )

            if use_dynamic_timeline:
                active_placements = self.timeline_manager.get_interpolated_placements(cur_time_s)
            else:
                active_placements = self.placements

            any_solo = any(active_placements.get(s.name, SpatialPlacement(s.name, 0,0,0,0,0,1)).is_solo for s in self.stems)

            for s in self.stems:
                plc = active_placements.get(s.name)
                if not plc:
                    continue
                if any_solo and not plc.is_solo:
                    continue
                if plc.is_muted:
                    continue

                ch_l_full = self._cached_ch_l.get(s.name)
                ch_r_full = self._cached_ch_r.get(s.name)
                if ch_l_full is None or ch_r_full is None:
                    continue

                slice_len = min(actual_frames, len(ch_l_full) - start_idx)
                if slice_len <= 0:
                    continue

                l_slice = ch_l_full[start_idx:start_idx + slice_len] * plc.volume_gain
                r_slice = ch_r_full[start_idx:start_idx + slice_len] * plc.volume_gain

                rms = float(np.sqrt(np.mean(0.5 * (l_slice ** 2 + r_slice ** 2)))) if slice_len > 0 else 0.0
                vu_stems[s.name] = min(1.0, rms * 3.5)

                if use_dynamic_timeline:
                    # Cálculo dinâmico para transições suaves entre seções
                    if plc.is_stereo:
                        dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
                        g_l = self.vbap.calculate_gains(-dist_x, plc.y, plc.z, plc.spread, plc.lfe_send)
                        g_r = self.vbap.calculate_gains(dist_x, plc.y, plc.z, plc.spread, plc.lfe_send)
                    else:
                        g_l = self.vbap.calculate_gains(plc.x, plc.y, plc.z, plc.spread, plc.lfe_send)
                        g_r = g_l
                else:
                    g_l = self._cached_vbap_gains_l.get(s.name)
                    g_r = self._cached_vbap_gains_r.get(s.name)
                    if g_l is None:
                        self._recompute_gains_for_stem(s.name)
                        g_l = self._cached_vbap_gains_l.get(s.name)
                        g_r = self._cached_vbap_gains_r.get(s.name)

                if plc.is_stereo:
                    for ch in range(12):
                        gain_l = g_l[ch]
                        gain_r = g_r[ch]
                        if gain_l > 1e-4:
                            block_714[:slice_len, ch] += l_slice * gain_l
                        if gain_r > 1e-4:
                            block_714[:slice_len, ch] += r_slice * gain_r
                        if ch == 3:
                            lfe_energy += float(np.sum(np.abs(l_slice * gain_l + r_slice * gain_r)))
                else:
                    mono_slice = 0.5 * (l_slice + r_slice)
                    for ch in range(12):
                        gain = g_l[ch]
                        if gain > 1e-4:
                            block_714[:slice_len, ch] += mono_slice * gain
                            if ch == 3:
                                lfe_energy += float(np.sum(np.abs(mono_slice * gain)))

            binaural_block = self.binaural.process_714_to_binaural(block_714, keep_state=True)

            if self._master_volume != 1.0:
                binaural_block *= self._master_volume

            outdata[:actual_frames] = binaural_block[:actual_frames]
            if actual_frames < frames:
                outdata[actual_frames:].fill(0)

            self._current_sample += actual_frames
            self._latest_time_s = float(self._current_sample) / float(self.sample_rate)
            self._latest_vu_stems = vu_stems
            self._latest_sub_vu = min(1.0, lfe_energy / (actual_frames * 0.4 + 1e-5))

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
