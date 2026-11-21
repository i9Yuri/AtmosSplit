"""Medição por blocos, alinhada à geometria do layout canônico 7.1.4."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

# BS.1770-4, anexo 3, tabela 4. Somente SL/SR estão entre 60° e 120° no plano horizontal.
WEIGHTS = np.array([1., 1., 1., 0., 1., 1., 1.41, 1.41, 1., 1., 1., 1.])


def _k_filter(rate: int) -> np.ndarray:
    # Protótipos dos dois biquads de De Man. A RLB usa numerador sem escala.
    k = np.tan(np.pi*1681.974450955533/rate)
    q = .7071752369554196
    vh = 10**(3.999843853973347/20)
    vb = vh**.4996667741545416
    den = 1 + k/q + k*k
    shelf = [(vh+vb*k/q+k*k)/den, 2*(k*k-vh)/den, (vh-vb*k/q+k*k)/den,
             1., 2*(k*k-1)/den, (1-k/q+k*k)/den]
    k = np.tan(np.pi*38.13547087602444/rate)
    q = .5003270373238773
    den = 1+k/q+k*k
    return np.array([shelf, [1., -2., 1., 1., 2*(k*k-1)/den, (1-k/q+k*k)/den]])


def _energy(block: np.ndarray, hop: int) -> np.ndarray:
    power = np.einsum("ij,j,ij->i", block, WEIGHTS, block)
    starts = np.arange(0, len(block), hop)
    return np.add.reduceat(power, starts)/np.diff(np.r_[starts, len(block)])


def integrated(energies: np.ndarray) -> float:
    if not len(energies):
        return -np.inf
    windows = (np.convolve(energies, np.full(4, .25), "valid")
               if len(energies) >= 4 else np.array([energies.mean()]))
    audible = windows[windows >= 10**((-70+.691)/10)]
    if not len(audible):
        return -np.inf
    gated = audible[audible >= .10*audible.mean()]
    return float(-.691 + 10*np.log10(gated.mean()))


def true_peak(audio: np.ndarray) -> float:
    """Pico interpolado 4×. Contexto FIR dos blocos mantém os intersamples nas bordas."""
    peak = 0.
    for at in range(0, len(audio), 16384):
        end = min(at+16384, len(audio))
        left, right = max(0, at-32), min(len(audio), end+32)
        interpolated = signal.resample_poly(audio[left:right], 4, 1, axis=0)
        peak = max(peak, float(np.max(np.abs(interpolated[(at-left)*4:(end-left)*4]))))
    return peak


@dataclass(frozen=True)
class MasterReport:
    integrated_lufs: float
    true_peak_dbtp: float
    vocal_balance_db: float | None
    presence_balance_db: float | None
    gain_db: float


class MixMeter:
    def __init__(self, rate: int, vocal: bool):
        self.hop = max(1, round(rate*.1))
        self.k = _k_filter(rate)
        self.presence = (signal.butter(2, [1000, min(rate*.45, 4500)], btype="bandpass",
                                       fs=rate, output="sos") if rate*.45 > 1000 else None)
        self.states: dict[str, np.ndarray] = {}
        self.vocal = vocal
        self.history: list[np.ndarray] = []
        self.final_partial = False

    def _filter(self, key: str, sos: np.ndarray, data: np.ndarray) -> np.ndarray:
        if key not in self.states:
            self.states[key] = np.zeros((len(sos), 2, data.shape[1]))
        out, self.states[key] = signal.sosfilt(sos, data, axis=0, zi=self.states[key])
        return out

    def add(self, mix: np.ndarray, lead: np.ndarray | None) -> None:
        """Blocos múltiplos de hop, exceto o último. Os estados nunca reiniciam na borda."""
        total_k = self._filter("mix", self.k, mix)
        values = [_energy(total_k, self.hop)]
        if self.vocal and lead is not None:
            lead_k = self._filter("lead", self.k, lead)
            values.extend((_energy(lead_k, self.hop), _energy(total_k-lead_k, self.hop)))
            if self.presence is not None:
                for key, data in (("lead_band", lead), ("music_band", mix-lead)):
                    values.append(_energy(self._filter(key, self.presence, data), self.hop))
        self.history.append(np.column_stack(values))
        self.final_partial = bool(len(mix) % self.hop)

    def values(self) -> np.ndarray:
        rows = np.concatenate(self.history) if self.history else np.zeros((0, 1))
        return rows[:-1] if self.final_partial and len(rows) > 4 else rows

    @staticmethod
    def balance(rows: np.ndarray) -> tuple[float | None, float | None]:
        if rows.shape[1] < 3 or not len(rows):
            return None, None
        active = rows[:, 1] > max(1e-7, rows[:, 1].max()*.0032)
        def ratio(a: int, b: int) -> float | None:
            if b >= rows.shape[1] or not active.any():
                return None
            numerator, denominator = rows[active, a].sum(), rows[active, b].sum()
            if min(numerator, denominator) <= 1e-12:
                return None
            return float(10*np.log10(numerator/denominator))
        return ratio(1, 2), ratio(3, 4)
