"""Master PCM 7.1.4 com automação por amostra, medição de voz e teto intersample."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .auto_director import SpatialPlacement
from .metering import MasterReport, MixMeter, integrated, true_peak
from .mix_engine import LEADS, MixPlan, prepare_sources
from .timeline_manager import SpatialTimelineManager
from .vbap_engine import VBAP714Engine
from ..separation.stem_engine import StemTrack


@dataclass
class RenderConfig:
    sample_rate: int = 48000
    target_lufs: float = -18.
    true_peak_limit_db: float = -1.
    apply_limiter: bool = True
    apply_lufs_norm: bool = True
    profile: str = "jbl"


class MasterRenderer714:
    def __init__(self, vbap_engine: VBAP714Engine | None = None):
        self.vbap = vbap_engine or VBAP714Engine()
        self.last_report: MasterReport | None = None

    def render_to_multichannel_714(self, stems: list[StemTrack], placements: dict[str, SpatialPlacement],
                                   config: RenderConfig | None = None,
                                   timeline_manager: SpatialTimelineManager | None = None) -> np.ndarray:
        cfg = config or RenderConfig()
        sources = prepare_sources(stems, cfg.sample_rate, cfg.profile)
        sections = timeline_manager.sections if timeline_manager else ()
        static = dict(placements)
        for s in stems:
            if not any((p.source_stem_name or k) == s.name for k, p in static.items()):
                static[s.name] = SpatialPlacement(s.name, s.initial_pan_x, s.initial_pan_y, s.initial_pan_z,
                                                  s.initial_spread, s.initial_lfe_send, 1.)
        plan = MixPlan.compile(sources, self.vbap, static, sections, cfg.sample_rate)
        mix = np.empty((plan.frames, 12), dtype="f")
        meter = MixMeter(cfg.sample_rate, any(s.name in LEADS for s in sources))
        for i in range(0, len(mix), meter.hop*4):
            block = mix[i:i+meter.hop*4]
            lead = np.empty_like(block) if meter.vocal else None
            plan.mix(i, block, lead)
            meter.add(block, lead)
        rows = meter.values()
        lufs = integrated(rows[:, 0])
        gain = self._target_gain(lufs, cfg.target_lufs) if cfg.apply_lufs_norm else 1.
        peak = true_peak(mix)
        if cfg.apply_limiter and peak:
            gain = min(gain, 10**(cfg.true_peak_limit_db/20)/peak)
        mix *= gain
        vocal, presence = meter.balance(rows)
        self.last_report = MasterReport(integrated(rows[:, 0]*gain**2),
                                        float(20*np.log10(peak*gain)) if peak else -np.inf,
                                        vocal, presence, float(20*np.log10(gain)))
        return mix

    @staticmethod
    def _target_gain(lufs: float, target: float) -> float:
        return 10**(np.clip(target-lufs, -36., 12.)/20) if np.isfinite(lufs) else 1.

    @staticmethod
    def _calculate_k_weighted_lufs(matrix_12ch: np.ndarray, sr: int = 48000) -> float:
        meter = MixMeter(sr, False)
        for i in range(0, len(matrix_12ch), 8*meter.hop):
            meter.add(matrix_12ch[i:i+8*meter.hop], None)
        return integrated(meter.values()[:, 0])

    def _apply_integrated_loudness_target(self, audio_matrix: np.ndarray, target_lufs: float = -18.,
                                          sr: int = 48000) -> np.ndarray:
        return audio_matrix*self._target_gain(self._calculate_k_weighted_lufs(audio_matrix, sr), target_lufs)

    @staticmethod
    def _apply_transparent_limiter(audio_matrix: np.ndarray, ceiling_db: float = -1.) -> np.ndarray:
        peak = true_peak(audio_matrix)
        return audio_matrix*min(1., 10**(ceiling_db/20)/peak) if peak else audio_matrix
