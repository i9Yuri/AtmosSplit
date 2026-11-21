"""
AtmosSplit — Spatial Timeline Manager (Automação Dinâmica por Trechos)
Permite dividir a música em múltiplos trechos/seções (ex: Intro, Verso, Refrão, Ponte, Final),
onde cada trecho possui seu próprio posicionamento espacial 3D independente para os instrumentos.
Fornece interpolação suave (crossfade linear/smoothstep de coordenadas) entre trechos,
garantindo transições musicais cinematográficas contínuas sem saltos bruscos ou estalos acústicos.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, replace
from math import isfinite
from typing import Dict, List, Optional


from .auto_director import SpatialPlacement
from .mix_engine import transition_half_width
from .micro_events import SpatialEvent


@dataclass
class SpatialSection:
    id: str
    name: str                           # ex: "Intro", "Verso 1", "Refrão", "Ponte", "Final"
    start_time_s: float                 # Início do trecho em segundos
    end_time_s: float                   # Fim do trecho em segundos
    placements: Dict[str, SpatialPlacement]  # Cópia independente do posicionamento 3D dos stems
    color_hex: str = "#00E5FF"          # Cor temática do bloco visual
    section_type: str = "manual"
    family: str = ""
    confidence: float = 0.
    description: str = ""
    tempo_bpm: float = 0.
    beats_per_bar: int = 0
    downbeats_s: tuple[float, ...] = ()
    micro_events: tuple[SpatialEvent, ...] = ()
    micro_enabled: bool = True


class SpatialTimelineManager:
    """
    Gerenciador de seções espaciais da faixa.
    Mantém uma lista encadeada e contígua de trechos cobrindo [0.0, total_duration_s].
    """
    DEFAULT_COLORS = [
        "#00E5FF",  # Ciano Neon
        "#48BB78",  # Verde Esmeralda
        "#ED8936",  # Laranja
        "#9F7AEA",  # Roxo Lavanda
        "#F56565",  # Coral / Vermelho suave
        "#38B2AC",  # Teal
        "#ECC94B",  # Amarelo Ouro
        "#4299E1",  # Azul Royal
    ]

    def __init__(self, total_duration_s: float = 180.0, initial_placements: Optional[Dict[str, SpatialPlacement]] = None):
        self.total_duration_s = max(1e-6, float(total_duration_s))
        self.sections: List[SpatialSection] = []
        self.active_edit_section_id: Optional[str] = None
        self._color_index = 0

        # Inicializa com uma seção cobrindo a música inteira
        init_plc = copy.deepcopy(initial_placements) if initial_placements else {}
        self.reset_to_single_section(self.total_duration_s, init_plc)

    def _next_color(self) -> str:
        color = self.DEFAULT_COLORS[self._color_index % len(self.DEFAULT_COLORS)]
        self._color_index += 1
        return color

    def reset_to_single_section(self, total_duration_s: float, initial_placements: Dict[str, SpatialPlacement]):
        """Reinicia a timeline com uma única seção cobrindo toda a faixa."""
        self.total_duration_s = max(1e-6, float(total_duration_s))
        sec_id = f"sec_{uuid.uuid4().hex[:6]}"
        self._color_index = 0
        first_section = SpatialSection(
            id=sec_id,
            name="Música Completa",
            start_time_s=0.0,
            end_time_s=self.total_duration_s,
            placements=copy.deepcopy(initial_placements),
            color_hex=self._next_color()
        )
        self.sections = [first_section]
        self.active_edit_section_id = sec_id

    def set_duration(self, new_duration_s: float):
        """Atualiza a duração total mantendo proporções das seções existentes."""
        new_d = max(1e-6, float(new_duration_s))
        ratio = new_d / self.total_duration_s
        for section in self.sections:
            section.start_time_s *= ratio
            section.end_time_s *= ratio
            section.downbeats_s = tuple(t * ratio for t in section.downbeats_s)
            section.tempo_bpm /= ratio
            section.micro_events = tuple(replace(e, start_s=e.start_s*ratio, end_s=e.end_s*ratio,
                                       attack_s=e.attack_s*ratio, release_s=e.release_s*ratio) for e in section.micro_events)
        self.sections[-1].end_time_s = new_d
        self.total_duration_s = new_d

    def split_section_at(self, split_time_s: float, new_name: Optional[str] = None) -> Optional[SpatialSection]:
        """Divide o arranjo sem perder a família MIR, a grade ou a precisão temporal."""
        t = float(split_time_s)
        for index, section in enumerate(self.sections):
            if section.start_time_s + .001 <= t <= section.end_time_s - .001:
                new = replace(
                    section, id=f"sec_{uuid.uuid4().hex[:12]}", name=new_name or f"Trecho {len(self.sections)+1}",
                    start_time_s=t, placements=copy.deepcopy(section.placements), color_hex=self._next_color(),
                    downbeats_s=tuple(bar for bar in section.downbeats_s if bar >= t))
                section.downbeats_s = tuple(bar for bar in section.downbeats_s if bar < t)
                new.micro_events = tuple(e for e in section.micro_events if e.start_s >= t)
                section.micro_events = tuple(e for e in section.micro_events if e.start_s < t)
                section.end_time_s = t
                self.sections.insert(index + 1, new)
                self.active_edit_section_id = new.id
                return new
        return None

    def adjust_boundary(self, boundary_idx: int, new_time_s: float) -> bool:
        """
        Ajusta a fronteira temporal entre self.sections[boundary_idx] e self.sections[boundary_idx + 1].
        Garante que nenhuma seção fique menor que 0.1s e preserva a contiguidade exata.
        """
        if boundary_idx < 0 or boundary_idx >= len(self.sections) - 1:
            return False

        sec_left = self.sections[boundary_idx]
        sec_right = self.sections[boundary_idx + 1]

        min_t = sec_left.start_time_s + 0.1
        max_t = sec_right.end_time_s - 0.1

        if min_t >= max_t:
            return False

        if not isfinite(new_time_s):
            return False
        clamped_t = max(min_t, min(max_t, float(new_time_s)))
        bars = sec_left.downbeats_s + sec_right.downbeats_s
        sec_left.downbeats_s = tuple(t for t in bars if t < clamped_t)
        sec_right.downbeats_s = tuple(t for t in bars if t >= clamped_t)
        events = sec_left.micro_events + sec_right.micro_events
        sec_left.micro_events = tuple(e for e in events if e.start_s < clamped_t)
        sec_right.micro_events = tuple(e for e in events if e.start_s >= clamped_t)
        sec_left.end_time_s = clamped_t
        sec_right.start_time_s = clamped_t
        return True

    def set_sections(self, new_sections: List[SpatialSection]):
        """Define uma nova lista completa de seções gerada pelo Atmos Maestro."""
        if not new_sections:
            return
        cursor = 0.
        identifiers = set()
        for section in new_sections:
            if (not isfinite(section.end_time_s) or section.start_time_s != cursor
                    or section.end_time_s <= cursor or section.id in identifiers):
                raise ValueError("As seções devem ser contíguas, ter duração positiva e IDs distintos.")
            identifiers.add(section.id)
            cursor = section.end_time_s
        self.sections = list(new_sections)
        self.active_edit_section_id = new_sections[0].id
        self.total_duration_s = new_sections[-1].end_time_s

    def remove_section(self, section_id: str) -> bool:
        """
        Remove uma seção fundindo seu tempo com a seção vizinha.
        Não permite remover se for a única seção restante.
        """
        if len(self.sections) <= 1:
            return False

        target_idx = next((i for i, s in enumerate(self.sections) if s.id == section_id), -1)
        if target_idx == -1:
            return False

        removed_sec = self.sections.pop(target_idx)

        # Se houver seção anterior, expande-a até o fim da removida
        if target_idx > 0:
            self.sections[target_idx - 1].end_time_s = removed_sec.end_time_s
            self.active_edit_section_id = self.sections[target_idx - 1].id
        else:
            # Era a primeira: expande a próxima para começar em 0.0
            self.sections[0].start_time_s = 0.0
            self.active_edit_section_id = self.sections[0].id

        neighbor = self.get_active_edit_section()
        neighbor.micro_events = tuple(sorted(neighbor.micro_events+removed_sec.micro_events, key=lambda e: e.start_s))
        neighbor.downbeats_s = tuple(sorted(set(neighbor.downbeats_s + removed_sec.downbeats_s)))
        return True

    def rename_section(self, section_id: str, new_name: str) -> bool:
        """Altera o nome descritivo da seção."""
        sec = self.get_section_by_id(section_id)
        if sec:
            sec.name = str(new_name).strip() or sec.name
            return True
        return False

    def get_section_by_id(self, section_id: str) -> Optional[SpatialSection]:
        return next((s for s in self.sections if s.id == section_id), None)

    def get_active_edit_section(self) -> SpatialSection:
        sec = self.get_section_by_id(self.active_edit_section_id or "")
        return sec or self.sections[0]

    def get_section_at_time(self, time_s: float) -> SpatialSection:
        """Retorna a seção ativa no tempo time_s."""
        t = max(0.0, min(self.total_duration_s, float(time_s)))
        for sec in self.sections:
            if sec.start_time_s <= t < sec.end_time_s:
                return sec
        return self.sections[-1]

    def get_interpolated_placements(self, time_s: float, crossfade_window_s: float | None = None) -> Dict[str, SpatialPlacement]:
        left, right, weight = self._scene_pair(time_s, crossfade_window_s)
        poses = (self._interpolate_placement_dicts(left.placements, right.placements, weight)
                 if right else left.placements)
        scenes = [(left, 1.-weight)] if right is None else [(left, 1.-weight), (right, weight)]
        def send_gain(name: str) -> float:
            gain = 0.
            for scene, fraction in scenes:
                source = scene.placements.get(name)
                if scene.micro_enabled and source and not source.is_muted:
                    if source.is_solo or not any(p.is_solo for p in scene.placements.values()):
                        gain += source.volume_gain*fraction
            return gain

        for section in self.sections:
            if not section.micro_enabled or section.start_time_s > time_s:
                continue
            for ev in section.micro_events:
                if not ev.audible or not ev.start_s <= time_s < ev.end_s:
                    continue
                strength = float(ev.envelope(time_s))*send_gain(ev.stem)
                if strength <= 0:
                    continue
                pose = ev.pose(float(ev.progress(time_s)))
                pose.volume_gain *= strength
                pose.lfe_send *= strength
                poses = {**poses, pose.stem_name: pose}
        return poses

    def _scene_pair(self, seconds: float, window: float | None) -> tuple[SpatialSection, SpatialSection | None, float]:
        for left, right in zip(self.sections, self.sections[1:]):
            half = transition_half_width(left, right, window)
            distance = seconds-right.start_time_s
            if half > 0 and -half <= distance <= half:
                t = (distance+half)/(2*half)
                return left, right, t*t*(3-2*t)
        return self.get_section_at_time(seconds), None, 0.

    @staticmethod
    def _interpolate_placement_dicts(
        dict_a: Dict[str, SpatialPlacement],
        dict_b: Dict[str, SpatialPlacement],
        alpha: float
    ) -> Dict[str, SpatialPlacement]:
        """Interpola linearmente as coordenadas X, Y, Z, volume e spread entre dois estados."""
        alpha = max(0.0, min(1.0, float(alpha)))
        inv_alpha = 1.0 - alpha

        result: Dict[str, SpatialPlacement] = {}
        all_keys = set(dict_a.keys()).union(dict_b.keys())

        for k in all_keys:
            p_a = dict_a.get(k)
            p_b = dict_b.get(k)

            if p_a and p_b:
                interp_plc = SpatialPlacement(
                    stem_name=k,
                    x=inv_alpha * p_a.x + alpha * p_b.x,
                    y=inv_alpha * p_a.y + alpha * p_b.y,
                    z=inv_alpha * p_a.z + alpha * p_b.z,
                    spread=inv_alpha * p_a.spread + alpha * p_b.spread,
                    lfe_send=inv_alpha * p_a.lfe_send + alpha * p_b.lfe_send,
                    volume_gain=inv_alpha * p_a.volume_gain + alpha * p_b.volume_gain,
                    is_muted=False if ((not p_a.is_muted or not p_b.is_muted) and (p_a.volume_gain > 0 or p_b.volume_gain > 0)) else (p_a.is_muted if alpha < 0.5 else p_b.is_muted),
                    is_solo=p_a.is_solo if alpha < 0.5 else p_b.is_solo,
                    is_stereo=p_a.is_stereo if alpha < 0.5 else p_b.is_stereo,
                    source_stem_name=p_a.source_stem_name or p_b.source_stem_name
                )
                result[k] = interp_plc
            elif p_a:
                result[k] = copy.copy(p_a)
                result[k].volume_gain *= inv_alpha
            elif p_b:
                result[k] = copy.copy(p_b)
                result[k].volume_gain *= alpha

        return result
