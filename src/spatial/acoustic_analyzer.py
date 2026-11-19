"""
AtmosSplit — Analisador Acústico de Stems
Analisa envelope de transientes, largura estéreo (Mid/Side),
densidade espectral em faixas-chave e centróide espectral.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import numpy as np


@dataclass
class StemAcousticProfile:
    stem_name: str
    rms_energy: float
    peak_amplitude: float
    crest_factor_db: float
    spectral_centroid_hz: float
    stereo_width_ratio: float       # 0.0 (Mono puro) a 1.0 (Super estéreo)
    sub_bass_energy_ratio: float    # < 80 Hz
    low_mid_energy_ratio: float     # 80 - 500 Hz
    high_freq_energy_ratio: float   # > 5000 Hz
    is_percussive: bool


class AcousticAnalyzer:
    @staticmethod
    def analyze_stem(stem_name: str, audio_data: np.ndarray, sample_rate: int = 44100) -> StemAcousticProfile:
        """Calcula o perfil acústico multidimensional da faixa."""
        if audio_data.ndim == 1:
            audio_data = np.column_stack([audio_data, audio_data])

        num_samples = audio_data.shape[0]
        if num_samples == 0:
            return StemAcousticProfile(
                stem_name=stem_name,
                rms_energy=0.0,
                peak_amplitude=0.0,
                crest_factor_db=0.0,
                spectral_centroid_hz=0.0,
                stereo_width_ratio=0.0,
                sub_bass_energy_ratio=0.0,
                low_mid_energy_ratio=0.0,
                high_freq_energy_ratio=0.0,
                is_percussive=False
            )

        # 1. Energia RMS e Pico
        peak = float(np.max(np.abs(audio_data)))
        rms = float(np.sqrt(np.mean(audio_data ** 2))) + 1e-9
        crest_factor = 20.0 * np.log10(max(peak / rms, 1.0))

        # 2. Largura estéreo (Mid / Side)
        mid = 0.5 * (audio_data[:, 0] + audio_data[:, 1])
        side = 0.5 * (audio_data[:, 0] - audio_data[:, 1])
        energy_mid = float(np.sum(mid ** 2)) + 1e-9
        energy_side = float(np.sum(side ** 2))
        stereo_width = energy_side / (energy_mid + energy_side)

        # 3. FFT e densidade energética por faixas
        # Usar um trecho central de até 10 segundos para cálculo ágil
        max_samples_fft = min(num_samples, sample_rate * 10)
        start_idx = (num_samples - max_samples_fft) // 2
        chunk_mid = mid[start_idx:start_idx + max_samples_fft]

        fft_vals = np.abs(np.fft.rfft(chunk_mid))
        freqs = np.fft.rfftfreq(len(chunk_mid), d=1.0 / sample_rate)
        total_fft_energy = float(np.sum(fft_vals ** 2)) + 1e-9

        # Faixas de frequência
        mask_sub = freqs < 80.0
        mask_low_mid = (freqs >= 80.0) & (freqs < 500.0)
        mask_high = freqs >= 5000.0

        sub_energy = float(np.sum(fft_vals[mask_sub] ** 2)) / total_fft_energy
        low_mid_energy = float(np.sum(fft_vals[mask_low_mid] ** 2)) / total_fft_energy
        high_energy = float(np.sum(fft_vals[mask_high] ** 2)) / total_fft_energy

        # Centróide espectral
        centroid = float(np.sum(freqs * fft_vals) / (np.sum(fft_vals) + 1e-9))

        # Heurística de transiente percussivo (fator de crista alto)
        is_percussive = crest_factor > 12.0 or "drum" in stem_name or "kick" in stem_name or "snare" in stem_name

        return StemAcousticProfile(
            stem_name=stem_name,
            rms_energy=rms,
            peak_amplitude=peak,
            crest_factor_db=crest_factor,
            spectral_centroid_hz=centroid,
            stereo_width_ratio=stereo_width,
            sub_bass_energy_ratio=sub_energy,
            low_mid_energy_ratio=low_mid_energy,
            high_freq_energy_ratio=high_energy,
            is_percussive=is_percussive
        )
