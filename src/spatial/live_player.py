"""Monitor binaural. O callback PortAudio só consome blocos já renderizados."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable

import numpy as np
try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

from .auto_director import SpatialPlacement
from .binaural_hrtf import BinauralHRTFEngine
from .mix_engine import MixPlan, MixSource, prepare_sources
from .native_monitor import NativePort, NativeRing
from .timeline_manager import SpatialTimelineManager
from .vbap_engine import VBAP714Engine
from ..separation.stem_engine import StemTrack


@dataclass(frozen=True)
class AudioDSPState:
    plan: MixPlan
    master_volume: float


@dataclass
class Transport:
    """Uma fila nativa por seek. Somente o produtor prepara DSP e publica medidores."""
    origin: int = 0
    next_sample: int = 0
    end: int = 0
    ring: NativeRing | None = None
    readings: tuple[tuple[int, dict[str, float], float], ...] = ()

    @property
    def cursor(self) -> int:
        return self.origin + (self.ring.consumed if self.ring else 0)

    @property
    def finished(self) -> bool:
        return self.ring is not None and self.cursor >= self.end

    def prepare(self, block: int, end: int) -> NativeRing:
        if self.ring is None:
            self.end = end
            self.ring = NativeRing(block, max(0, end-self.origin))
        return self.ring


class LiveSpatialPlayer:
    def __init__(self, sample_rate: int = 48000, block_size: int = 1024,
                 on_playback_progress: Callable | None = None, on_vu_update: Callable | None = None,
                 device_index: int | None = None, profile: str = "jbl"):
        self.sample_rate, self.block_size = sample_rate, block_size
        self.on_playback_progress, self.on_vu_update = on_playback_progress, on_vu_update
        self.device_index, self.profile = device_index, profile
        self.vbap = VBAP714Engine()
        self.binaural = BinauralHRTFEngine(sample_rate)
        self.stems: list[StemTrack] = []
        self.placements: dict[str, SpatialPlacement] = {}
        self.timeline_manager: SpatialTimelineManager | None = None
        self._sources: tuple[MixSource, ...] = ()
        self._master_volume = 1.
        self._dsp_state = AudioDSPState(MixPlan.compile((), self.vbap, {}, (), sample_rate), 1.)
        self._transport = Transport()
        self._stream_generation = 0
        self._stream = None
        self._stream_starting = False
        self._is_playing = False
        self.last_error = ""
        self._notified = None

    @staticmethod
    def get_available_devices() -> list[dict[str, Any]]:
        if sd is None:
            return []
        try:
            hosts = sd.query_hostapis()
            return [dict(index=i, name=d["name"], hostapi=hosts[d["hostapi"]]["name"],
                         channels=d["max_output_channels"], default_sr=d["default_samplerate"])
                    for i, d in enumerate(sd.query_devices()) if d["max_output_channels"] >= 2]
        except (sd.PortAudioError, OSError):
            return []

    def set_output_device(self, device_index: int | None) -> None:
        if self.device_index != device_index:
            resume = self.is_playing
            self.pause()
            self.device_index = device_index
            if resume:
                self.play()

    def _publish(self) -> None:
        sections = self.timeline_manager.sections if self.timeline_manager else ()
        plan = MixPlan.compile(self._sources, self.vbap, self.placements, sections, self.sample_rate)
        self._dsp_state = AudioDSPState(plan, self._master_volume)

    def set_timeline_manager(self, timeline_mgr: SpatialTimelineManager | None) -> None:
        self.timeline_manager = timeline_mgr
        self._publish()

    def set_active_placements(self, placements: dict[str, SpatialPlacement]) -> None:
        self.placements = placements
        if self.timeline_manager:
            self.timeline_manager.get_active_edit_section().placements = placements
        self._publish()

    def set_stems_and_placements(self, stems: list[StemTrack], placements: dict[str, SpatialPlacement]) -> None:
        changed = len(stems) != len(self.stems) or any(a is not b for a, b in zip(stems, self.stems))
        if changed:
            self.stop()
            self._sources = prepare_sources(stems, self.sample_rate, self.profile)
            self.stems = list(stems)
        self.placements = placements
        self._publish()

    def set_monitor_profile(self, profile: str) -> None:
        if self.profile != profile:
            self._sources = prepare_sources(self.stems, self.sample_rate, profile)
            self.profile = profile
            self._publish()

    def update_placement(self, stem_name: str, x: float, y: float, z: float,
                         spread: float | None = None, lfe: float | None = None,
                         is_stereo: bool | None = None) -> None:
        plc = self.placements.get(stem_name)
        if plc is None:
            return
        plc.x, plc.y, plc.z = x, y, z
        if spread is not None:
            plc.spread = spread
        if lfe is not None:
            plc.lfe_send = lfe
        if is_stereo is not None:
            plc.is_stereo = is_stereo
        if self.timeline_manager:
            self.timeline_manager.get_active_edit_section().placements[stem_name] = plc
        self._publish()

    def set_volume(self, vol: float) -> None:
        self._master_volume = max(0., min(1.5, vol))
        self._dsp_state = replace(self._dsp_state, master_volume=self._master_volume)

    def _produce(self, transport: Transport, dsp: AudioDSPState, hrtf: BinauralHRTFEngine,
                 previous: AudioDSPState | None = None) -> bool:
        start = transport.next_sample
        length = min(self.block_size, dsp.plan.frames-start)
        ring = transport.prepare(self.block_size, dsp.plan.frames)
        if length <= 0 or not ring.available:
            return False
        matrix = np.empty((length, 12), dtype="f")
        levels = {}
        dsp.plan.mix(start, matrix, meters=levels)
        if previous is not None and previous.plan is not dsp.plan:
            old = np.empty_like(matrix)
            previous.plan.mix(start, old)
            ramp = np.linspace(0, 1, length, dtype="f")[:, None]
            matrix = old + (matrix-old)*ramp
        stereo = hrtf.process_714_to_binaural(matrix)
        if previous is not None and previous.master_volume != dsp.master_volume:
            stereo *= np.linspace(previous.master_volume, dsp.master_volume, length, dtype="f")[:, None]
        else:
            stereo *= dsp.master_volume
        # Joelho suave apenas na saída de monitor, contínuo entre blocos.
        mask = np.abs(stereo) > .9
        hot = stereo[mask]
        stereo[mask] = np.sign(hot)*(.9+.1*np.tanh((np.abs(hot)-.9)/.1))
        if not ring.push(np.ascontiguousarray(stereo, dtype="f")):
            return False
        transport.next_sample += length
        sub = min(1., float(np.abs(matrix[:, 3]).mean())*2.5)
        transport.readings = (*transport.readings[-4:], (start, levels, sub))
        return True

    def play(self) -> None:
        if not self.stems or self.is_playing:
            return
        if sd is None:
            self.last_error = "PortAudio indisponível."
            return
        if self._transport.finished or self._transport.cursor >= self._dsp_state.plan.frames:
            self.seek_seconds(0)
        self._stream_generation += 1
        generation = self._stream_generation
        self._stream_starting = self._is_playing = True
        self.last_error = ""

        def run() -> None:
            stream = None
            current = None
            previous = None
            try:
                # Estado de filtragem exclusivo do produtor desta geração.
                hrtf = BinauralHRTFEngine(self.sample_rate)
                port = NativePort()
                while generation == self._stream_generation and self._is_playing:
                    transport = self._transport
                    if transport.finished:
                        break
                    if current is not transport:
                        hrtf.reset_states()
                        port.publish(transport.prepare(self.block_size, self._dsp_state.plan.frames))
                        current, previous = transport, None
                    port.collect()
                    dsp = self._dsp_state
                    if self._produce(transport, dsp, hrtf, previous):
                        previous = dsp
                        continue
                    if stream is None:
                        stream = port.open_stream(sd, self.sample_rate, self.block_size, self.device_index)
                        if generation != self._stream_generation:
                            break
                        stream.start()
                        if generation != self._stream_generation:
                            break
                        self._stream, self._stream_starting = stream, False
                    time.sleep(min(.003, self.block_size/self.sample_rate/4))
            except Exception as exc:
                if generation == self._stream_generation:
                    self.last_error = str(exc)
            finally:
                if stream is not None:
                    try:
                        if generation == self._stream_generation and self._transport.finished:
                            stream.stop()  # Permite que PipeWire reproduza o último bloco entregue.
                        else:
                            stream.abort()
                    except Exception as exc:
                        if generation == self._stream_generation:
                            self.last_error = str(exc)
                    finally:
                        try:
                            stream.close()
                        except Exception as exc:
                            if generation == self._stream_generation:
                                self.last_error = str(exc)
                if generation == self._stream_generation:
                    self._is_playing = self._stream_starting = False
                    self._stream = None
        # O interpretador aguarda o fechamento do PortAudio antes de executar Pa_Terminate.
        threading.Thread(target=run, name="AtmosSplit Monitor", daemon=False).start()

    def pause(self) -> None:
        self._stream_generation += 1
        self._is_playing = self._stream_starting = False
        self._stream = None
        sample = self._transport.cursor
        self._transport = Transport(sample, sample)

    def stop(self) -> None:
        self.pause()
        self._transport = Transport()

    def seek_seconds(self, time_s: float) -> None:
        sample = min(self._dsp_state.plan.frames, max(0, round(time_s*self.sample_rate)))
        self._transport = Transport(sample, sample)

    def seek(self, target_sample_or_ratio: float) -> None:
        target = target_sample_or_ratio
        self.seek_seconds(target*self.total_duration_s if 0 <= target <= 1 else target/self.sample_rate)

    @property
    def is_playing(self) -> bool:
        return self._is_playing and not self._transport.finished

    @property
    def current_time_s(self) -> float:
        return self._transport.cursor/self.sample_rate

    @property
    def total_duration_s(self) -> float:
        return self._dsp_state.plan.frames/self.sample_rate

    @property
    def underruns(self) -> int:
        ring = self._transport.ring
        return ring.underruns if ring else 0

    def get_ui_snapshot(self) -> tuple[float, float, dict[str, float], float, bool]:
        transport = self._transport
        cursor = transport.cursor
        now = cursor/self.sample_rate
        total = self.total_duration_s
        levels, sub = {}, 0.
        for start, meters, bass in reversed(transport.readings):
            if start < cursor:
                levels, sub = dict(meters), bass
                break
        if self._notified != (id(transport), cursor):
            self._notified = (id(transport), cursor)
            if self.on_playback_progress:
                self.on_playback_progress(now, total)
            if self.on_vu_update:
                self.on_vu_update(dict(levels), sub)
        return now, total, levels, sub, self.is_playing
