"""Conecta a análise estrutural à automação editável da sala."""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import replace

import numpy as np

from .acoustic_analyzer import AcousticAnalyzer, StemAcousticProfile
from .auto_director import AutoAtmosDirector, DirectorPreset
from .micro_events import detect_micro_events
from .music_structure import analyze_structure
from .timeline_manager import SpatialSection
from ..separation.stem_engine import StemTrack


class SongStructureIntelligence:
    LABELS = {
        "intro": ("Intro", "#A8BDDE"), "verse": ("Verso", "#7BC5B4"),
        "buildup": ("Pré-refrão / Build-up", "#E7BB79"), "chorus": ("Refrão / Drop", "#71DCCA"),
        "bridge": ("Ponte", "#ADABD8"), "breakdown": ("Breakdown", "#CEB3D7"),
        "solo": ("Solo instrumental", "#B2C5E9"), "climax": ("Refrão final", "#F0AC88"),
        "outro": ("Outro", "#CBB78D"), "uniform": ("Trecho contínuo", "#9FAEB9"),
    }

    @classmethod
    def analyze_and_arrange(cls, stems: list[StemTrack], total_duration_s: float,
                            preset: DirectorPreset = DirectorPreset.BALANCED, intensity: float = .7,
                            *, mix_audio: np.ndarray | None = None, mix_sample_rate: int | None = None
                            ) -> list[SpatialSection]:
        parts, pulse = analyze_structure(stems, total_duration_s, mix_audio, mix_sample_rate)
        counts: Counter = Counter()
        sections = []
        for part in parts:
            label, color = cls.LABELS[part.kind]
            counts[part.kind] += 1
            name = f"{label} {counts[part.kind]}" if part.kind in ("verse", "chorus") else label
            bars = pulse.bars[(pulse.bars >= part.start) & (pulse.bars < part.end)]
            sections.append(SpatialSection(
                uuid.uuid4().hex[:12], name, part.start, part.end, {}, color,
                section_type=part.kind, family=part.family, confidence=part.confidence,
                description=part.description, tempo_bpm=pulse.bpm, beats_per_bar=pulse.meter,
                downbeats_s=tuple(map(float, bars))))
        detect_micro_events(stems, sections, intensity)
        return cls.redirect(sections, stems, preset, intensity)

    @staticmethod
    def redirect(sections: list[SpatialSection], stems: list[StemTrack], preset: DirectorPreset,
                 intensity: float, profiles: dict[str, StemAcousticProfile] | None = None
                 ) -> list[SpatialSection]:
        if profiles is None:
            profiles = {s.name: AcousticAnalyzer.analyze_stem(s.name, s.audio_data, s.sample_rate)
                        for s in stems}
        base = AutoAtmosDirector.generate_placements(profiles, preset)
        return [replace(s, placements=AutoAtmosDirector.direct_section(base, s.section_type, intensity),
                        micro_events=tuple(replace(e, intensity=float(np.clip(intensity, 0, 1)))
                                           for e in s.micro_events)) for s in sections]
