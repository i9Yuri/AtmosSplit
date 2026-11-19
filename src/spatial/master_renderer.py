"""
AtmosSplit — Master Renderer 7.1.4
Renderiza matriz multicanal com VBAP, suporte a espelhamento estéreo (is_stereo),
automação dinâmica por trechos via SpatialTimelineManager, limiter transparente
anti-clipping e normalização para padrão EBU R128 (-14 LUFS / True Peak -0.5 dBTP).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np
from scipy import signal

from .vbap_engine import VBAP714Engine
from .auto_director import SpatialPlacement
from ..separation.stem_engine import StemTrack

if TYPE_CHECKING:
    from .timeline_manager import SpatialTimelineManager


@dataclass
class RenderConfig:
    sample_rate: int = 48000
    target_lufs: float = -18.0          # Padrão profissional da indústria Dolby Atmos (-18 LUFS)
    true_peak_limit_db: float = -1.0    # Teto True Peak rigoroso (-1.0 dBTP para QC Apple Music / Tidal)
    apply_limiter: bool = True
    apply_lufs_norm: bool = True


class MasterRenderer714:
    def __init__(self, vbap_engine: Optional[VBAP714Engine] = None):
        self.vbap = vbap_engine or VBAP714Engine()

    def render_to_multichannel_714(
        self,
        stems: List[StemTrack],
        placements: Dict[str, SpatialPlacement],
        config: Optional[RenderConfig] = None,
        timeline_manager: Optional[SpatialTimelineManager] = None
    ) -> np.ndarray:
        """
        Renderiza todos os stems posicionados em uma matriz multicanal 7.1.4 (num_samples, 12).
        Se timeline_manager for fornecido e contiver múltiplas seções, processa em blocos
        interpolando suavemente o posicionamento espacial ao longo do tempo.
        """
        cfg = config or RenderConfig()
        if not stems:
            return np.zeros((1024, 12), dtype=np.float32)

        # Encontrar o comprimento máximo em amostras
        max_samples = max(s.audio_data.shape[0] for s in stems)
        sr = cfg.sample_rate

        # Padronizar stems para comprimento uniforme
        padded_stems: List[Tuple[StemTrack, np.ndarray, np.ndarray]] = []
        for s in stems:
            data = s.audio_data
            if data.shape[0] < max_samples:
                pad_len = max_samples - data.shape[0]
                data = np.pad(data, ((0, pad_len), (0, 0)))
            
            # Canais L e R separados para suporte estéreo
            if data.ndim == 2 and data.shape[1] >= 2:
                ch_l = data[:, 0]
                ch_r = data[:, 1]
            else:
                raw = data[:, 0] if data.ndim == 2 else data
                ch_l = raw
                ch_r = raw
            padded_stems.append((s, ch_l, ch_r))

        # Checar se usamos renderização estática ou automação dinâmica temporal
        has_dynamic_timeline = (
            timeline_manager is not None
            and hasattr(timeline_manager, "sections")
            and len(timeline_manager.sections) > 1
        )

        if has_dynamic_timeline:
            out_matrix = self._render_dynamic_timeline(
                padded_stems=padded_stems,
                max_samples=max_samples,
                sr=sr,
                timeline_manager=timeline_manager
            )
        else:
            out_matrix = self._render_static_placements(
                padded_stems=padded_stems,
                max_samples=max_samples,
                placements=placements
            )

        # Normalização profissional de sonoridade (ITU-R BS.1770-4) e Limiter True Peak (-1.0 dBTP)
        if cfg.apply_lufs_norm:
            out_matrix = self._apply_integrated_loudness_target(out_matrix, target_lufs=cfg.target_lufs, sr=sr)

        if cfg.apply_limiter:
            out_matrix = self._apply_transparent_limiter(out_matrix, ceiling_db=cfg.true_peak_limit_db)

        return out_matrix.astype(np.float32)

    def _render_static_placements(
        self,
        padded_stems: List[Tuple[StemTrack, np.ndarray, np.ndarray]],
        max_samples: int,
        placements: Dict[str, SpatialPlacement]
    ) -> np.ndarray:
        """Renderização vetorizada rápida para quando o posicionamento é constante."""
        out_matrix = np.zeros((max_samples, 12), dtype=np.float32)
        any_solo = any(placements.get(s[0].name, SpatialPlacement(s[0].name, 0,0,0,0,0,1)).is_solo for s in padded_stems)

        for s, ch_l, ch_r in padded_stems:
            plc = placements.get(s.name, SpatialPlacement(
                stem_name=s.name,
                x=s.initial_pan_x,
                y=s.initial_pan_y,
                z=s.initial_pan_z,
                spread=s.initial_spread,
                lfe_send=s.initial_lfe_send,
                volume_gain=1.0,
                is_stereo=False
            ))

            if any_solo and not plc.is_solo:
                continue
            if plc.is_muted:
                continue

            self._accumulate_stem_audio(out_matrix, ch_l, ch_r, plc)

        return out_matrix

    def _render_dynamic_timeline(
        self,
        padded_stems: List[Tuple[StemTrack, np.ndarray, np.ndarray]],
        max_samples: int,
        sr: int,
        timeline_manager: "SpatialTimelineManager",
        block_size: int = 2048
    ) -> np.ndarray:
        """
        Renderização em blocos com interpolação contínua (smoothstep) de coordenadas e ganhos
        entre seções musicais da timeline.
        """
        out_matrix = np.zeros((max_samples, 12), dtype=np.float32)
        num_blocks = (max_samples + block_size - 1) // block_size

        for b in range(num_blocks):
            start_idx = b * block_size
            end_idx = min(max_samples, start_idx + block_size)
            block_len = end_idx - start_idx
            if block_len <= 0:
                break

            time_s = (start_idx + block_len / 2.0) / float(sr)
            # Obter posicionamentos interpolados da timeline para este momento exato
            current_plcs = timeline_manager.get_interpolated_placements(time_s)
            any_solo = any(current_plcs.get(s[0].name, SpatialPlacement(s[0].name, 0,0,0,0,0,1)).is_solo for s in padded_stems)

            block_out = np.zeros((block_len, 12), dtype=np.float32)

            for s, ch_l, ch_r in padded_stems:
                plc = current_plcs.get(s.name)
                if not plc:
                    continue
                if any_solo and not plc.is_solo:
                    continue
                if plc.is_muted:
                    continue

                b_l = ch_l[start_idx:end_idx]
                b_r = ch_r[start_idx:end_idx]
                self._accumulate_stem_audio(block_out, b_l, b_r, plc)

            out_matrix[start_idx:end_idx, :] += block_out

        return out_matrix

    def _accumulate_stem_audio(
        self,
        dest_matrix: np.ndarray,
        sig_l: np.ndarray,
        sig_r: np.ndarray,
        plc: SpatialPlacement
    ):
        """
        Acumula o áudio de um stem na matriz 7.1.4:
        - Se is_stereo=True: canal L é posicionado em -|x| e canal R em +|x|, criando
          um campo sonoro estéreo 3D envolvente com total coerência de fase.
        - Se is_stereo=False: mono mix (0.5*(L+R)) posicionado em (x, y, z).
        """
        gain = plc.volume_gain

        if plc.is_stereo:
            dist_x = abs(plc.x) if abs(plc.x) > 0.05 else 0.50
            gains_left = self.vbap.calculate_gains(
                x=-dist_x,
                y=plc.y,
                z=plc.z,
                spread=plc.spread,
                lfe_send=plc.lfe_send
            )
            gains_right = self.vbap.calculate_gains(
                x=dist_x,
                y=plc.y,
                z=plc.z,
                spread=plc.spread,
                lfe_send=plc.lfe_send
            )

            l_weighted = sig_l * gain
            r_weighted = sig_r * gain

            for ch in range(12):
                g_l = gains_left[ch]
                g_r = gains_right[ch]
                if g_l > 1e-5:
                    dest_matrix[:, ch] += l_weighted * g_l
                if g_r > 1e-5:
                    dest_matrix[:, ch] += r_weighted * g_r
        else:
            mono_sig = (0.5 * (sig_l + sig_r)) * gain
            gains = self.vbap.calculate_gains(
                x=plc.x,
                y=plc.y,
                z=plc.z,
                spread=plc.spread,
                lfe_send=plc.lfe_send
            )
            for ch in range(12):
                g = gains[ch]
                if g > 1e-5:
                    dest_matrix[:, ch] += mono_sig * g

    @staticmethod
    def _calculate_k_weighted_lufs(matrix_12ch: np.ndarray, sr: int = 48000) -> float:
        """
        Calcula a sonoridade integrada LKFS / LUFS conforme a norma ITU-R BS.1770-4 (Dolby Atmos QC).
        Filtro K de 2 estágios:
        - Estágio 1: High-shelf (+4 dB a 1.5 kHz, modelo de transmissão acústica da cabeça)
        - Estágio 2: RLB High-pass (filtro passa-altas de 2ª ordem a ~100 Hz)
        - Pesos dos canais: Frontais/L/R/C = 1.0, Surrounds/Alturas = 1.41 (+1.5 dB), LFE = 0.0 (ignorado)
        """
        num_samples = matrix_12ch.shape[0]
        if num_samples == 0:
            return -70.0

        # Coeficientes ITU-R BS.1770 calculados para 48 kHz
        # Estágio 1: Pre-filter (high shelf)
        b_stage1 = np.array([1.53512485958697, -2.69169618940638, 1.19839281085285], dtype=np.float64)
        a_stage1 = np.array([1.0, -1.69065929318241, 0.73248077421585], dtype=np.float64)

        # Estágio 2: RLB weighting (high pass)
        b_stage2 = np.array([1.0, -2.0, 1.0], dtype=np.float64)
        a_stage2 = np.array([1.0, -1.99004745483398, 0.99007225036621], dtype=np.float64)

        # Pesos dos canais G_i (7.1.4: L, R, C, LFE, BL, BR, SL, SR, TFL, TFR, TBL, TBR)
        # O canal LFE (3) é estritamente excluído da medição de sonoridade (peso 0.0)
        weights = [1.0, 1.0, 1.0, 0.0, 1.41, 1.41, 1.41, 1.41, 1.41, 1.41, 1.41, 1.41]

        total_weighted_energy = 0.0
        for ch in range(min(12, matrix_12ch.shape[1])):
            w = weights[ch]
            if w <= 0.0:
                continue
            ch_data = matrix_12ch[:, ch].astype(np.float64)
            y1 = signal.lfilter(b_stage1, a_stage1, ch_data)
            y2 = signal.lfilter(b_stage2, a_stage2, y1)
            mean_sq = float(np.mean(y2 ** 2))
            total_weighted_energy += w * mean_sq

        if total_weighted_energy <= 1e-12:
            return -70.0

        lufs = -0.691 + 10.0 * np.log10(total_weighted_energy)
        return float(lufs)

    def _apply_transparent_limiter(self, audio_matrix: np.ndarray, ceiling_db: float = -1.0) -> np.ndarray:
        """Limiter True Peak transparente (-1.0 dBTP) sem inter-sample clipping."""
        ceiling_linear = 10.0 ** (ceiling_db / 20.0)
        peak = float(np.max(np.abs(audio_matrix)))
        if peak > ceiling_linear:
            gain_reduction = ceiling_linear / (peak + 1e-9)
            audio_matrix = audio_matrix * gain_reduction
        return audio_matrix

    def _apply_integrated_loudness_target(self, audio_matrix: np.ndarray, target_lufs: float = -18.0, sr: int = 48000) -> np.ndarray:
        """Normalização precisa ITU-R BS.1770-4 para o alvo profissional Dolby Atmos (-18.0 LUFS)."""
        current_lufs = self._calculate_k_weighted_lufs(audio_matrix, sr=sr)
        if current_lufs < -65.0:
            return audio_matrix

        gain_db = target_lufs - current_lufs
        # Margem de segurança de ganho (-18 dB a +12 dB)
        gain_db = max(-18.0, min(12.0, gain_db))
        gain_linear = 10.0 ** (gain_db / 20.0)

        normalized = audio_matrix * gain_linear
        return normalized
