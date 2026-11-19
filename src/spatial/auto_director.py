"""
AtmosSplit — Auto Atmos Director (Montador Espacial Inteligente 7.1.4)
Analisa características acústicas e gera posicionamentos musicais coerentes.
Suporta espelhamento estéreo (is_stereo) para pratos, ambiências e harmonias balanceadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

from .acoustic_analyzer import AcousticAnalyzer, StemAcousticProfile


class DirectorPreset(str, Enum):
    BALANCED = "balanced"        # Equilibrado (Estúdio Atmos clássico)
    IMMERSION_360 = "immersion"  # Imersão Total 360°
    LIVE_STAGE = "live"          # Palco Show ao Vivo (Frente sólida, plateia e teto com ambiência)
    VOCAL_FOCUS = "vocal_focus"  # Foco nos Vocais (Voz limpa e ancorada no centro)
    CLUB_BASS = "club"           # Pancada / Clube (Subwoofer pesado, batida frontal/lateral)


@dataclass
class SpatialPlacement:
    stem_name: str
    x: float            # -1.0 a 1.0 (Esquerda / Direita)
    y: float            # -1.0 a 1.0 (Traseira / Frente)
    z: float            #  0.0 a 1.0 (Chão / Teto)
    spread: float       #  0.0 a 1.0 (Foco pontual vs Difusão)
    lfe_send: float     #  0.0 a 1.0 (Envio ao subwoofer)
    volume_gain: float  #  Ganho relativo (padrão 1.0)
    is_muted: bool = False
    is_solo: bool = False
    is_stereo: bool = False  # Espelhamento simétrico estéreo L / R


class AutoAtmosDirector:
    @staticmethod
    def generate_placements(
        profiles: Dict[str, StemAcousticProfile],
        preset: DirectorPreset = DirectorPreset.BALANCED
    ) -> Dict[str, SpatialPlacement]:
        """Gera automaticamente as coordenadas e parâmetros de mixagem 7.1.4."""
        placements: Dict[str, SpatialPlacement] = {}

        for name, p in profiles.items():
            name_lower = name.lower()

            # Posições padrão para o preset BALANCED
            x = 0.0
            y = 0.0
            z = 0.0
            spread = 0.2
            lfe_send = 0.0
            gain = 1.0
            is_stereo = False

            # 1. Voz Principal (Lead Vocal) — Regra de Ouro da Indústria:
            # Ancoragem firme no canal central frontal (Center Channel) para máxima inteligibilidade e foco
            is_lead_vocal = "lead" in name_lower or (("vocal" in name_lower or "voice" in name_lower) and "back" not in name_lower and "choir" not in name_lower and p.stereo_width_ratio < 0.35)
            is_backing_vocal = "back" in name_lower or "choir" in name_lower or ("vocal" in name_lower and p.stereo_width_ratio >= 0.35)

            if is_lead_vocal:
                x = 0.0        # Ponto focal frontal absoluto (Center)
                y = 0.95       # Ancorado no canal frontal central (em frente ao ouvinte)
                z = 0.08       # Altura do ouvido (Ear Level)
                spread = 0.12  # Foco acústico preciso
                lfe_send = 0.0
                gain = 1.05
                is_stereo = False

            # 2. Coro / Backing Vocals / Harmonias
            # ESPELHADO: Amplo envolvimento lateral, traseiro e elevação aérea
            elif is_backing_vocal:
                x = 0.55       # Espelhado: -0.55 e +0.55
                y = -0.30      # Envolvendo as laterais e traseira
                z = 0.55       # Elevação aérea (teto/overhead)
                spread = 0.65
                lfe_send = 0.0
                is_stereo = True

            # 3. Bumbo (Kick) — Ancorado no centro frontal para soco rítmico
            elif "kick" in name_lower:
                x = 0.0
                y = 0.75
                z = 0.0
                spread = 0.10
                lfe_send = 0.95
                is_stereo = False

            # 4. Sub-Grave puro ou faixas com predominância sub-bass
            elif "sub" in name_lower or (p.sub_bass_energy_ratio > 0.45 and "air" not in name_lower and not is_lead_vocal and not is_backing_vocal):
                x = 0.0
                y = 0.55
                z = 0.0
                spread = 0.05
                lfe_send = 1.0
                is_stereo = False

            # 5. Baixo melódico
            elif "bass" in name_lower:
                x = 0.0
                y = 0.65
                z = 0.0
                spread = 0.20
                lfe_send = 0.35 if p.sub_bass_energy_ratio > 0.15 else 0.10
                is_stereo = False

            # 6. Caixa (Snare)
            elif "snare" in name_lower:
                x = 0.0        # Centralizado para impacto sólido no palco frontal
                y = 0.70
                z = 0.08
                spread = 0.20
                lfe_send = 0.05
                is_stereo = False

            # 7. Pratos / Chocalhos / Percussão aguda (Cymbals / Hi-hat / Shakers)
            # ESPELHAMENTO ESTÉREO AUTOMÁTICO: Envolve surround traseiro/lateral e teto em ambos os lados
            elif "cymbal" in name_lower or "hihat" in name_lower or (p.is_percussive and p.high_freq_energy_ratio > 0.35):
                x = 0.65       # Espelhado: -0.65 (Esq) e +0.65 (Dir)
                y = -0.15      # Laterais/Surround envolvendo o ouvinte
                z = 0.85       # Drivers de teto JBL Bar 1000 ativados
                spread = 0.45
                lfe_send = 0.0
                is_stereo = True

            # 8. Ambiência aérea (Teto / Reverb / Sintetizadores etéreos)
            # ESPELHADO: Topo da cúpula sonora nos 4 canais de teto
            elif "air" in name_lower or (p.high_freq_energy_ratio > 0.50 and not is_lead_vocal and not is_backing_vocal):
                x = 0.70       # Espelhado: -0.70 e +0.70
                y = -0.35      # Cúpula sonora surround completa
                z = 0.95       # Topo da cúpula sonora (4 canais de teto)
                spread = 0.85
                lfe_send = 0.0
                is_stereo = True

            # 9. Guitarras / Cordas / Teclados
            # ESPELHADO: Balanço estéreo natural do palco estendido
            elif "guitar" in name_lower or "key" in name_lower or "piano" in name_lower:
                x = 0.60       # Espelhado: -0.60 e +0.60
                y = 0.20
                z = 0.25
                spread = 0.50
                lfe_send = 0.0
                is_stereo = True

            # 10. Bateria genérica macro
            elif "drum" in name_lower:
                x = 0.0
                y = 0.70
                z = 0.15
                spread = 0.40
                lfe_send = 0.60
                is_stereo = False
            else:
                x = 0.0
                y = 0.0
                z = 0.30
                spread = 0.70
                lfe_send = 0.0
                is_stereo = False

            # Ajustes específicos conforme o PRESET selecionado
            if preset == DirectorPreset.IMMERSION_360:
                # Prática Profissional de Mixagem Atmos:
                # Voz Principal, Bumbo e Sub-Bass permanecem sempre solidamente ancorados na frente!
                if is_lead_vocal or "kick" in name_lower or "sub" in name_lower:
                    x = 0.0
                    y = max(0.85, y)
                    is_stereo = False
                elif is_backing_vocal:
                    y = -0.45
                    z = 0.70
                    spread = 0.70
                    is_stereo = True
                else:
                    y = y - 0.35
                    z = min(1.0, z + 0.30)
                    spread = min(1.0, spread + 0.25)
                    is_stereo = True

            elif preset == DirectorPreset.LIVE_STAGE:
                if "air" in name_lower or is_backing_vocal:
                    y = -0.80
                    z = 0.90
                    spread = 1.00
                    is_stereo = True
                else:
                    y = max(0.6, y)
                    z = min(0.3, z)

            elif preset == DirectorPreset.VOCAL_FOCUS:
                if is_lead_vocal:
                    gain = 1.25
                    spread = 0.10
                    y = 1.00
                    is_stereo = False
                elif is_backing_vocal:
                    gain = 0.90
                    spread = 0.70
                    is_stereo = True
                else:
                    gain = 0.88
                    spread = min(1.0, spread + 0.20)

            elif preset == DirectorPreset.CLUB_BASS:
                if "sub" in name_lower or "kick" in name_lower or "bass" in name_lower:
                    lfe_send = min(1.0, lfe_send * 1.3 + 0.2)
                    gain = 1.20
                if "cymbal" in name_lower or "air" in name_lower:
                    z = 1.00
                    is_stereo = True

            placements[name] = SpatialPlacement(
                stem_name=name,
                x=max(-1.0, min(1.0, x)),
                y=max(-1.0, min(1.0, y)),
                z=max(0.0, min(1.0, z)),
                spread=max(0.0, min(1.0, spread)),
                lfe_send=max(0.0, min(1.0, lfe_send)),
                volume_gain=gain,
                is_stereo=is_stereo
            )

        return placements
