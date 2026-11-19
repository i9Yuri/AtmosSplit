"""
AtmosSplit — Motor de Pré-escuta Binaural HRTF para Fones de Ouvido
Simula espacialização 7.1.4 em fones estéreo (Havit H2002D / QCY N70)
aplicando atraso interaural (ITD), diferença de nível (IID) e filtros de elevação.
Possui suporte a continuidade de estado de filtros (zi) para reprodução contínua
sem micro-estalos entre blocos de áudio.
"""

from __future__ import annotations

import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from scipy import signal

from .vbap_engine import SPEAKER_COORDINATES_714, SpeakerPosition714


class BinauralHRTFEngine:
    def __init__(self, sample_rate: int = 48000, head_radius_m: float = 0.0875):
        self.sample_rate = sample_rate
        self.c = 343.0  # Velocidade do som no ar em m/s
        self.head_radius = head_radius_m
        self.channel_profiles: List[Dict[str, Any]] = []
        self._filter_states: Dict[str, Any] = {}
        self._init_speaker_filters()

    def _init_speaker_filters(self):
        """Pré-calcula atrasos em amostras e filtros IID para cada caixa 7.1.4."""
        self.channel_profiles = []
        self._filter_states.clear()

        for idx, spk in enumerate(SPEAKER_COORDINATES_714):
            if spk.is_lfe:
                # LFE: apenas passa-baixa mono (< 120 Hz)
                sos_lfe = signal.butter(4, 120.0, btype="lowpass", fs=self.sample_rate, output="sos")
                zi_lfe = signal.sosfilt_zi(sos_lfe)
                self.channel_profiles.append({
                    "is_lfe": True,
                    "sos_lfe": sos_lfe,
                    "ch_index": idx
                })
                self._filter_states[f"lfe_{idx}"] = np.zeros_like(zi_lfe)
                continue

            # Calcular Azimute (theta) e Elevação (phi) esféricos
            # x: Esquerda (-1) a Direita (+1)
            # y: Trás (-1) a Frente (+1)
            # z: Chão (0) a Teto (+1)
            theta_rad = math.atan2(spk.x, spk.y)   # Azimute: 0 = Frente, pi/2 = Direita, -pi/2 = Esquerda
            phi_rad = math.atan2(spk.z, math.sqrt(spk.x**2 + spk.y**2)) # Elevação

            # 1. Atraso Interaural (ITD) - Modelo Woodworth
            itd_s = (self.head_radius / self.c) * (math.sin(abs(theta_rad)) + abs(theta_rad))
            itd_samples = int(round(itd_s * self.sample_rate))

            # 2. Diferença de Nível (IID) - Atenuação de cabeça
            pan_lr = (math.sin(theta_rad) + 1.0) / 2.0  # 0.0 (Esq) a 1.0 (Dir)
            gain_l = math.cos(pan_lr * math.pi / 2.0)
            gain_r = math.sin(pan_lr * math.pi / 2.0)

            # 3. Filtro de Elevação de Teto (Drivers superiores de teto)
            sos_elevation = None
            if spk.z > 0.5:
                # Som de teto: boost de brilho aéreo em ~9 kHz
                sos_elevation = signal.butter(2, [7000.0, 11000.0], btype="bandpass", fs=self.sample_rate, output="sos")
                zi_elev = signal.sosfilt_zi(sos_elevation)
                self._filter_states[f"elev_{idx}"] = np.zeros_like(zi_elev)

            self.channel_profiles.append({
                "is_lfe": False,
                "ch_index": idx,
                "delay_l": itd_samples if theta_rad > 0 else 0,
                "delay_r": itd_samples if theta_rad < 0 else 0,
                "gain_l": gain_l,
                "gain_r": gain_r,
                "sos_elevation": sos_elevation,
                "z": spk.z
            })

    def reset_states(self):
        """Zera os estados dos filtros para transição suave em pausas e seeks."""
        for k in self._filter_states:
            self._filter_states[k].fill(0.0)

    def process_714_to_binaural(self, multichannel_714: np.ndarray, keep_state: bool = True) -> np.ndarray:
        """
        Converte matriz (N, 12) em áudio estéreo binaural (N, 2) pronto para headset.
        Usa keep_state=True para encadeamento contínuo sem estalos acústicos entre blocos.
        """
        num_samples = multichannel_714.shape[0]
        stereo_out = np.zeros((num_samples, 2), dtype=np.float32)

        for ch_idx in range(min(12, multichannel_714.shape[1])):
            ch_data = multichannel_714[:, ch_idx]
            prof = self.channel_profiles[ch_idx]

            if prof["is_lfe"]:
                # LFE Subwoofer: distribuído igualmente em ambos os canais com filtro contínuo
                state_key = f"lfe_{ch_idx}"
                if keep_state and state_key in self._filter_states:
                    filtered_lfe, self._filter_states[state_key] = signal.sosfilt(
                        prof["sos_lfe"], ch_data, zi=self._filter_states[state_key]
                    )
                else:
                    filtered_lfe = signal.sosfilt(prof["sos_lfe"], ch_data)
                
                scaled_lfe = filtered_lfe * 0.7
                stereo_out[:, 0] += scaled_lfe
                stereo_out[:, 1] += scaled_lfe
                continue

            if np.max(np.abs(ch_data)) < 1e-6:
                continue

            # Processamento espacial
            gain_l = prof["gain_l"]
            gain_r = prof["gain_r"]
            delay_l = prof["delay_l"]
            delay_r = prof["delay_r"]

            # Aplicar filtro de elevação se for canal de teto
            sig_processed = ch_data
            if prof.get("sos_elevation") is not None:
                state_key = f"elev_{ch_idx}"
                if keep_state and state_key in self._filter_states:
                    elevation_boost, self._filter_states[state_key] = signal.sosfilt(
                        prof["sos_elevation"], ch_data, zi=self._filter_states[state_key]
                    )
                else:
                    elevation_boost = signal.sosfilt(prof["sos_elevation"], ch_data)
                sig_processed = ch_data + elevation_boost * 0.4

            # Canal Esquerdo com ITD
            if delay_l > 0 and delay_l < num_samples:
                stereo_out[delay_l:, 0] += sig_processed[:-delay_l] * gain_l
            else:
                stereo_out[:, 0] += sig_processed * gain_l

            # Canal Direito com ITD
            if delay_r > 0 and delay_r < num_samples:
                stereo_out[delay_r:, 1] += sig_processed[:-delay_r] * gain_r
            else:
                stereo_out[:, 1] += sig_processed * gain_r

        # Normalização suave anti-clipping
        peak = float(np.max(np.abs(stereo_out)))
        if peak > 0.95:
            stereo_out = (stereo_out / peak) * 0.95

        return stereo_out
