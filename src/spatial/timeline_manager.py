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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .auto_director import SpatialPlacement


@dataclass
class SpatialSection:
    id: str
    name: str                           # ex: "Intro", "Verso 1", "Refrão", "Ponte", "Final"
    start_time_s: float                 # Início do trecho em segundos
    end_time_s: float                   # Fim do trecho em segundos
    placements: Dict[str, SpatialPlacement]  # Cópia independente do posicionamento 3D dos stems
    color_hex: str = "#00E5FF"          # Cor temática do bloco visual


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
        self.total_duration_s = max(1.0, float(total_duration_s))
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
        self.total_duration_s = max(1.0, float(total_duration_s))
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
        new_d = max(1.0, float(new_duration_s))
        if not self.sections or abs(new_d - self.total_duration_s) < 0.1:
            self.total_duration_s = new_d
            return

        ratio = new_d / self.total_duration_s
        for sec in self.sections:
            sec.start_time_s = round(sec.start_time_s * ratio, 2)
            sec.end_time_s = round(sec.end_time_s * ratio, 2)

        # Assegurar que o último termine exatamente no total
        self.sections[0].start_time_s = 0.0
        self.sections[-1].end_time_s = new_d
        self.total_duration_s = new_d

    def split_section_at(self, split_time_s: float, new_name: Optional[str] = None) -> Optional[SpatialSection]:
        """
        Divide a seção que contém split_time_s em duas seções contíguas.
        A nova seção herda uma cópia do posicionamento para fácil ajuste pelo usuário.
        """
        t = max(0.5, min(self.total_duration_s - 0.5, float(split_time_s)))

        # Localizar a seção alvo
        target_idx = -1
        for idx, sec in enumerate(self.sections):
            if sec.start_time_s + 0.3 <= t <= sec.end_time_s - 0.3:
                target_idx = idx
                break

        if target_idx == -1:
            return None  # Ponto muito próximo da borda existente

        orig_sec = self.sections[target_idx]
        orig_end = orig_sec.end_time_s

        # Reduz a seção original
        orig_sec.end_time_s = round(t, 2)

        # Cria a nova seção
        num_sections = len(self.sections) + 1
        name = new_name or f"Trecho {num_sections}"
        new_id = f"sec_{uuid.uuid4().hex[:6]}"
        new_sec = SpatialSection(
            id=new_id,
            name=name,
            start_time_s=round(t, 2),
            end_time_s=orig_end,
            placements=copy.deepcopy(orig_sec.placements),
            color_hex=self._next_color()
        )

        self.sections.insert(target_idx + 1, new_sec)
        self.active_edit_section_id = new_id
        return new_sec

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
            if sec.start_time_s <= t <= sec.end_time_s:
                return sec
        return self.sections[-1]

    def get_interpolated_placements(
        self,
        time_s: float,
        crossfade_window_s: float = 1.0
    ) -> Dict[str, SpatialPlacement]:
        """
        Retorna as coordenadas e ganhos dos stems para o tempo time_s.
        Quando próximo à fronteira B entre duas seções, realiza uma interpolação suave (smoothstep)
        na janela [B - W/2, B + W/2], garantindo movimentação espacial orgânica, fluida e contínua
        sem saltos bruscos ou descontinuidades acústicas.
        """
        if len(self.sections) <= 1:
            return self.sections[0].placements

        t = max(0.0, min(self.total_duration_s, float(time_s)))
        half_w = max(0.05, crossfade_window_s / 2.0)

        # Verificar se está na janela de transição de alguma fronteira entre seções
        for idx in range(len(self.sections) - 1):
            sec_a = self.sections[idx]
            sec_b = self.sections[idx + 1]
            boundary = sec_b.start_time_s

            if (boundary - half_w) <= t <= (boundary + half_w):
                raw_alpha = (t - (boundary - half_w)) / (2.0 * half_w)
                raw_alpha = max(0.0, min(1.0, raw_alpha))
                # Curva Hermite / Smoothstep S-Curve: 3a^2 - 2a^3
                alpha = raw_alpha * raw_alpha * (3.0 - 2.0 * raw_alpha)
                return self._interpolate_placement_dicts(sec_a.placements, sec_b.placements, alpha)

        # Se não estiver em transição de fronteira, retorna a seção estacionária ativa
        return self.get_section_at_time(t).placements

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
                    is_muted=p_a.is_muted if alpha < 0.5 else p_b.is_muted,
                    is_solo=p_a.is_solo if alpha < 0.5 else p_b.is_solo,
                    is_stereo=p_a.is_stereo if alpha < 0.5 else p_b.is_stereo
                )
                result[k] = interp_plc
            elif p_a:
                result[k] = copy.copy(p_a)
            elif p_b:
                result[k] = copy.copy(p_b)

        return result
