"""Estrutura musical por contraste local e repetição de descritores sincronizados."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, gcd
from typing import Sequence

import numpy as np
from scipy import fft, ndimage, signal
from scipy.cluster import hierarchy
from scipy.spatial.distance import cdist, pdist

from ..separation.stem_engine import StemTrack

RATE = 12000
HOP = 240
FPS = RATE / HOP
ROLES = ("lead", "backing", "kick", "snare", "cymbal", "bass", "harmony")
ROLE_MAP = {
    "vocals": "lead", "voice": "lead", "lead_vocal": "lead", "backing_vocals": "backing",
    "drums": "kick", "drum": "kick", "kick": "kick", "snare": "snare",
    "cymbals_hihat": "cymbal", "hihat": "cymbal", "cymbals": "cymbal",
    "bass": "bass", "sub_bass_lfe": "bass", "melodic_bass": "bass",
}


@dataclass(frozen=True)
class Pulse:
    beats: np.ndarray
    bars: np.ndarray
    bpm: float
    meter: int
    confidence: float


@dataclass(frozen=True)
class MusicalPart:
    start: float
    end: float
    kind: str
    family: str
    confidence: float
    description: str


def _relative(values: np.ndarray) -> np.ndarray:
    reference = max(float(np.percentile(values, 95)), float(values.max(initial=0)) * .10, 1e-5)
    return np.minimum(values / reference, 1.5)


def _frames(audio: np.ndarray, sr: int, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Energia a cada 20 ms na taxa original, incluindo os agudos da percussão."""
    data = audio.reshape(len(audio), -1) if audio.size else np.empty((0, 1))
    powers = np.zeros((count, 2), dtype=np.float32)
    valid = min(count, ceil(len(data) * FPS / sr))
    for start in range(0, valid, 512):
        stop = min(start + 512, valid)
        edges = np.minimum(np.floor(np.arange(start, stop+1) * sr / FPS).astype(int), len(data))
        chunk = data[edges[0]:edges[-1]]
        power = np.mean(np.square(chunk, dtype=np.float32), axis=1)
        mid = chunk[:, 0] if chunk.shape[1] == 1 else .5 * (chunk[:, 0]+chunk[:, 1])
        edges -= edges[0]
        lengths = np.maximum(1, np.diff(edges))
        powers[start:stop, 0] = np.add.reduceat(power, edges[:-1]) / lengths
        powers[start:stop, 1] = np.add.reduceat(mid**2, edges[:-1]) / lengths
    return powers[:, 0], np.maximum(0, powers[:, 0]-powers[:, 1])


