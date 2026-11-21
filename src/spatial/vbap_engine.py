"""
AtmosSplit — Motor de Pan 3D VBAP para Sala 7.1.4
Calcula ganhos dos 12 alto-falantes com conservação estrita de potência constante (L2 norm).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class SpeakerPosition714:
    channel_index: int
    code: str
    name: str
    x: float  # -1 (Esquerda) a +1 (Direita)
    y: float  # -1 (Traseira) a +1 (Frente)
    z: float  #  0 (Chão) a +1 (Teto)
    is_lfe: bool = False


# Coordenadas físicas do layout 7.1.4 da JBL Bar 1000MK2
SPEAKER_COORDINATES_714: List[SpeakerPosition714] = [
    SpeakerPosition714(0,  "FL",  "Frontal Esquerdo",        -0.70,  1.00, 0.00),
    SpeakerPosition714(1,  "FR",  "Frontal Direito",          0.70,  1.00, 0.00),
    SpeakerPosition714(2,  "FC",  "Frontal Central",          0.00,  1.00, 0.00),
    SpeakerPosition714(3,  "LFE", "Subwoofer (LFE)",          0.00,  1.00, 0.00, is_lfe=True),
    SpeakerPosition714(4,  "BL",  "Traseiro Esquerdo",       -0.70, -1.00, 0.00),
    SpeakerPosition714(5,  "BR",  "Traseiro Direito",         0.70, -1.00, 0.00),
    SpeakerPosition714(6,  "SL",  "Lateral Esquerdo",        -1.00,  0.00, 0.00),
    SpeakerPosition714(7,  "SR",  "Lateral Direito",          1.00,  0.00, 0.00),
    SpeakerPosition714(8,  "TFL", "Teto Frontal Esquerdo",   -0.60,  0.60, 1.00),
    SpeakerPosition714(9,  "TFR", "Teto Frontal Direito",    0.60,  0.60, 1.00),
    SpeakerPosition714(10, "TBL", "Teto Traseiro Esquerdo",  -0.60, -0.60, 1.00),
    SpeakerPosition714(11, "TBR", "Teto Traseiro Direito",   0.60, -0.60, 1.00),
]


class VBAP714Engine:
    def __init__(self, speakers: Optional[List[SpeakerPosition714]] = None):
        self.speakers = speakers or SPEAKER_COORDINATES_714
        self.spatial_speakers = [s for s in self.speakers if not s.is_lfe]
        self._xyz = np.array([(s.x, s.y, s.z) for s in self.spatial_speakers])
        self._indices = [s.channel_index for s in self.spatial_speakers]
        self.lfe_speaker = next(s for s in self.speakers if s.is_lfe)

    def calculate_gains(
        self,
        x: float,
        y: float,
        z: float,
        spread: float = 0.2,
        lfe_send: float = 0.0
    ) -> np.ndarray:
        """
        Calcula o vetor de ganhos [12] para um som localizado em (x, y, z).
        - x in [-1.0, 1.0] (Esquerda / Direita)
        - y in [-1.0, 1.0] (Atrás / Frente)
        - z in [ 0.0, 1.0] (Chão / Teto)
        - spread in [0.0, 1.0] (0 = pontual preciso, 1 = ambiente difuso)
        - lfe_send in [0.0, 1.0] (envio direto ao canal de subwoofer)
        """
        # Limitar valores ao domínio válido
        x = max(-1.0, min(1.0, float(x)))
        y = max(-1.0, min(1.0, float(y)))
        z = max(0.0, min(1.0, float(z)))
        spread = max(0.0, min(1.0, float(spread)))
        lfe_send = max(0.0, min(1.0, float(lfe_send)))

        gains = np.zeros(12, dtype=np.float32)

        # 1. Distância euclidiana 3D para cada alto-falante espacial
        pos_target = np.array([x, y, z], dtype=np.float32)
        exponent = 2.0 / (0.2 + 0.8*spread)
        distances = np.linalg.norm(self._xyz - pos_target, axis=1) + .08
        weights = (distances.min()/distances)**exponent
        gains[self._indices] = weights/np.linalg.norm(weights)

        # 3. Canal LFE (Subwoofer)
        gains[self.lfe_speaker.channel_index] = lfe_send

        return gains
