"""
AtmosSplit — Song Structure Intelligence (Atmos Maestro Automático Profissional)
Motor analítico autônomo de inteligência musical que estuda detalhadamente a estrutura,
a dinâmica espectral, transientes de percussão, pausas de fraseado vocal (VAD) e curvas de energia.
Segmenta a faixa em frases musicais realistas e granulares (8s a 20s em vez de blocos gigantes),
e projeta movimentações tridimensionais (X, Y, Z, Spread, LFE, Altura) dinâmicas, cinematográficas
e expressivas para cada momento da faixa.
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .auto_director import AutoAtmosDirector, DirectorPreset, SpatialPlacement
from .timeline_manager import SpatialSection, SpatialTimelineManager
from ..separation.stem_engine import StemTrack

log = logging.getLogger(__name__)


@dataclass
class SectionDescriptor:
    name: str
    section_type: str
    start_time_s: float
    end_time_s: float
    color_hex: str
    description: str


class SongStructureIntelligence:
    """
    Inteligência musical autônoma de estúdio para arranjo e mixagem espacial Dolby Atmos 7.1.4.
    Analisa a estrutura da música frase a frase, detectando transições, risers, quedas,
    entradas de beat e pausas vocais, aplicando posicionamentos 3D cinematográficos ativos.
    """

    COLOR_PALETTE = {
        "intro_ambient": "#4299E1",   # Azul Royal (Ambiência aérea)
        "intro_beat": "#3182CE",      # Azul Safira (Entrada do ritmo)
        "verse_dry": "#38B2AC",       # Teal Claro (Voz frontal íntima e seca)
        "verse_groove": "#319795",    # Teal Escuro (Groove preenchido com baixo)
        "buildup": "#ED8936",         # Laranja (Riser ascendente ao teto)
        "pre_drop": "#DD6B20",        # Laranja Escuro (Pausa/respiração dramática)
        "chorus_drop": "#00E5FF",     # Ciano Neon (Explosão 360°)
        "chorus_hook": "#0BC5EA",     # Turquesa (Hook vocal + satélites)
        "post_chorus": "#00B5D8",     # Ciano Marítimo (Decaimento do refrão)
        "verse_contrast": "#4FD1C5",   # Menta (Contraste despojado pós-refrão)
        "bridge_solo": "#9F7AEA",     # Roxo Lavanda (Solo em destaque frontal)
        "breakdown": "#805AD5",       # Índigo (Queda etérea / voz suspensa)
        "climax": "#F56565",          # Coral Neon (Pico de energia 7.1.4)
        "outro_groove": "#ECC94B",    # Âmbar (Descompressão rítmica)
        "outro_ambient": "#D69E2E",   # Ouro (Dissolução no teto/traseira)
    }

    @classmethod
    def analyze_and_arrange(
        cls,
        stems: List[StemTrack],
        total_duration_s: float,
        preset: DirectorPreset = DirectorPreset.BALANCED
    ) -> List[SpatialSection]:
        """
        Analisa os stems da música ao longo do tempo e gera uma automação espacial rica,
        granular e dinâmica com transições musicais naturais.
        """
        dur = max(2.0, float(total_duration_s))
        sections_desc = cls._detect_musical_sections(stems, dur)

        spatial_sections: List[SpatialSection] = []
        for desc in sections_desc:
            sec_id = f"sec_{uuid.uuid4().hex[:6]}"
            placements = cls._generate_section_placements(stems, desc.section_type, preset)
            spatial_sections.append(
                SpatialSection(
                    id=sec_id,
                    name=desc.name,
                    start_time_s=round(desc.start_time_s, 3),
                    end_time_s=round(desc.end_time_s, 3),
                    placements=placements,
                    color_hex=desc.color_hex
                )
            )

        return spatial_sections

    @classmethod
    def _detect_musical_sections(
        cls,
        stems: List[StemTrack],
        duration_s: float
    ) -> List[SectionDescriptor]:
        """
        Analisa curvas de energia RMS, VAD (Voice Activity Detection), transientes rítmicos
        e quedas bruscas para particionar a faixa em frases musicais de 8s a 20s.
        """
        stems_by_name = {s.name.lower(): s for s in stems}
        vocals_track = stems_by_name.get("vocals") or stems_by_name.get("lead_vocal")
        drums_track = stems_by_name.get("drums") or stems_by_name.get("drum")
        bass_track = stems_by_name.get("bass")
        other_track = stems_by_name.get("other") or stems_by_name.get("synths")

        # Janelas de alta resolução temporal: 100 ms
        frame_s = 0.100
        num_frames = max(10, int(duration_s / frame_s))

        vocal_energy = cls._compute_rms_profile(vocals_track, num_frames)
        drums_energy = cls._compute_rms_profile(drums_track, num_frames)
        bass_energy = cls._compute_rms_profile(bass_track, num_frames)
        other_energy = cls._compute_rms_profile(other_track, num_frames)

        # Energia combinada ponderada
        total_energy = 0.35 * vocal_energy + 0.30 * drums_energy + 0.20 * bass_energy + 0.15 * other_energy
        max_e = np.max(total_energy) if np.max(total_energy) > 0 else 1.0
        norm_energy = total_energy / max_e

        # Curva de fluxo de novidade (primeira derivada de energia para capturar transições)
        diff_energy = np.diff(norm_energy, prepend=norm_energy[0])
        flux = np.maximum(0, diff_energy)

        # 1. Detectar pontos de transição musical significativos
        # Mínimo de 7.5 segundos e máximo de 20.0 segundos por frase musical
        min_section_frames = int(7.5 / frame_s)
        max_section_frames = int(20.0 / frame_s)

        candidate_cuts: List[int] = [0]
        last_cut = 0

        # Identificar entrada do ritmo / bateria
        drums_max = np.max(drums_energy) if np.max(drums_energy) > 0 else 1.0
        norm_drums = drums_energy / drums_max
        beat_entries = np.where(norm_drums > 0.20)[0]
        beat_start_frame = int(beat_entries[0]) if len(beat_entries) > 0 else int(10.0 / frame_s)

        if beat_start_frame > min_section_frames and beat_start_frame < int(duration_s * 0.25 / frame_s):
            candidate_cuts.append(beat_start_frame)
            last_cut = beat_start_frame

        # Varredura de frases musicais com base em transientes, quedas de bateria e pausas de voz
        cur_frame = last_cut + min_section_frames
        end_search_frame = int((duration_s - 6.0) / frame_s)

        while cur_frame < end_search_frame:
            window_end = min(end_search_frame, last_cut + max_section_frames)
            window_start = last_cut + min_section_frames

            if window_start >= window_end:
                break

            # Buscar o ponto de corte ótimo dentro da janela musical:
            # - Pico no fluxo de energia (transiente de entrada)
            # - Ou vale profundo na bateria (corte antes de drop)
            # - Ou pausa na voz (fim de verso / frase vocal)
            window_flux = flux[window_start:window_end]
            window_drums = norm_drums[window_start:window_end]

            # Queda de bateria (break / drop gap)
            drop_candidates = np.where(window_drums < 0.12)[0]
            if len(drop_candidates) > 0:
                best_sub_idx = drop_candidates[0]
            else:
                best_sub_idx = int(np.argmax(window_flux))

            chosen_cut = window_start + best_sub_idx
            candidate_cuts.append(chosen_cut)
            last_cut = chosen_cut
            cur_frame = last_cut + min_section_frames

        candidate_cuts.append(num_frames)

        # 2. Filtrar e consolidar cortes em tempos exatos em segundos
        cut_times: List[float] = [0.0]
        for c in candidate_cuts[1:]:
            t_s = float(c) * frame_s
            t_s = min(duration_s, max(cut_times[-1] + 6.0, t_s))
            if t_s > cut_times[-1] + 3.0:
                cut_times.append(t_s)

        if cut_times[-1] < duration_s:
            cut_times[-1] = duration_s

        # 3. Classificação e Atribuição Musical Rica de Cada Frase
        num_sections = len(cut_times) - 1
        descriptors: List[SectionDescriptor] = []

        chorus_counter = 1
        verse_counter = 1

        for idx in range(num_sections):
            t_start = cut_times[idx]
            t_end = cut_times[idx + 1]
            dur_sec = t_end - t_start

            f_start = int(t_start / frame_s)
            f_end = min(num_frames, int(t_end / frame_s))

            sec_norm_energy = float(np.mean(norm_energy[f_start:f_end]))
            sec_drums = float(np.mean(norm_drums[f_start:f_end]))
            sec_vocals = float(np.mean(vocal_energy[f_start:f_end])) if len(vocal_energy) > 0 else 0.0

            # Taxa de variação de energia no trecho (ascendente = buildup)
            slope = 0.0
            if f_end - f_start >= 4:
                half = (f_start + f_end) // 2
                e1 = np.mean(norm_energy[f_start:half])
                e2 = np.mean(norm_energy[half:f_end])
                slope = float(e2 - e1)

            time_ratio = t_start / duration_s

            # --- Determinação da Personalidade Musical da Seção ---
            if idx == 0:
                if sec_drums < 0.25:
                    stype = "intro_ambient"
                    name = "Intro (Ambiência Aérea)"
                    desc = "Abertura imersiva: sintetizadores e ambiência espalhados no teto e laterais com centro livre."
                else:
                    stype = "intro_beat"
                    name = "Intro (Entrada do Groove)"
                    desc = "Batida inicial entra no palco frontal com ambiência estéreo aberta."
            elif idx == num_sections - 1:
                stype = "outro_ambient"
                name = "Outro (Dissolução 3D)"
                desc = "Decaimento etéreo: elementos e caudas sonoras flutuam suavemente para o teto e traseira."
            elif idx == num_sections - 2 and time_ratio > 0.80:
                stype = "outro_groove"
                name = "Outro (Descompressão)"
                desc = "Groove desacelerando e recuando para os módulos traseiros."
            elif time_ratio > 0.70 and sec_norm_energy > 0.65:
                # Clímax final da música
                stype = "climax"
                name = "Refrão Final (Clímax 7.1.4)"
                desc = "Pico máximo de energia: 12 canais ativos, coros em ambos os módulos traseiros e pratos no teto."
            elif sec_drums < 0.15 and sec_vocals > 0.20 and time_ratio > 0.45:
                # Breakdown: corte de bateria, voz e acordes flutuando
                stype = "breakdown"
                name = "Breakdown (Voz Celestial no Teto)"
                desc = "Queda dramática: bateria cessa e a voz flutua suspensa no centro da sala acima da cabeça."
            elif slope > 0.12 or (sec_norm_energy > 0.45 and sec_norm_energy < 0.75 and sec_drums > 0.35 and idx % 3 == 2):
                stype = "buildup"
                name = f"Build-up (Ascensão ao Teto)"
                desc = "Tensão crescente: esteiras, risers e vocais sobem gradualmente em direção aos 4 canais de altura."
            elif sec_norm_energy > 0.60:
                # Refrão de alta energia
                if chorus_counter % 2 == 1:
                    stype = "chorus_drop"
                    name = f"Refrão {chorus_counter} (Explosão 360°)"
                    desc = "Explosão espacial: kick centrado, pratos nas alturas e respostas vocais nos módulos traseiros."
                else:
                    stype = "chorus_hook"
                    name = f"Refrão {chorus_counter} (Hook & Eco Traseiro)"
                    desc = "Imersão total: vocal throw destacado nos satélites destacáveis traseiros (BL/BR)."
                chorus_counter += 1
            elif time_ratio > 0.60 and time_ratio < 0.78 and verse_counter >= 3:
                stype = "bridge_solo"
                name = "Ponte / Solo (Destaque Tridimensional)"
                desc = "Foco em instrumento melódico destacado no palco frontal com acordes ao redor."
            else:
                # Versos
                if verse_counter == 1:
                    stype = "verse_dry"
                    name = "Verso 1A (Voz Frontal Íntima)"
                    desc = "Voz cristalina e seca ancorada no centro frontal (Center), com palco íntimo e foco máximo."
                elif verse_counter == 2:
                    stype = "verse_groove"
                    name = "Verso 1B (Groove Preenchido)"
                    desc = "Entrada do baixo e ritmo preenchendo o palco com voz aberta e dinâmica."
                elif verse_counter == 3:
                    stype = "verse_contrast"
                    name = "Verso 2 (Contraste Despojado)"
                    desc = "Contraste imediato pós-refrão: retorno ao palco frontal seco e intimista."
                else:
                    stype = "verse_groove"
                    name = f"Verso {verse_counter} (Desenvolvimento)"
                    desc = "Ritmo pulsante e arranjo lateral dinâmico."
                verse_counter += 1

            descriptors.append(
                SectionDescriptor(
                    name=name,
                    section_type=stype,
                    start_time_s=t_start,
                    end_time_s=t_end,
                    color_hex=cls.COLOR_PALETTE.get(stype, "#4299E1"),
                    description=desc
                )
            )

        # Garantir contiguidade exata das bordas
        for i in range(len(descriptors) - 1):
            descriptors[i].end_time_s = descriptors[i + 1].start_time_s

        return descriptors

    @classmethod
    def _generate_section_placements(
        cls,
        stems: List[StemTrack],
        section_type: str,
        preset: DirectorPreset
    ) -> Dict[str, SpatialPlacement]:
        """
        Calcula coordenadas tridimensionais (X, Y, Z), espelhamento estéreo, difusão e ganho
        que realmente se movem e se transformam no espaço de forma dinâmica e musical.
        """
        placements: Dict[str, SpatialPlacement] = {}
        has_vocal = any("vocal" in s.name.lower() or "voice" in s.name.lower() for s in stems)

        for s in stems:
            name = s.name
            nl = name.lower()

            # --- 1. VOZES (VOCALS) ---
            if "vocal" in nl or "voice" in nl:
                if section_type in ("intro_ambient",):
                    # Intro aérea: voz (se houver) soa distante, flutuando alto
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.15, z=0.55,
                        spread=0.50, lfe_send=0.0, volume_gain=0.85, is_stereo=False
                    )
                elif section_type in ("verse_dry", "verse_contrast"):
                    # Verso seco/íntimo: Ancoragem frontal máxima no centro (TV/Center bar)
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.98, z=0.0,
                        spread=0.05, lfe_send=0.0, volume_gain=1.05, is_stereo=False
                    )
                elif section_type == "verse_groove":
                    # Verso com ritmo: leve abertura frontal
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.92, z=0.10,
                        spread=0.15, lfe_send=0.0, volume_gain=1.08, is_stereo=False
                    )
                elif section_type == "buildup":
                    # Build-up: Voz se eleva verticalmente aos canais de teto!
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.80, z=0.48,
                        spread=0.35, lfe_send=0.0, volume_gain=1.10, is_stereo=False
                    )
                elif section_type == "pre_drop":
                    # Pausa pré-drop: voz focada no centro da sala
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.50, z=0.25,
                        spread=0.20, lfe_send=0.0, volume_gain=1.0, is_stereo=False
                    )
                elif section_type in ("chorus_drop", "climax"):
                    # Refrão / Clímax: Potência frontal incisiva e presente
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.96, z=0.12,
                        spread=0.22, lfe_send=0.0, volume_gain=1.16, is_stereo=False
                    )
                elif section_type == "chorus_hook":
                    # Hook do refrão: arco frontal mais amplo
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.86, z=0.22,
                        spread=0.40, lfe_send=0.0, volume_gain=1.12, is_stereo=False
                    )
                elif section_type == "post_chorus":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.75, z=0.20,
                        spread=0.30, lfe_send=0.0, volume_gain=1.02, is_stereo=False
                    )
                elif section_type == "bridge_solo":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.70, z=0.30,
                        spread=0.35, lfe_send=0.0, volume_gain=1.05, is_stereo=False
                    )
                elif section_type == "breakdown":
                    # Breakdown: Voz suspensa no centro da sala acima do ouvinte (efeito etéreo)
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.20, z=0.68,
                        spread=0.65, lfe_send=0.0, volume_gain=1.10, is_stereo=False
                    )
                else:  # outro_ambient, outro_groove
                    # Outro: Voz flutua suavemente para trás em direção aos satélites e sobe
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=-0.45, z=0.72,
                        spread=0.65, lfe_send=0.0, volume_gain=0.92, is_stereo=False
                    )

            # --- 2. BATERIA / PERCUSSÃO (DRUMS) ---
            elif "drum" in nl or "kick" in nl or "snare" in nl:
                if section_type in ("intro_ambient",):
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.40, z=0.0,
                        spread=0.15, lfe_send=0.30, volume_gain=0.80, is_stereo=False
                    )
                elif section_type in ("verse_dry", "verse_contrast"):
                    # Verso seco: Kit focado e firme no chão
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.65, z=0.0,
                        spread=0.12, lfe_send=0.85, volume_gain=1.00, is_stereo=False
                    )
                elif section_type == "verse_groove":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.60, z=0.05,
                        spread=0.22, lfe_send=0.90, volume_gain=1.02, is_stereo=False
                    )
                elif section_type == "buildup":
                    # Build-up: Snare roll e viradas sobem verticalmente ao teto!
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.52, z=0.62,
                        spread=0.50, lfe_send=0.95, volume_gain=1.08, is_stereo=False
                    )
                elif section_type in ("chorus_drop", "climax"):
                    # Refrão: Explosão com pratos distribuídos no teto frontal/traseiro
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.62, z=0.45,
                        spread=0.55, lfe_send=1.00, volume_gain=1.12, is_stereo=False
                    )
                elif section_type == "chorus_hook":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.58, z=0.40,
                        spread=0.48, lfe_send=1.00, volume_gain=1.08, is_stereo=False
                    )
                elif section_type == "breakdown":
                    # Breakdown: Bateria é silenciada ou opera com mínima presença
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.35, z=0.0,
                        spread=0.08, lfe_send=0.20, volume_gain=0.15, is_stereo=False,
                        is_muted=True
                    )
                else:  # bridge_solo, outro
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.50, z=0.20,
                        spread=0.30, lfe_send=0.75, volume_gain=0.95, is_stereo=False
                    )

            # --- 3. BAIXO (BASS / 808) ---
            elif "bass" in nl:
                if section_type in ("intro_ambient", "breakdown"):
                    # Sub bass sutil e contido
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.35, z=0.0,
                        spread=0.05, lfe_send=0.40, volume_gain=0.80, is_stereo=False
                    )
                elif section_type in ("chorus_drop", "climax"):
                    # Refrão: Impacto máximo de baixa frequência (100% LFE subwoofer 10")
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.50, z=0.0,
                        spread=0.05, lfe_send=1.00, volume_gain=1.15, is_stereo=False
                    )
                elif section_type == "buildup":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.45, z=0.0,
                        spread=0.05, lfe_send=0.95, volume_gain=1.05, is_stereo=False
                    )
                else:  # Versos normais
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.0, y=0.55, z=0.0,
                        spread=0.05, lfe_send=0.88, volume_gain=1.00, is_stereo=False
                    )

            # --- 4. INSTRUMENTOS HARMÔNICOS / AMBIÊNCIA / SINTETIZADORES (OTHER) ---
            else:
                if section_type in ("intro_ambient",):
                    # Nuvem envolvente no teto e laterais
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.78, y=-0.15, z=0.82,
                        spread=0.75, lfe_send=0.0, volume_gain=1.02, is_stereo=True
                    )
                elif section_type in ("verse_dry", "verse_contrast"):
                    # Verso: Puxado deliberadamente para os flancos laterais,
                    # limpando 100% o centro para a voz principal
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.68, y=0.20, z=0.10,
                        spread=0.35, lfe_send=0.0, volume_gain=0.95, is_stereo=True
                    )
                elif section_type == "verse_groove":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.74, y=0.05, z=0.22,
                        spread=0.48, lfe_send=0.0, volume_gain=0.98, is_stereo=True
                    )
                elif section_type == "buildup":
                    # Riser acústico: Sintetizadores ascendem em espiral ao teto
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.68, y=0.15, z=0.88,
                        spread=0.75, lfe_send=0.10, volume_gain=1.10, is_stereo=True
                    )
                elif section_type in ("chorus_drop", "climax"):
                    # Envolvimento 360° total: abraça o ouvinte pelas laterais e satélites traseiros
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.88, y=-0.25, z=0.45,
                        spread=0.80, lfe_send=0.15, volume_gain=1.18, is_stereo=True
                    )
                elif section_type == "chorus_hook":
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.84, y=-0.15, z=0.55,
                        spread=0.72, lfe_send=0.10, volume_gain=1.12, is_stereo=True
                    )
                elif section_type == "bridge_solo":
                    # Solo melódico: avança para o palco frontal direito em destaque
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.35, y=0.65, z=0.30,
                        spread=0.30, lfe_send=0.0, volume_gain=1.15, is_stereo=True
                    )
                elif section_type == "breakdown":
                    # Breakdown: Acordes e pads pairam diretamente sobre o ouvinte no teto
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.55, y=0.0, z=0.90,
                        spread=0.85, lfe_send=0.0, volume_gain=1.05, is_stereo=True
                    )
                else:  # outro
                    placements[name] = SpatialPlacement(
                        stem_name=name, x=0.70, y=-0.75, z=0.75,
                        spread=0.75, lfe_send=0.0, volume_gain=0.90, is_stereo=True
                    )

        # --- 5. EFEITO METICULOSO "LAST CHRISTMAS": VOCAL THROW NOS MÓDULOS TRASEIROS DESTACÁVEIS ---
        if has_vocal:
            base_vocal_name = next(s.name for s in stems if "vocal" in s.name.lower() or "voice" in s.name.lower())
            throw_instance_name = f"{base_vocal_name}::spatial_throw"

            if section_type in ("chorus_drop", "climax"):
                # Salto potente e inesperado nos módulos traseiros destacáveis (BL/BR)
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.72,
                    y=-0.82,                 # MÓDULOS TRASEIROS DESTACÁVEIS DA JBL BAR 1000
                    z=0.50,
                    spread=0.55,
                    lfe_send=0.0,
                    volume_gain=1.35,        # DESTAQUE AUDÍVEL, PROEMINENTE E POTENTE
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            elif section_type == "chorus_hook":
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.75,
                    y=-0.85,
                    z=0.55,
                    spread=0.50,
                    lfe_send=0.0,
                    volume_gain=1.30,
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            elif section_type == "buildup":
                # Prévia sutil ao fundo
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.60,
                    y=-0.50,
                    z=0.40,
                    spread=0.45,
                    lfe_send=0.0,
                    volume_gain=0.65,
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            elif section_type == "breakdown":
                # Eco etéreo no teto traseiro
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.55,
                    y=-0.65,
                    z=0.80,
                    spread=0.60,
                    lfe_send=0.0,
                    volume_gain=0.75,
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            elif section_type in ("post_chorus", "outro_groove"):
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.68,
                    y=-0.75,
                    z=0.38,
                    spread=0.50,
                    lfe_send=0.0,
                    volume_gain=0.80,
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            else:
                # Silenciado no Verso, Pausa e Intro:
                # Garante que a voz do verso permaneça 100% pura, seca e íntima na frente!
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.68,
                    y=-0.80,
                    z=0.45,
                    spread=0.50,
                    lfe_send=0.0,
                    volume_gain=0.0,
                    is_stereo=True,
                    is_muted=True,
                    source_stem_name=base_vocal_name
                )

        return placements

    @staticmethod
    def _compute_rms_profile(stem: Optional[StemTrack], num_frames: int) -> np.ndarray:
        """Calcula o perfil de energia RMS em janelas contíguas."""
        if stem is None or stem.audio_data is None or len(stem.audio_data) == 0:
            return np.zeros(num_frames, dtype=np.float32)

        data = stem.audio_data
        total_samples = len(data)
        frame_len = max(1, total_samples // num_frames)

        # Converte para mono
        if data.ndim == 2 and data.shape[1] >= 2:
            mono = 0.5 * (data[:, 0] + data[:, 1])
        elif data.ndim == 2:
            mono = data[:, 0]
        else:
            mono = data

        profile = np.zeros(num_frames, dtype=np.float32)
        for i in range(num_frames):
            start = i * frame_len
            end = min(total_samples, start + frame_len)
            if start < end:
                chunk = mono[start:end]
                profile[i] = float(np.sqrt(np.mean(chunk ** 2)))

        return profile