def _add_mix(dest: np.ndarray, audio: np.ndarray, sr: int) -> None:
    if not len(audio):
        return
    audio = audio[:, None] if audio.ndim == 1 else audio[:, :2]
    div = gcd(sr, RATE)
    small = signal.resample_poly(audio, RATE//div, sr//div, axis=0) if sr != RATE else audio
    length = min(len(dest), len(small))
    dest[:length] += small[:length]


def _spectrum(mix: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nfft = 2048
    freq = fft.rfftfreq(nfft, 1/RATE)
    # A potência dos dois canais preserva sinais fora de fase.
    window = np.hanning(nfft).astype("f")
    padded = np.pad(mix, ((nfft//2, nfft//2), (0, 0)))
    windows = np.lib.stride_tricks.sliding_window_view(padded, nfft, axis=0)[::HOP]
    mel = 2595*np.log10(1+freq/700)
    centers = np.linspace(0, mel[-1], 28)
    filters = np.maximum(0, 1-np.abs(mel[:, None]-centers[None, 1:-1])/(centers[1]-centers[0]))
    filters /= np.maximum(1e-9, filters.sum(axis=0))
    pitch = np.rint(69 + 12*np.log2(np.maximum(freq, 1)/440)).astype(int)
    chroma_filter = (pitch[:, None] % 12 == np.arange(12)) * ((freq >= 55) & (freq < 3800))[:, None]
    projection = np.ascontiguousarray(np.column_stack((filters, chroma_filter, freq < 80)), dtype="f")
    bands = np.zeros((count, 39), dtype="f")
    for i in range(0, count, 128):
        batch = windows[i:min(i+128, count)]
        power = np.abs(fft.rfft(batch*window, axis=-1))**2
        bands[i:i+len(batch)] = (power.mean(axis=1) @ projection) / nfft
    logmel = np.log1p(150*bands[:, :26])
    cepstrum = fft.dct(logmel, norm="ortho", axis=1)[:, 1:9]
    chroma = np.sqrt(bands[:, 26:38])
    chroma /= np.maximum(.01, np.linalg.norm(chroma, axis=1, keepdims=True))
    flux = np.maximum(0, np.diff(logmel, axis=0, prepend=logmel[:1])).mean(axis=1)
    return chroma, cepstrum, flux, _relative(np.sqrt(bands[:, -1]))


def _pulse(flux: np.ndarray, drum: np.ndarray, kick: np.ndarray, duration: float) -> Pulse:
    empty = Pulse(np.empty(0), np.empty(0), 0., 0, 0.)
    onset = _relative(flux) + 1.7*_relative(np.maximum(0, np.diff(drum, prepend=0)))
    onset = np.maximum(0, onset - ndimage.median_filter(onset, size=19))
    if duration < 2 or np.max(onset) < .05:
        return empty
    peaks = signal.find_peaks(np.pad(onset, 1), prominence=.12, distance=4)[0] - 1
    if len(peaks) < 4:
        return empty
    ac = signal.correlate(onset, onset, mode="full", method="fft")[len(onset)-1:]
    lags = np.arange(15, min(52, len(ac)//3))
    if not len(lags):
        return empty
    ac /= max(ac[0], 1e-7)
    scores = (ac[lags] + .42*ac[2*lags] + .22*ac[3*lags]) * np.exp(-.12*np.log(lags/25)**2)
    lag = int(lags[np.argmax(scores)])
    confidence = float(np.clip(scores.max()/1.4, 0, 1))
    if confidence < .18:
        return empty

    phase = np.argmax([onset[i::lag].sum() for i in range(lag)])
    # O período local acompanha ataques próximos à batida prevista.
    times, accents = [], []
    period = float(lag)
    prediction = float(phase)
    while prediction < len(onset)-.5:
        lo = max(0, round(prediction-.20*period))
        hi = min(len(onset), round(prediction+.20*period)+1)
        near = np.arange(lo, hi)
        if not len(near):
            break
        score = onset[near]*np.exp(-.5*((near-prediction)/(.13*period))**2)
        beat = int(near[np.argmax(score)]) if score.max() > .1 else round(prediction)
        if times:
            period = float(np.clip(.78*period+.22*(beat-times[-1]), .75*lag, 1.25*lag))
        times.append(beat)
        accents.append(float(.35*onset[beat]+3*np.max(kick[max(0, beat-2):beat+4])))
        prediction = beat+period

    if len(times) < 4:
        return empty
    beats = np.asarray(times)
    accents = np.asarray(accents)
    best, meter, offset = -np.inf, 4, 0
    variance = np.mean((accents-accents.mean())**2)
    for m in (4, 3):
        # Quanto da variação dos acentos é explicado pela repetição métrica?
        phases = np.arange(len(accents)) % m
        strengths = np.array([np.median(accents[phases == k]) for k in range(m)])
        error = np.mean((accents-strengths[phases])**2)
        evidence = 1-error/max(variance, 1e-9) + (.025 if m == 4 else 0)
        if evidence > best:
            best, meter, offset = evidence, m, int(strengths.argmax())
            if np.ptp(strengths) < .04*max(.1, accents.mean()):
                offset = 0
    return Pulse(beats/FPS, beats[offset::meter]/FPS, float(60*FPS/np.median(np.diff(beats))), meter, confidence)


def _novelty(features: np.ndarray, radii: tuple[int, ...]) -> np.ndarray:
    """Foote em faixas diagonais da SSM gaussiana. A memória independe do quadrado da duração."""
    count = len(features)
    novelty = np.zeros(count)
    for radius in radii:
        if 2*radius > count:
            continue
        taper = np.exp(-.5*(np.arange(radius)/(.7*radius))**2)
        kernel = np.r_[-taper[::-1], taper]
        kernel /= taper.sum()
        for first in range(radius, count-radius+1, 128):
            stop = min(count-radius+1, first+128)
            local = features[first-radius:stop+radius-1]
            ssm = np.exp(-cdist(local, local, metric="sqeuclidean")/.85)
            tiles = np.lib.stride_tricks.sliding_window_view(ssm, (2*radius, 2*radius))
            idx = np.arange(stop-first)
            values = np.einsum("nij,i,j->n", tiles[idx, idx], kernel, kernel)
            novelty[first:stop] = np.maximum(novelty[first:stop], values)
    return novelty


def analyze_structure(stems: Sequence[StemTrack], duration: float,
                      mix_audio: np.ndarray | None = None, mix_sample_rate: int | None = None
                      ) -> tuple[list[MusicalPart], Pulse]:
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError("A duração deve ser positiva.")
    if mix_audio is not None and not mix_sample_rate:
        raise ValueError("Informe a taxa da mixagem estéreo.")
    count = max(1, ceil(duration*FPS))
    mix = np.zeros((count*HOP, 2), "f")
    env = np.zeros((count, len(ROLES)), "f")
    side = np.zeros(count, "f")
    for stem in stems:
        power, width = _frames(stem.audio_data, stem.sample_rate, count)
        env[:, ROLES.index(ROLE_MAP.get(stem.name.lower(), "harmony"))] += power
        side += width
        if mix_audio is None:
            _add_mix(mix, stem.audio_data, stem.sample_rate)
    if mix_audio is not None:
        _add_mix(mix, mix_audio, mix_sample_rate)
    chroma, mfcc, flux, sub = _spectrum(mix, count)
    total = env.sum(axis=1)
    width = np.sqrt(np.clip(side/np.maximum(1e-8, total), 0, 1))
    energy = _relative(np.sqrt(total))
    kick = np.sqrt(env[:, 2])
    kick /= max(1e-6, np.percentile(kick, 99.8), .15*kick.max())
    env = np.column_stack([_relative(np.sqrt(column)) for column in env.T])
    drum = env[:, 2:5].max(axis=1)
    pulse = _pulse(flux, drum, kick, duration)
    window = max(5, round(FPS*(60/pulse.bpm if pulse.bpm else .5)))
    attacks = np.maximum(0, np.diff(env[:, 2:5], axis=0, prepend=env[:1, 2:5]))
    density = ndimage.uniform_filter1d(attacks, size=window, axis=0, mode="nearest")
    density = np.column_stack([_relative(channel) for channel in density.T])
    # VAD contínuo relativo ao stem, com piso absoluto aplicado na normalização.
    vad = np.clip((20*np.log10(np.maximum(env[:, 0], 1e-5))+34)/25, 0, 1)
    vad = ndimage.uniform_filter1d(vad, size=7, mode="nearest")
    frames = np.column_stack((chroma, np.clip(mfcc/8, -1, 1)*.5,
                              np.log1p(5*env)/np.log(6), energy, width*.6,
                              .38*density, .45*sub, .45*vad))
    grid = np.unique(np.r_[0., pulse.beats if pulse.bpm else np.arange(0, duration, .25), duration])
    indices = np.minimum(count, np.rint(grid*FPS).astype(int))
    valid = np.r_[np.diff(indices) > 0, True]
    grid, indices = grid[valid], indices[valid]
    if len(grid) < 2:
        grid, indices = np.array([0., duration]), np.array([0, count])
    grid[0], indices[0], indices[-1] = 0, 0, count
    pooled = np.add.reduceat(frames, indices[:-1], axis=0) / np.diff(indices)[:, None]
    nov = _novelty(pooled, (2, 4, 8) if pulse.bpm else (3, 6, 12))
    threshold = max(.095, np.median(nov)+2.5*np.median(np.abs(nov-np.median(nov))))
    peaks, _ = signal.find_peaks(nov, height=threshold, prominence=max(.055, .10*nov.max(initial=0)))
    candidates: list[tuple[float, float]] = []
    for peak in peaks:
        t = grid[peak]
        if pulse.bpm and len(pulse.bars):
            # A cabeça de compasso mais próxima carrega uma transição com pulso confiável.
            t = pulse.bars[np.argmin(abs(pulse.bars-t))]
        else:
            # Pausa vocal e mudança espectral refinam a borda em música sem pulso.
            center = round(t*FPS)
            near = np.arange(max(1, center-10), min(count, center+11))
            if len(near):
                d = np.linalg.norm(frames[near]-frames[near-1], axis=1)
                t = near[np.argmax(d - .12*env[near, 0])]/FPS
        candidates.append((float(nov[peak]), float(t)))
    cuts = {0.: 0., duration: 0.}
    spacing = (pulse.meter*60/pulse.bpm*1.5) if pulse.bpm else 1.8
    for score, t in sorted(candidates, reverse=True):
        if min(abs(t-edge) for edge in cuts) >= spacing:
            cuts[t] = score
    bounds = sorted(cuts)
    slices = [slice(min(count-1, round(a*FPS)), max(round(a*FPS)+1, round(b*FPS)))
              for a, b in zip(bounds, bounds[1:])]
    summaries = np.array([frames[s].mean(axis=0) for s in slices])
    n = len(summaries)
    clusters = (hierarchy.fcluster(hierarchy.linkage(pdist(summaries), method="complete"),
                                   .55, criterion="distance") if n > 1 else np.ones(1, int))
    family_ids = {c: i+1 for i, c in enumerate(dict.fromkeys(clusters))}
    strengths = np.array([np.mean(energy[s]) for s in slices])
    rhythm = np.array([np.mean(drum[s]) for s in slices])
    voice = np.array([np.mean(vad[s]) for s in slices])
    ranks = strengths + .30*rhythm + .12*voice
    recurring = [c for c in family_ids if np.sum(clusters == c) > 1]
    chorus = max(recurring, key=lambda c: ranks[clusters == c].mean()) if recurring else None
    if chorus is not None and ranks[clusters == chorus].mean() < np.max(ranks) - .32:
        chorus = None
    parts = []
    for i, (a, b, s) in enumerate(zip(bounds, bounds[1:], slices)):
        fam = clusters[i]
        section_energy = energy[s]
        third = max(1, len(section_energy)//3)
        growth = section_energy[-third:].mean() - section_energy[:third].mean()
        if n == 1:
            kind = "uniform"
        elif i == 0 and fam not in recurring and (ranks[i] + .1 < max(ranks) or voice[i] < .12):
            kind = "intro"
        elif i == n-1 and fam != chorus and ranks[i] < ranks[i-1]-.12:
            kind = "outro"
        elif growth > .17 and i+1 < n and ranks[i+1] > ranks[i]:
            kind = "buildup"
        elif fam == chorus or (ranks[i] >= max(ranks)-.10 and np.ptp(ranks) > .25):
            kind = "climax" if i > n/2 and fam in clusters[:i] and fam not in clusters[i+1:] else "chorus"
        elif 0 < i < n-1 and rhythm[i] < .45*max(rhythm) and ranks[i] < ranks[i-1]-.12:
            kind = "breakdown"
        elif voice[i] < .14 and np.max(voice) > .35:
            kind = "solo"
        elif 0 < i < n-1 and fam not in recurring and i > n/2:
            kind = "bridge"
        else:
            kind = "verse"
        confidence = (min(.93, .32 + .24*min(cuts[a] or cuts[b], 1.5) +
                          .12*pulse.confidence + .13*(fam in recurring)) if n > 1 else .25)
        details = (f"Atividade vocal {min(100, round(100*voice[i]))}% · "
                   f"percussão {min(100, round(100*rhythm[i]))}% · "
                   f"energia relativa {min(100, round(100*strengths[i]))}%")
        parts.append(MusicalPart(a, b, kind, f"F{family_ids[fam]}", confidence, details))
    return parts, pulse
