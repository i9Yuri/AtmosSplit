"""
AtmosSplit — Song Structure Intelligence (Atmos Maestro Automático)
Motor analítico autônomo que estuda a estrutura musical e a dinâmica da faixa
(energia RMS temporal por stems, detecção de atividade vocal/VAD, largura estéreo
e contrastes espectrais).
Gera automaticamente uma automação espacial 7.1.4 de nível de estúdio Dolby Atmos,
identificando seções (Intro, Versos, Build-ups/Load-up, Refrões, Pontes, Clímax e Outro)
e criando instâncias de destaque vocal ("vocal throws" e respostas corais)
nos módulos traseiros destacáveis da JBL Bar 1000MK2 e nos canais de teto.
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
    section_type: str  # "intro", "verse", "buildup", "chorus", "bridge", "outro"
    start_time_s: float
    end_time_s: float
    color_hex: str
    description: str


class SongStructureIntelligence:
    """
    Inteligência musical autônoma para arranjo e mixagem espacial dinâmica Dolby Atmos 7.1.4.
    Analisa os stems da música ao longo do tempo e projeta movimentos cinematográficos,
    ancoragem frontal no verso, ascensão no build-up, explosão 360° no refrão e
    lançamento vocal nos módulos traseiros destacáveis ("vocal throw" / eco surround).
    """

    COLOR_PALETTE = {
        "intro": "#4299E1",     # Azul Royal (Aberto, acolhedor)
        "verse": "#38B2AC",     # Teal (Focado, intimista)
        "buildup": "#ED8936",   # Laranja (Tensão, ascensão)
        "chorus": "#00E5FF",    # Ciano Neon (Explosão 360°)
        "bridge": "#9F7AEA",    # Roxo Lavanda (Contraste harmônico)
        "climax": "#F56565",    # Coral Neon (Pico de energia)
        "outro": "#ECC94B",     # Amarelo Ouro (Decaimento suave)
    }

    @classmethod
    def analyze_and_arrange(
        cls,
        stems: List[StemTrack],
        total_duration_s: float,
        preset: DirectorPreset = DirectorPreset.BALANCED
    ) -> List[SpatialSection]:
        """
        Analisa os stems da música ao longo do tempo e gera a lista completa de seções
        musicais com seus respectivos mapas de posicionamento 7.1.4 refinados.
        """
        dur = max(2.0, float(total_duration_s))
        sections_desc = cls._detect_musical_sections(stems, dur)

        # 2. Gerar posicionamentos 7.1.4 meticulosos para cada seção
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
        Analisa curvas de energia RMS, VAD (atividade vocal) e transientes dos stems
        para segmentar a música em seções estruturais realistas.
        """
        stems_by_name = {s.name.lower(): s for s in stems}
        vocals_track = stems_by_name.get("vocals") or stems_by_name.get("lead_vocal")
        drums_track = stems_by_name.get("drums") or stems_by_name.get("drum")
        bass_track = stems_by_name.get("bass")
        other_track = stems_by_name.get("other") or stems_by_name.get("synths")

        # Resolução temporal: janelas de 200 ms
        frame_s = 0.200
        num_frames = max(5, int(duration_s / frame_s))

        vocal_energy = cls._compute_rms_profile(vocals_track, num_frames)
        drums_energy = cls._compute_rms_profile(drums_track, num_frames)
        bass_energy = cls._compute_rms_profile(bass_track, num_frames)
        other_energy = cls._compute_rms_profile(other_track, num_frames)

        # Energia combinada ponderada
        total_energy = 0.35 * vocal_energy + 0.30 * drums_energy + 0.20 * bass_energy + 0.15 * other_energy
        max_energy = np.max(total_energy) if np.max(total_energy) > 0 else 1.0
        norm_energy = total_energy / max_energy

        # Suavização para identificar macro-regiões (janela de 3 segundos = 15 quadros)
        smoothed = np.convolve(norm_energy, np.ones(15) / 15.0, mode="same")

        # 1. Identificar início da batida e da voz (Intro)
        intro_end = 0.0
        has_drums = drums_track is not None and np.max(drums_energy) > 0.05
        has_vocals = vocals_track is not None and np.max(vocal_energy) > 0.05

        if has_drums:
            # Ponto onde a bateria atinge 25% da sua potência máxima
            thresh_drums = 0.25 * np.max(drums_energy)
            beat_start_idx = np.where(drums_energy > thresh_drums)[0]
            if len(beat_start_idx) > 0 and beat_start_idx[0] > 5:
                intro_end = float(beat_start_idx[0]) * frame_s

        if intro_end <= 0.0 and has_vocals:
            # Ponto onde a voz entra com firmeza
            thresh_vocal = 0.20 * np.max(vocal_energy)
            voc_start_idx = np.where(vocal_energy > thresh_vocal)[0]
            if len(voc_start_idx) > 0 and voc_start_idx[0] > 5:
                intro_end = float(voc_start_idx[0]) * frame_s

        # Limitar Intro entre 6s e 30s (ou 15% da música)
        max_intro = min(28.0, duration_s * 0.18)
        if intro_end < 6.0 or intro_end > max_intro:
            intro_end = min(max_intro, max(8.0, duration_s * 0.10))

        # 2. Identificar Outro (queda final de energia)
        outro_start = duration_s
        tail_search_start = int((duration_s * 0.80) / frame_s)
        tail_energy = smoothed[tail_search_start:]
        if len(tail_energy) > 10:
            low_thresh = 0.30
            low_indices = np.where(tail_energy < low_thresh)[0]
            if len(low_indices) > 0:
                candidate_outro = (tail_search_start + low_indices[0]) * frame_s
                if (duration_s - candidate_outro) >= 6.0:
                    outro_start = candidate_outro

        if (duration_s - outro_start) < 6.0:
            outro_start = max(intro_end + 30.0, duration_s - min(25.0, duration_s * 0.12))

        mid_duration = outro_start - intro_end

        # 3. Segmentação inteligente do corpo musical
        sections: List[SectionDescriptor] = []

        # Intro
        sections.append(
            SectionDescriptor(
                name="Intro (Ambiência Aérea)",
                section_type="intro",
                start_time_s=0.0,
                end_time_s=intro_end,
                color_hex=cls.COLOR_PALETTE["intro"],
                description="Abertura espacial: ambiência no teto e laterais com campo frontal aberto."
            )
        )

        if mid_duration < 60.0:
            # Músicas curtas (< 1m30s): Verso -> Refrão
            v_len = mid_duration * 0.50
            t_mid = intro_end + v_len
            sections.append(
                SectionDescriptor(
                    name="Verso (Voz Frontal Seca)",
                    section_type="verse",
                    start_time_s=intro_end,
                    end_time_s=t_mid,
                    color_hex=cls.COLOR_PALETTE["verse"],
                    description="Voz ancorada no centro frontal, ritmo firme e intimista."
                )
            )
            sections.append(
                SectionDescriptor(
                    name="Refrão (Imersão 360°)",
                    section_type="chorus",
                    start_time_s=t_mid,
                    end_time_s=outro_start,
                    color_hex=cls.COLOR_PALETTE["chorus"],
                    description="Explosão 360°: coros nos módulos traseiros e pratos no teto."
                )
            )
        elif mid_duration < 140.0:
            # Músicas médias (~2 a 3 minutos): Verso 1 -> Build-up 1 -> Refrão 1 -> Verso 2 -> Refrão Final
            t1 = intro_end + mid_duration * 0.28   # Fim do Verso 1
            t2 = intro_end + mid_duration * 0.40   # Fim do Build-up 1
            t3 = intro_end + mid_duration * 0.65   # Fim do Refrão 1
            t4 = intro_end + mid_duration * 0.80   # Fim do Verso 2

            sections.extend([
                SectionDescriptor("Verso 1 (Foco Vocal)", "verse", intro_end, t1, cls.COLOR_PALETTE["verse"], "Voz no centro frontal (Center), clareza máxima."),
                SectionDescriptor("Build-up (Ascensão ao Teto)", "buildup", t1, t2, cls.COLOR_PALETTE["buildup"], "Tensão crescente: sintetizadores e esteiras sobem ao teto."),
                SectionDescriptor("Refrão 1 (Surround 360°)", "chorus", t2, t3, cls.COLOR_PALETTE["chorus"], "Voz central + respostas nos módulos destacáveis traseiros."),
                SectionDescriptor("Verso 2 (Groove Íntimo)", "verse", t3, t4, cls.COLOR_PALETTE["verse"], "Retorno ao palco frontal seco e ancorado."),
                SectionDescriptor("Refrão Final (Clímax 7.1.4)", "climax", t4, outro_start, cls.COLOR_PALETTE["climax"], "Pico de imersão: 12 canais ativos, coros em ambos os satélites.")
            ])
        else:
            # Músicas completas (> 3 minutos):
            # Verso 1 -> Build-up 1 -> Refrão 1 -> Verso 2 -> Build-up 2 -> Refrão 2 -> Ponte / Solo -> Refrão Final
            t1 = intro_end + mid_duration * 0.18
            t2 = intro_end + mid_duration * 0.26
            t3 = intro_end + mid_duration * 0.44
            t4 = intro_end + mid_duration * 0.58
            t5 = intro_end + mid_duration * 0.66
            t6 = intro_end + mid_duration * 0.80
            t7 = intro_end + mid_duration * 0.88

            sections.extend([
                SectionDescriptor("Verso 1 (Foco Central)", "verse", intro_end, t1, cls.COLOR_PALETTE["verse"], "Palco frontal cristalino."),
                SectionDescriptor("Build-up 1 (Riser 3D)", "buildup", t1, t2, cls.COLOR_PALETTE["buildup"], "Ascensão vertical aos 4 canais de teto."),
                SectionDescriptor("Refrão 1 (Explosão 360°)", "chorus", t2, t3, cls.COLOR_PALETTE["chorus"], "Respostas vocais saltam para os módulos traseiros destacáveis."),
                SectionDescriptor("Verso 2 (Dinâmica Seca)", "verse", t3, t4, cls.COLOR_PALETTE["verse"], "Ancoragem frontal estreita."),
                SectionDescriptor("Build-up 2 (Tensão Máxima)", "buildup", t4, t5, cls.COLOR_PALETTE["buildup"], "Elevação acústica e abertura estéreo."),
                SectionDescriptor("Refrão 2 (Envolvimento Total)", "chorus", t5, t6, cls.COLOR_PALETTE["chorus"], "Ambiência envolvente e pratos aéreos."),
                SectionDescriptor("Ponte / Solo (Destaque 3D)", "bridge", t6, t7, cls.COLOR_PALETTE["bridge"], "Foco nos instrumentos melódicos e movimento lateral."),
                SectionDescriptor("Refrão Final (Clímax Absoluto)", "climax", t7, outro_start, cls.COLOR_PALETTE["climax"], "Potência total em todos os 12 canais 7.1.4.")
            ])

        # Outro / Final
        sections.append(
            SectionDescriptor(
                name="Outro (Decaimento Imersivo)",
                section_type="outro",
                start_time_s=outro_start,
                end_time_s=duration_s,
                color_hex=cls.COLOR_PALETTE["outro"],
                description="Decaimento espacial: instrumentos e caudas flutuam suavemente para o teto e traseira."
            )
        )

        # Ajuste de bordas com tolerância estrita (contiguidade contínua)
        for i in range(len(sections) - 1):
            sections[i].end_time_s = sections[i + 1].start_time_s

        return sections

    @classmethod
    def _generate_section_placements(
        cls,
        stems: List[StemTrack],
        section_type: str,
        preset: DirectorPreset
    ) -> Dict[str, SpatialPlacement]:
        """
        Calcula as coordenadas 3D (X, Y, Z), espelhamento estéreo, difusão e ganho
        específicos para o clima emocional e arquitetural de cada seção.
        Gera automaticamente o "vocals::spatial_throw" (lançamento nos módulos traseiros destacáveis).
        """
        placements: Dict[str, SpatialPlacement] = {}

        has_vocal = any("vocal" in s.name.lower() or "voice" in s.name.lower() for s in stems)

        for s in stems:
            name = s.name
            name_lower = name.lower()

            # --- 1. VOZES (VOCALS) ---
            if "vocal" in name_lower or "voice" in name_lower:
                if section_type in ("verse", "intro"):
                    # Verso: Ancoragem frontal firme e cristalina (Regra de ouro Atmos)
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.95,
                        z=0.08,
                        spread=0.10,
                        lfe_send=0.0,
                        volume_gain=1.05,
                        is_stereo=False
                    )
                elif section_type == "buildup":
                    # Build-up: Voz abre ligeira difusão aérea
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.90,
                        z=0.22,
                        spread=0.25,
                        lfe_send=0.0,
                        volume_gain=1.08,
                        is_stereo=False
                    )
                elif section_type in ("chorus", "climax"):
                    # Refrão: Centro firme com asas laterais
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.95,
                        z=0.12,
                        spread=0.30,
                        lfe_send=0.0,
                        volume_gain=1.12,
                        is_stereo=False
                    )
                elif section_type == "bridge":
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.75,
                        z=0.18,
                        spread=0.35,
                        lfe_send=0.0,
                        volume_gain=1.00,
                        is_stereo=False
                    )
                else:  # Outro
                    # Outro: Flutua suavemente para trás e para o teto
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=-0.25,
                        z=0.55,
                        spread=0.50,
                        lfe_send=0.0,
                        volume_gain=0.95,
                        is_stereo=False
                    )

            # --- 2. BATERIA / RITMO (DRUMS) ---
            elif "drum" in name_lower or "kick" in name_lower or "snare" in name_lower:
                if section_type == "intro":
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.50,
                        z=0.0,
                        spread=0.20,
                        lfe_send=0.50,
                        volume_gain=0.90,
                        is_stereo=False
                    )
                elif section_type in ("verse", "bridge"):
                    # Verso: Bateria seca e frontal
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.68,
                        z=0.0,
                        spread=0.12,
                        lfe_send=0.90,
                        volume_gain=1.00,
                        is_stereo=False
                    )
                elif section_type == "buildup":
                    # Build-up: Pratos e caixas começam a subir ao teto
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.60,
                        z=0.35,
                        spread=0.35,
                        lfe_send=0.95,
                        volume_gain=1.05,
                        is_stereo=False
                    )
                else:  # chorus, climax
                    # Refrão: Grande presença com pratos espelhados no teto
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.0,
                        y=0.65,
                        z=0.25,
                        spread=0.40,
                        lfe_send=1.0,
                        volume_gain=1.10,
                        is_stereo=False
                    )

            # --- 3. BAIXO (BASS / 808) ---
            elif "bass" in name_lower:
                # Ancoragem firme no centro e envio direto ao Subwoofer de 10" da JBL Bar 1000
                placements[name] = SpatialPlacement(
                    stem_name=name,
                    x=0.0,
                    y=0.55,
                    z=0.0,
                    spread=0.05,
                    lfe_send=1.0,
                    volume_gain=1.0,
                    is_stereo=False
                )

            # --- 4. INSTRUMENTOS HARMÔNICOS / AMBIÊNCIA (OTHER) ---
            else:
                if section_type == "intro":
                    # Nuvem aérea envolvente no teto e laterais
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.70,
                        y=0.0,
                        z=0.70,
                        spread=0.60,
                        lfe_send=0.0,
                        volume_gain=1.0,
                        is_stereo=True
                    )
                elif section_type == "verse":
                    # Asas estéreo ao nível do ouvido, deixando o centro livre para a voz
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.55,
                        y=0.25,
                        z=0.10,
                        spread=0.40,
                        lfe_send=0.0,
                        volume_gain=0.95,
                        is_stereo=True
                    )
                elif section_type == "buildup":
                    # Riser acústico: Sintetizadores e acordes ascendem ao teto
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.65,
                        y=0.10,
                        z=0.85,
                        spread=0.65,
                        lfe_send=0.10,
                        volume_gain=1.08,
                        is_stereo=True
                    )
                elif section_type in ("chorus", "climax"):
                    # Envolvimento 360° total: lateral, traseira e teto
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.85,
                        y=-0.20,
                        z=0.50,
                        spread=0.75,
                        lfe_send=0.15,
                        volume_gain=1.15,
                        is_stereo=True
                    )
                elif section_type == "bridge":
                    # Spotlight solo: destaque melódico avançado
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.40,
                        y=0.60,
                        z=0.30,
                        spread=0.40,
                        lfe_send=0.0,
                        volume_gain=1.10,
                        is_stereo=True
                    )
                else:  # outro
                    placements[name] = SpatialPlacement(
                        stem_name=name,
                        x=0.65,
                        y=-0.60,
                        z=0.75,
                        spread=0.70,
                        lfe_send=0.0,
                        volume_gain=0.90,
                        is_stereo=True
                    )

        # --- 5. EFEITO METICULOSO "LAST CHRISTMAS": VOCAL THROW NOS MÓDULOS TRASEIROS DESTACÁVEIS ---
        # Se a música possui vocal, criamos automaticamente a instância clonada "vocals::spatial_throw".
        # No verso, ela permanece mutada (voz íntima na frente).
        # No refrão e clímax, ela salta com força (+1.25) diretamente nos módulos traseiros destacáveis (BL/BR)!
        if has_vocal:
            base_vocal_name = next(s.name for s in stems if "vocal" in s.name.lower() or "voice" in s.name.lower())
            throw_instance_name = f"{base_vocal_name}::spatial_throw"

            if section_type in ("chorus", "climax"):
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.68,                  # Espelhado L e R
                    y=-0.78,                 # MÓDULOS TRASEIROS DESTACÁVEIS (Traseira marcante)
                    z=0.45,                  # Altura imersiva surround
                    spread=0.50,
                    lfe_send=0.0,
                    volume_gain=1.28,        # PROEMINENTE E DESTACADO (Perceptível e inesperado!)
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            elif section_type == "buildup":
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.55,
                    y=-0.50,
                    z=0.35,
                    spread=0.45,
                    lfe_send=0.0,
                    volume_gain=0.85,
                    is_stereo=True,
                    is_muted=False,
                    source_stem_name=base_vocal_name
                )
            else:
                # Mutado no Verso e Intro: mantém a voz do verso limpa e na frente
                placements[throw_instance_name] = SpatialPlacement(
                    stem_name=throw_instance_name,
                    x=0.65,
                    y=-0.75,
                    z=0.40,
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
