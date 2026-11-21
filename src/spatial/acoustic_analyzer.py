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
        data = np.asarray(audio_data)
        if data.ndim == 1:
            data = data[:, None]
        if not len(data):
            return StemAcousticProfile(stem_name, 0., 0., 0., 0., 0., 0., 0., 0., False)
        # RMS e largura em toda a faixa, memória temporária limitada.
        energy = side_energy = 0.
        peak = 0.
        for i in range(0, len(data), 65536):
            block = data[i:i+65536]
            energy += float(np.einsum("ij,ij->", block, block, dtype="d")) / block.shape[1]
            peak = max(peak, float(np.abs(block).max()))
            if block.shape[1] >= 2:
                side = .5*(block[:, 0]-block[:, 1])
                side_energy += float(np.dot(side, side))
        rms = np.sqrt(energy/len(data))
        crest_factor = 20*np.log10(max(1., peak/max(rms, 1e-12)))
        stereo_width = side_energy/max(energy, 1e-15)
        # Amostras distribuídas ao longo da música; potência L/R preserva conteúdo fora de fase.
        size = min(4096, len(data))
        window = np.hanning(size) if size > 2 else np.ones(size)
        spectrum = np.zeros(size//2+1)
        for i in np.linspace(0, len(data)-size, min(64, 1+len(data)//size), dtype=int):
            spectrum += (np.abs(np.fft.rfft(data[i:i+size]*window[:, None], axis=0))**2).mean(axis=1)
        freqs = np.fft.rfftfreq(size, 1/sample_rate)
        total = max(spectrum.sum(), 1e-15)
        sub_energy = spectrum[freqs < 80].sum()/total
        low_mid_energy = spectrum[(freqs >= 80) & (freqs < 500)].sum()/total
        high_energy = spectrum[freqs >= 5000].sum()/total
        magnitude = np.sqrt(spectrum)
        centroid = np.dot(freqs, magnitude)/max(magnitude.sum(), 1e-15)

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
