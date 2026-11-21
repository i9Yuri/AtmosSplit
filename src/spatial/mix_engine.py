"""Preparação dos sinais e automação de ganhos comum ao monitor e ao master."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import gcd, sqrt
from functools import lru_cache
from typing import Iterator, Sequence

import numpy as np
from scipy import signal

from .auto_director import SpatialPlacement
from .micro_events import SpatialEvent
from .vbap_engine import VBAP714Engine
from ..separation.stem_engine import StemTrack
from ..separation.vocal_image import vocal_axis

LEADS = frozenset(("lead_vocal", "vocals", "voice"))
MASKERS = frozenset(("other", "guitar_keys", "guitar", "synths", "piano", "backing_vocals"))
PROFILES = ("studio", "jbl")


def _readonly(data: np.ndarray) -> np.ndarray:
    data.flags.writeable = False
    return data


def stereo_at_rate(data: np.ndarray, source_rate: int, rate: int) -> np.ndarray:
    if rate <= 0 or source_rate <= 0:
        raise ValueError("Taxa de amostragem inválida.")
    data = np.asarray(data, dtype=np.float32)
    data = data[:, None] if data.ndim == 1 else data
    if data.ndim != 2 or data.shape[1] not in (1, 2):
        raise ValueError("O stem deve ser mono ou estéreo.")
    if rate != source_rate and len(data):
        d = gcd(rate, source_rate)
        data = signal.resample_poly(data, rate//d, source_rate//d, axis=0)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return np.array(data, dtype="f", order="C", copy=True)


def _presence(data: np.ndarray, rate: int) -> np.ndarray:
    upper = min(4500., .45*rate)
    if upper <= 1000 or len(data) < 2:
        return np.zeros_like(data)
    sos = signal.butter(2, [1000, upper], fs=rate, btype="bandpass", output="sos").astype("f")
    # Contexto de 20 ms de cada lado evita criar bordas entre blocos do filtro.
    out = np.empty_like(data)
    margin = max(1, rate//50)
    for i in range(0, len(data), 131072):
        end = min(i+131072, len(data))
        left, right = max(0, i-margin), min(len(data), end+margin)
        extended = data[left:right]
        filtered = signal.sosfiltfilt(sos, extended, axis=0, padlen=min(15, len(extended)-1))
        out[i:end] = filtered[i-left:end-left]
    return out


def _envelope(data: np.ndarray, hop: int) -> np.ndarray:
    if not len(data):
        return np.zeros(0)
    starts = np.arange(0, len(data), hop)
    power = np.einsum("ij,ij->i", data, data) / data.shape[1]
    return np.sqrt(np.add.reduceat(power, starts)/np.diff(np.r_[starts, len(data)]))


@dataclass(frozen=True)
class MixSource:
    name: str
    audio: np.ndarray
    bass: np.ndarray
    relief: np.ndarray | None
    correlation: float
    mono_weights: tuple[float, float]


def prepare_sources(stems: Sequence[StemTrack], rate: int, profile: str) -> tuple[MixSource, ...]:
    if profile not in PROFILES:
        raise ValueError(f"Perfil de monitoração desconhecido: {profile}")
    audio = {s.name: stereo_at_rate(s.audio_data, s.sample_rate, rate) for s in stems}
    if len(audio) != len(stems):
        raise ValueError("Os identificadores dos stems devem ser únicos.")
    hop = max(1, rate//50)
    voice = np.zeros(0)
    if profile == "jbl":
        envelopes = [_envelope(_presence(data, rate), hop) for name, data in audio.items() if name in LEADS]
        if envelopes:
            voice = np.zeros(max(map(len, envelopes)))
            for env in envelopes:
                voice[:len(env)] += env
    sources = []
    low = signal.butter(4, min(120., .4*rate), fs=rate, output="sos").astype("f")
    for name, data in audio.items():
        relief = None
        if name in MASKERS and len(voice) and voice.max() > .0002 and len(data):
            band = _presence(data, rate)
            mask = _envelope(band, hop)
            v = np.zeros_like(mask)
            common = min(len(voice), len(v))
            v[:common] = voice[:common]
            ref = max(np.percentile(voice, 85)*.2, .0006)
            active = np.clip(v/ref, 0, 1)
            overlap = np.clip(mask/np.maximum(v, .0006), 0, 1)
            reduction = (1-10**(-3.5/20))*active*overlap
            # Ataque gradual e liberação de aproximadamente 100 ms.
            for i in range(1, len(reduction)):
                speed = .55 if reduction[i] >= reduction[i-1] else .18
                reduction[i] = reduction[i-1] + speed*(reduction[i]-reduction[i-1])
            for i in range(0, len(band), 65536):
                j = min(i+65536, len(band))
                band[i:j] *= np.interp(np.arange(i, j)/hop-.5, np.arange(len(reduction)), reduction)[:, None]
            relief = _readonly(band)
        weights = (.5, .5)
        if name in LEADS or name == "backing_vocals":
            axis = vocal_axis(data)
            weights = (axis[0]/sqrt(2), axis[1]/sqrt(2))
        mid = data @ np.asarray(weights, dtype="f")
        bass = signal.sosfilt(low, mid) if len(mid) else mid
        power = float(np.einsum("ij,ij->", data, data, dtype="d"))
        cross = float(np.einsum("i,i->", data[:, 0], data[:, 1], dtype="d"))
        corr = np.clip(2*cross/max(power, 1e-20), -1, 1)
        sources.append(MixSource(name, _readonly(data), _readonly(bass), relief, float(corr), weights))
    return tuple(sources)


@dataclass(frozen=True)
class Scene:
    # Por stem, duas contribuições full-range + um envio mono filtrado ao LFE.
    gains: np.ndarray
    voice: float
    main_gains: np.ndarray


def placement_pair(vbap: VBAP714Engine, p: SpatialPlacement, correlation: float = 1.,
                   mono_weights: tuple[float, float] = (.5, .5)) -> np.ndarray:
    result = np.zeros((3, 12), dtype="f")
    if p.is_muted or p.volume_gain <= 0:
        return result
    if p.is_stereo:
        x = abs(p.x)
        left = vbap.calculate_gains(-x, p.y, p.z, p.spread)
        right = vbap.calculate_gains(x, p.y, p.z, p.spread)
        overlap = float(left @ right) * max(0., correlation)
        scale = p.volume_gain/sqrt(2*(1+overlap))
        result[0], result[1] = left*scale, right*scale
    else:
        gains = vbap.calculate_gains(p.x, p.y, p.z, p.spread)*p.volume_gain
        result[0], result[1] = mono_weights[0]*gains, mono_weights[1]*gains
    result[2, 3] = float(np.clip(p.lfe_send, 0, 1))*p.volume_gain
    return result


@lru_cache(maxsize=512)
def _trajectory(vbap: VBAP714Engine, event: SpatialEvent, correlation: float,
                mono_weights: tuple[float, float]) -> np.ndarray:
    # As trajetórias são imutáveis durante um arraste de fonte no inspetor.
    return _readonly(np.stack([placement_pair(vbap, event.pose(t), correlation, mono_weights)[:2]
                               for t in np.linspace(0, 1, 13)]))


@dataclass(frozen=True)
class Projection:
    event: SpatialEvent
    start: int
    end: int
    knots: np.ndarray

    def add(self, out: np.ndarray, dry: np.ndarray, bass: np.ndarray, at: int, rate: int, gain: float):
        lo = max(self.start-at, 0)
        hi = min(self.end-at, len(out))
        if hi <= lo or not gain:
            return
        event = self.event
        time = np.arange(at+lo, at+hi)/rate
        env = (gain*event.envelope(time)).astype("f")
        if event.lfe_send:
            out[lo:hi, 3] += bass[lo:hi]*env*event.lfe_send
        if event.gain:
            pos = event.progress(time)*(len(self.knots)-1)
            index = np.minimum(pos.astype(int), len(self.knots)-2)
            weight = (pos-index).astype("f")[:, None, None]
            gains = self.knots[index] + weight*(self.knots[index+1]-self.knots[index])
            out[lo:hi] += np.einsum("ni,nij->nj", dry[lo:hi], gains)*env[:, None]


@dataclass(frozen=True)
class MixPlan:
    sources: tuple[MixSource, ...]
    scenes: tuple[Scene, ...]
    boundaries: tuple[int, ...]
    half_widths: tuple[int, ...]
    frames: int
    rate: int
    projections: tuple[tuple[Projection, ...], ...]
    ends: tuple[tuple[int, ...], ...]

    @classmethod
    def compile(cls, sources: tuple[MixSource, ...], vbap: VBAP714Engine,
                placements: dict[str, SpatialPlacement], sections: Sequence, rate: int) -> MixPlan:
        names = {s.name: i for i, s in enumerate(sources)}
        scenes = []
        for section in (sections or [None]):
            group = section.placements if section else placements
            main = np.zeros(len(sources), dtype="f")
            gains = np.zeros((len(sources), 3, 12), dtype="f")
            solo = any(p.is_solo for p in group.values())
            voice = 0.
            for key, p in group.items():
                name = p.source_stem_name or key
                if name not in names or p.is_muted or (solo and not p.is_solo):
                    continue
                i = names[name]
                pair = placement_pair(vbap, p, sources[i].correlation, sources[i].mono_weights)
                if name == "sub_bass_lfe":
                    pair[:2] = 0  # Banda complementar exclusiva do subwoofer.
                gains[i] += pair
                if key == name and (section is None or section.micro_enabled):
                    main[i] = p.volume_gain
                if name in LEADS:
                    voice = max(voice, min(1., p.volume_gain))
            scenes.append(Scene(_readonly(gains), voice, _readonly(main)))
        boundaries = tuple(round(s.start_time_s*rate) for s in sections[1:])
        widths = tuple(max(0, round(rate*transition_half_width(a, b)))
                       for a, b in zip(sections, sections[1:]))
        projections = [[] for _ in sources]
        for section in sections:
            if not section.micro_enabled:
                continue
            for event in section.micro_events:
                if not event.audible or event.stem not in names:
                    continue
                i = names[event.stem]
                src = sources[i]
                knots = _trajectory(vbap, event, src.correlation, src.mono_weights)
                projections[i].append(Projection(event, round(event.start_s*rate), round(event.end_s*rate),
                                                 knots))
        tracks = tuple(tuple(sorted(p, key=lambda e:e.start)) for p in projections)
        ends = tuple(tuple(np.maximum.accumulate([e.end for e in track])) for track in tracks)
        return cls(sources, tuple(scenes), boundaries, widths,
                   max((len(s.audio) for s in sources), default=0), rate, tracks, ends)

    def _spans(self, start: int, end: int) -> Iterator[tuple[int, int, Scene, Scene | None, np.ndarray | None]]:
        pos = start
        while pos < end:
            i = bisect_right(self.boundaries, pos)
            transition = None
            if i and pos < self.boundaries[i-1]+self.half_widths[i-1]:
                transition = i-1
            elif i < len(self.boundaries) and pos >= self.boundaries[i]-self.half_widths[i]:
                transition = i
            if transition is not None and self.half_widths[transition]:
                k = transition
                boundary, half = self.boundaries[k], self.half_widths[k]
                stop = min(end, boundary+half)
                t = (np.arange(pos, stop)-boundary+half)/(2*half)
                weight = (t*t*(3-2*t)).astype("f")[:, None]
                yield pos, stop, self.scenes[k], self.scenes[k+1], weight
            else:
                stop = min(end, self.boundaries[i]-self.half_widths[i]) if i < len(self.boundaries) else end
                yield pos, stop, self.scenes[i], None, None
            pos = stop

    def mix(self, start: int, out: np.ndarray, lead_bus: np.ndarray | None = None,
            meters: dict[str, float] | None = None) -> None:
        out.fill(0.)
        if lead_bus is not None:
            lead_bus.fill(0.)
        for at, stop, a, b, w in self._spans(start, start+len(out)):
            for i, src in enumerate(self.sources):
                last = min(stop, len(src.audio))
                if last <= at:
                    continue
                dry = src.audio[at:last]
                bass = src.bass[at:last]
                relief = src.relief[at:last] if src.relief is not None else None

                def contribution(scene: Scene) -> np.ndarray:
                    data = dry if relief is None or not scene.voice else dry - scene.voice*relief
                    gains = scene.gains[i]
                    block = data @ gains[:2]
                    if relief is not None and scene.voice and gains[:2, 2].any():
                        # Folga adicional somente na presença da fonte mascarante no FC.
                        block[:, 2] -= .25*scene.voice*(relief @ gains[:2, 2])
                    block[:, 3] = bass*gains[2, 3]
                    for k in range(bisect_right(self.ends[i], at), len(self.projections[i])):
                        projection = self.projections[i][k]
                        if projection.start >= last:
                            break
                        projection.add(block, data, bass, at, self.rate, scene.main_gains[i])
                    return block

                block = contribution(a)
                if b is not None:
                    block += (contribution(b)-block)*w[:len(block)]
                dest = slice(at-start, last-start)
                out[dest] += block
                if lead_bus is not None and src.name in LEADS:
                    lead_bus[dest] += block
                if meters is not None:
                    meters[src.name] = float(min(1., 3.5*np.sqrt(np.sum(block*block)/len(block))))


def transition_half_width(a, b, window_s: float | None = None) -> float:
    beat_window = 60/b.tempo_bpm if b.tempo_bpm > 0 else 1.
    if a.section_type == "buildup" or b.section_type == "outro":
        beat_window *= b.beats_per_bar or a.beats_per_bar or 1
    return .5*min(window_s if window_s is not None else beat_window,
                  a.end_time_s-a.start_time_s, b.end_time_s-b.start_time_s)
