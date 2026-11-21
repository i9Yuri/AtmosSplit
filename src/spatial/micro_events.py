"""Microautomação baseada em ataques acústicos. Tempos absolutos em segundos."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass
from math import ceil, gcd, isfinite
from typing import TYPE_CHECKING

import numpy as np
from scipy import fft, ndimage, signal

from .auto_director import SpatialPlacement
from ..separation.stem_engine import StemTrack

if TYPE_CHECKING:
    from .timeline_manager import SpatialSection

HOP_S = .005
MIR_RATE = 16000
MIR_HOP = 80


def smooth(t):
    t = np.clip(t, 0., 1.)
    return t*t*(3.-2.*t)


@dataclass(frozen=True)
class SpatialEvent:
    start_s: float
    end_s: float
    attack_s: float
    release_s: float
    stem: str
    kind: str
    x: float
    y: float
    z: float
    end_x: float
    end_y: float
    end_z: float
    gain: float
    spread: float
    lfe_send: float
    confidence: float
    intensity: float = 1.

    def __post_init__(self):
        if not (0 <= self.start_s < self.end_s and isfinite(self.end_s)
                and 0 < self.attack_s <= self.end_s-self.start_s+.000001
                and 0 < self.release_s <= self.end_s-self.start_s+.000001
                and all(-1 <= c <= 1 for c in (self.x, self.y, self.end_x, self.end_y))
                and all(0 <= c <= 1 for c in (self.z, self.end_z, self.spread, self.lfe_send,
                                               self.confidence, self.intensity))
                and 0 <= self.gain <= 2 and self.stem and self.kind):
            raise ValueError("Evento espacial com tempo, rota ou ganho inválido.")

    @property
    def audible(self) -> bool:
        return self.intensity > 0 and self.confidence + .22*self.intensity >= .80

    @property
    def mirrored(self) -> bool:
        return self.kind in ("throw", "crash", "swell", "bass_accent")

    def envelope(self, t):
        return smooth((t-self.start_s)/self.attack_s)*smooth((self.end_s-t)/self.release_s)*self.intensity

    def progress(self, t):
        return smooth((t-self.start_s)/(self.end_s-self.start_s))

    def pose(self, fraction: float) -> SpatialPlacement:
        return SpatialPlacement(self.stem+"::micro", self.x+(self.end_x-self.x)*fraction,
                                self.y+(self.end_y-self.y)*fraction, self.z+(self.end_z-self.z)*fraction,
                                self.spread, self.lfe_send, self.gain,
                                is_stereo=self.mirrored, source_stem_name=self.stem)


@dataclass
class Observation:
    level: np.ndarray
    bands: np.ndarray
    attacks: np.ndarray
    bursts: list[tuple[int, int]]

    def signature(self, start: int, end: int) -> np.ndarray:
        bands = self.bands[start:max(start+1, end)].mean(axis=0)
        return bands / max(1e-8, np.linalg.norm(bands))


def _observe(stem: StemTrack) -> Observation:
    audio = stem.audio_data.reshape(len(stem.audio_data), -1)
    div = gcd(stem.sample_rate, MIR_RATE)
    small = signal.resample_poly(audio, MIR_RATE//div, stem.sample_rate//div, axis=0) if stem.sample_rate != MIR_RATE else audio
    n = ceil(len(small)/MIR_HOP)
    padded = np.pad(small, ((0, n*MIR_HOP-len(small)), (0, 0)))
    level = np.sqrt(np.mean(padded.reshape(n, MIR_HOP, -1)**2, axis=(1, 2)))
    reference = max(.001, float(level.max())*.12, float(np.percentile(level, 95)))
    level = level/reference
    # Descritores estéreo por potência. Um backing em Side conserva a sua assinatura.
    edges = np.unique(np.round(np.geomspace(1, 256, 26)).astype(int))
    bands = np.empty((n, len(edges)), "f")
    win = np.hanning(512).astype("f")
    padded = np.pad(small, ((256, 256), (0, 0)))
    windows = np.lib.stride_tricks.sliding_window_view(padded, 512, axis=0)[::MIR_HOP]
    for i in range(0, n, 192):
        batch = windows[i:min(i+192, n)]
        power = (abs(fft.rfft(batch*win, axis=-1))**2).mean(axis=1)
        bands[i:i+len(batch)] = np.sqrt(np.add.reduceat(power, edges, axis=1))
    norm = bands/np.maximum(1e-6, np.linalg.norm(bands, axis=1, keepdims=True))
    flux = np.maximum(0., np.diff(norm, axis=0, prepend=norm[:1])).sum(axis=1)
    attack = np.maximum(0., level-np.r_[np.zeros(min(3,n)), level[:-3]]) + .28*flux*np.minimum(1., level)
    peaks = signal.find_peaks(np.pad(attack, 1), prominence=.12, distance=12)[0]-1
    active = ndimage.binary_closing(np.pad(level > .095, 8), structure=np.ones(5))[8:-8]
    edges_vad = np.flatnonzero(np.diff(np.r_[False, active, False]))
    bursts = []
    for a, b in edges_vad.reshape(-1, 2):
        # Desata sílabas com uma reentrada pronunciada mesmo sem silêncio absoluto.
        cuts = [a]
        for valley in signal.find_peaks(-level[a:b], prominence=.24, distance=16)[0]+a:
            if level[valley] < .28 and valley-cuts[-1] >= 14 and b-valley >= 14:
                cuts.append(valley)
        bursts.extend((int(i), int(j)) for i,j in zip(cuts, [*cuts[1:], b]) if j-i >= 8)
    return Observation(level, norm, peaks, bursts)


# Início e destino dos envios auxiliares na sala, ganho linear e largura.
ROUTES = {
    "syllable": ((.70,-1.,.06), (.70,-.90,.28), .96, .09),
    "response": ((.70,-1.,.04), (.64,-.80,.44), 1.08, .13),
    "throw": ((.70,-1.,.06), (.60,-.63,.94), 1.10, .10),
    "fill": ((-.64,.72,.12), (.65,-.74,.68), .72, .22),
    "snare_hit": ((-.85,.0,.15), (-.72,-.65,.40), .55, .22),
    "crash": ((.60,.60,1.), (.60,-.60,1.), .88, .17),
    "open_hat": ((.65,.55,.65), (.60,-.60,.94), .56, .24),
    "kick_hit": ((0.,1.,0.), (0.,1.,0.), 0., 0.),
    "sub_drop": ((0.,1.,0.), (0.,1.,0.), 0., 0.),
    "bass_accent": ((.55,.88,0.), (.85,.4,0.), .38, .12),
    "motif": ((-.85,.10,.18), (-.72,-.78,.48), .59, .22),
    "swell": ((.7,-.40,.38), (.60,-.60,1.), .72, .28),
}


class _Candidates:
    """Observações por seção e grupos de gestos que concorrem pelo mesmo orçamento."""

    def __init__(self, section: SpatialSection, intensity: float):
        self.section = section
        self.intensity = intensity
        self.frames = (round(section.start_time_s/HOP_S), round(section.end_time_s/HOP_S))
        self.beat = 60/section.tempo_bpm if section.tempo_bpm > 0 else .5
        self.loud = section.section_type in ("chorus", "climax")
        self.groups: list[list[SpatialEvent]] = []

    def event(self, stem: str, kind: str, first: int, last: int, score: float, side: int = 1) -> SpatialEvent | None:
        start = max(self.section.start_time_s, float(first*HOP_S))
        end = min(self.section.end_time_s, float(last*HOP_S))
        if end-start < .035:
            return None
        p, q, gain, width = ROUTES[kind]
        return SpatialEvent(start, end, min(.018, (end-start)*.16), min(.095, (end-start)*.27),
                            stem, kind, side*p[0], p[1], p[2], side*q[0], q[1], q[2],
                            gain, width, .32 if kind in ("sub_drop", "kick_hit") else 0.,
                            float(score), self.intensity)

    def add(self, stem: str, kind: str, first: int, last: int, score: float) -> None:
        candidate = self.event(stem, kind, first, last, score)
        if candidate:
            self.groups.append([candidate])

    def vocals(self, observations: dict[str, Observation], lead_name: str, phrase_ends: list[int]) -> None:
        lead = observations.get(lead_name)
        if lead is None:
            return
        first, last = self.frames
        beat, loud = self.beat, self.loud
        phrases = [(a,b) for a,b in lead.bursts if first<=a<last]
        used = set()
        for i in range(2, len(phrases)):
            triplet = phrases[i-2:i+1]
            if any(a in used or not .045 <= (b-a)*HOP_S <= min(.42,.8*beat) for a,b in triplet):
                continue
            intervals = np.diff([a for a,b in triplet])*HOP_S
            if min(intervals) < .09 or max(intervals) > min(.85,1.6*beat) or min(intervals)/max(intervals) < .72:
                continue
            sig = [lead.signature(a,b) for a,b in triplet]
            similarity = min(sig[0]@sig[1], sig[1]@sig[2])
            if similarity < .86:
                continue
            candidates = [self.event(lead_name,"syllable",a,b,.83+.15*float(min(1,similarity)), side)
                          for (a,b),side in zip(triplet[1:],(1,-1))]
            if all(candidates):
                self.groups.append(candidates)
                used.update(a for a,b in triplet)

        for name in (lead_name, "backing_vocals"):
            obs = observations.get(name)
            if obs is None:
                continue
            for a,b in obs.bursts:
                if not first <= a < last or a in used and name == lead_name or (b-a)*HOP_S > 1.0:
                    continue
                lower = bisect_left(phrase_ends, a-min(.95,1.7*beat)/HOP_S)
                upper = bisect_right(phrase_ends, a-.02/HOP_S)
                previous = [(c,d) for c,d in lead.bursts[lower:upper]
                            if (d-c)*HOP_S >= max(.28,(b-a)*HOP_S*1.35)]
                if not previous:
                    continue
                c,d = previous[-1]
                similarity = obs.signature(a,b) @ lead.signature(max(c,d-(b-a)),d)
                gap_after = lead.level[b:b+round(.10/HOP_S)]
                isolated = len(gap_after) == 0 or np.mean(gap_after) < .28
                if similarity >= .89 and isolated and (name == lead_name or lead.level[a:b].max(initial=0)<.35):
                    self.add(name,"response",a,b,.80+.17*min(1.,float(similarity)))
        others = [o.level for k,o in observations.items() if k not in (lead_name,"backing_vocals")]
        for a,b in phrases:
            if not loud or (b-a)*HOP_S < max(.42,.85*beat) or lead.level[a:b].max() < .78:
                continue
            # Voz sustentada e suporte instrumental coincidem. Lança parte da nota.
            support = max((v[a:min(len(v),b)].max(initial=0) for v in others), default=0.)
            if support >= .55:
                start = a+round(min(.24,.40*beat)/HOP_S)
                score = min(.99, .86 + .065*float(lead.level[a:b].mean()) + .055*float(support))
                self.add(lead_name,"throw",start,min(b,start+round(min(.95,1.45*beat)/HOP_S)),score)

    def instruments(self, observations: dict[str, Observation], lead_name: str) -> None:
        first, last = self.frames
        beat, loud = self.beat, self.loud
        for name,obs in observations.items():
            if name in (lead_name,"backing_vocals"):
                continue
            attacks = (np.asarray([a for a, _ in obs.bursts], dtype=int)
                       if name in ("sub_bass_lfe","bass","kick","melodic_bass") else obs.attacks)
            peaks = attacks[(attacks>=first)&(attacks<last)]
            if name == "air_ambience":
                # Um crescendo lento pode não ter ataque percussivo detectável.
                for a, b in obs.bursts:
                    if not first <= a < last or b-a < 55:
                        continue
                    envelope = ndimage.uniform_filter1d(obs.level[a:min(b,last,a+320)], 11)
                    top = int(np.argmax(envelope))
                    if top >= 40 and envelope[top] > .65 and envelope[top]-envelope[:12].mean() > .42:
                        self.add(name, "swell", a, min(b, a+top+24), .86)
            for j,a in enumerate(peaks):
                future = obs.level[a:min(last,a+36)]
                if not len(future):
                    continue
                strength = float(future.max())
                if strength < .63:
                    continue
                elapsed = a*HOP_S-self.section.start_time_s
                entry = elapsed < max(.40,beat*1.5) and loud
                prev = (a-peaks[j-1])*HOP_S if j else np.inf
                gap = (peaks[j+1]-a)*HOP_S if j+1<len(peaks) else np.inf
                span = min(.55, gap, (last-a)*HOP_S)
                if name in ("snare","drums"):
                    dense = peaks[j:np.searchsorted(peaks, a+round(beat*1.35/HOP_S), side="right")]
                    if len(dense)>=3 and np.max(np.diff(dense))*HOP_S <= beat*.65:
                        self.add(name,"fill",a,dense[-1]+18,.93)
                    elif prev>beat*1.5 and gap>beat*.8 and strength>.90:
                        self.add(name,"snare_hit",a,a+28,.79)
                elif name in ("cymbals_hihat","cymbals","hihat") and (entry or gap>beat*.65):
                    if np.mean(future[:24]) > .18:
                        self.add(name,"crash" if entry else "open_hat",a,a+round(span/HOP_S),.93 if entry else .76)
                elif name in ("sub_bass_lfe","bass","kick"):
                    if entry or (prev>beat*1.8 and strength>1.15):
                        self.add(name,"kick_hit" if name=="kick" else "sub_drop",a,a+round(min(span,.26)/HOP_S),.88)
                elif name=="melodic_bass" and gap>beat*.4 and strength>.92:
                    self.add(name,"bass_accent",a,a+round(min(span,.22)/HOP_S),.74)
                elif name in ("guitar_keys","other","air_ambience"):
                    recent = obs.level[max(0,a-36):a]
                    if name=="air_ambience" and (entry or (len(recent) and strength>2*recent.mean())):
                        self.add(name,"swell",a,a+round(span/HOP_S),.81)
                    elif len(peaks)>=3 and gap < beat*.90 and strength>.84:
                        origin = self.section.downbeats_s[0] if self.section.downbeats_s else self.section.start_time_s
                        phase = ((a*HOP_S-origin)/beat) % 1
                        offbeat = min(abs(phase-q) for q in (.25,.5,.75)) < .12
                        neighbor = peaks[j+1]
                        timbre_change = obs.signature(a,a+12) @ obs.signature(neighbor,neighbor+12)
                        if offbeat or timbre_change < .88:
                            self.add(name,"motif",a,a+round(span/HOP_S),.78+.04*offbeat)

    def select(self, recent_end: dict[tuple[str, str], float]) -> tuple[SpatialEvent, ...]:
        beat = self.beat
        # Um gesto pode conter duas sílabas. Aceitar o par preserva a resposta musical.
        duration = self.section.end_time_s-self.section.start_time_s
        budget = min(12, max(3, ceil(duration/(3.8 if self.loud else 5.5))))
        counts: Counter = Counter()
        selected: list[SpatialEvent] = []
        gestures = 0
        for group in sorted(self.groups, key=lambda g: (-g[0].confidence, g[0].start_s)):
            if gestures >= budget:
                continue
            head = group[0]
            key = (head.stem, head.kind)
            cooldown = max(2., 8*beat) if head.kind in ("response","throw","fill") else max(.55, 2*beat)
            if (counts[key] >= max(1, ceil(duration/(15 if head.kind=="throw" else 11)))
                    or head.start_s < recent_end.get(key, -np.inf)+cooldown):
                continue
            clashes = any(old.end_s+(max(2.5, 8*beat) if old.kind==new.kind=="throw" else .28)>new.start_s
                          and new.end_s+.28>old.start_s and old.stem==new.stem for old in selected for new in group)
            if not clashes and all(new.lfe_send or sum(old.start_s<=new.start_s<old.end_s and not old.lfe_send for old in selected)<2 for new in group):
                selected.extend(group)
                gestures += 1
                counts[key] += 1
        events = tuple(sorted(selected, key=lambda e:e.start_s))
        for ev in events:
            recent_end[ev.stem, ev.kind] = ev.end_s
        return events


def detect_micro_events(stems: list[StemTrack], sections: list[SpatialSection], intensity: float = .7) -> None:
    observations = {stem.name: _observe(stem) for stem in stems if len(stem.audio_data)}
    lead_name = next((name for name in ("lead_vocal", "vocals", "voice") if name in observations), "")
    lead = observations.get(lead_name)
    phrase_ends = [end for _, end in lead.bursts] if lead else []
    recent_end: dict[tuple[str, str], float] = {}
    intensity = float(np.clip(intensity, 0, 1))
    for section in sections:
        candidates = _Candidates(section, intensity)
        candidates.vocals(observations, lead_name, phrase_ends)
        candidates.instruments(observations, lead_name)
        section.micro_events = candidates.select(recent_end)
