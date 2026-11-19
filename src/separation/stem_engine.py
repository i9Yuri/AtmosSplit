"""
AtmosSplit — Orquestrador de Separação Profunda de Stems
Implementa pipeline multi-estágio:
- Estágio 1 (Macro-camadas via Demucs com segmentação temporal e controle estrito de RAM)
- Estágio 2 (Sub-divisão cirúrgica via DSP de fase linear)
- Cache transparente por SHA-256
- Blindagem térmica / CPU (Process Shield com afinidade de núcleos)
"""

from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any

import numpy as np
import soundfile as sf
from scipy import signal

from .process_shield import apply_process_shield, get_shielded_thread_count
from .cache_manager import StemCacheManager, CachedStemMetadata

log = logging.getLogger(__name__)


@dataclass
class StemTrack:
    name: str
    display_name: str
    color_hex: str
    audio_data: np.ndarray  # Shape: (num_samples, 2)
    sample_rate: int
    is_lfe_candidate: bool = False
    is_ceiling_candidate: bool = False
    initial_pan_x: float = 0.0   # -1.0 (Left) a +1.0 (Right)
    initial_pan_y: float = 0.0   # -1.0 (Back) a +1.0 (Front)
    initial_pan_z: float = 0.0   #  0.0 (Floor) a +1.0 (Ceiling)
    initial_spread: float = 0.2  # Largura na sala (0 = pontual, 1 = surround)
    initial_lfe_send: float = 0.0 # 0.0 a 1.0


@dataclass
class SeparationResult:
    stems: List[StemTrack]
    mode: str
    file_hash: str
    elapsed_time_s: float
    from_cache: bool


STEM_DEFINITIONS = {
    # Modo Rápido
    "vocals": {
        "display_name": "Vozes",
        "color_hex": "#00E5FF",      # Ciano brilhante
        "is_lfe_candidate": False,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.9,
        "initial_pan_z": 0.1,
        "initial_spread": 0.2,
        "initial_lfe_send": 0.0,
    },
    "drums": {
        "display_name": "Bateria Completa",
        "color_hex": "#FF9100",      # Laranja quente
        "is_lfe_candidate": True,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.6,
        "initial_pan_z": 0.0,
        "initial_spread": 0.3,
        "initial_lfe_send": 0.5,
    },
    "bass": {
        "display_name": "Baixo & Graves",
        "color_hex": "#FF3D00",      # Vermelho intenso
        "is_lfe_candidate": True,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.5,
        "initial_pan_z": 0.0,
        "initial_spread": 0.1,
        "initial_lfe_send": 0.8,
    },
    "other": {
        "display_name": "Harmonia & Instrumentos",
        "color_hex": "#00E676",      # Verde esmeralda
        "is_lfe_candidate": False,
        "is_ceiling_candidate": True,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.0,
        "initial_pan_z": 0.3,
        "initial_spread": 0.6,
        "initial_lfe_send": 0.0,
    },
    # Modo Cirúrgico / Destrinchado (Sub-divisões)
    "lead_vocal": {
        "display_name": "Voz Principal",
        "color_hex": "#00E5FF",      # Ciano
        "is_lfe_candidate": False,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 1.0,        # Ancorado na frente (Canal Central)
        "initial_pan_z": 0.1,
        "initial_spread": 0.15,
        "initial_lfe_send": 0.0,
    },
    "backing_vocals": {
        "display_name": "Coro & Backing Vocals",
        "color_hex": "#1DE9B6",      # Verde-água
        "is_lfe_candidate": False,
        "is_ceiling_candidate": True,
        "initial_pan_x": 0.0,
        "initial_pan_y": -0.3,       # Envolvendo os lados e traseira
        "initial_pan_z": 0.5,        # Leve elevação espacial
        "initial_spread": 0.8,
        "initial_lfe_send": 0.0,
    },
    "kick": {
        "display_name": "Bumbo (Kick)",
        "color_hex": "#FF3D00",      # Vermelho escuro
        "is_lfe_candidate": True,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.7,        # Frontal sólido
        "initial_pan_z": 0.0,
        "initial_spread": 0.1,
        "initial_lfe_send": 1.0,     # Envio máximo para subwoofer
    },
    "snare": {
        "display_name": "Caixa (Snare)",
        "color_hex": "#FF9100",      # Laranja
        "is_lfe_candidate": False,
        "is_ceiling_candidate": False,
        "initial_pan_x": -0.15,      # Levemente à esquerda como bateria real
        "initial_pan_y": 0.7,
        "initial_pan_z": 0.1,
        "initial_spread": 0.2,
        "initial_lfe_send": 0.1,
    },
    "cymbals_hihat": {
        "display_name": "Pratos & Chocalhos",
        "color_hex": "#FFEA00",      # Dourado
        "is_lfe_candidate": False,
        "is_ceiling_candidate": True, # Excelente para canais de altura
        "initial_pan_x": 0.4,
        "initial_pan_y": 0.2,
        "initial_pan_z": 0.8,        # Elevado ao teto
        "initial_spread": 0.5,
        "initial_lfe_send": 0.0,
    },
    "sub_bass_lfe": {
        "display_name": "Sub-Grave Puro (< 80 Hz)",
        "color_hex": "#D50000",      # Vermelho profundo
        "is_lfe_candidate": True,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.5,
        "initial_pan_z": 0.0,
        "initial_spread": 0.0,
        "initial_lfe_send": 1.0,     # 100% canal LFE
    },
    "melodic_bass": {
        "display_name": "Baixo Melódico",
        "color_hex": "#FF6D00",      # Laranja escuro
        "is_lfe_candidate": False,
        "is_ceiling_candidate": False,
        "initial_pan_x": 0.0,
        "initial_pan_y": 0.5,
        "initial_pan_z": 0.0,
        "initial_spread": 0.2,
        "initial_lfe_send": 0.2,
    },
    "guitar_keys": {
        "display_name": "Guitarras & Teclados",
        "color_hex": "#00E676",      # Verde
        "is_lfe_candidate": False,
        "is_ceiling_candidate": False,
        "initial_pan_x": -0.6,       # Lateral esquerdo
        "initial_pan_y": 0.1,
        "initial_pan_z": 0.2,
        "initial_spread": 0.6,
        "initial_lfe_send": 0.0,
    },
    "air_ambience": {
        "display_name": "Ambiência Aérea (Teto)",
        "color_hex": "#76FF03",      # Verde claro etéreo
        "is_lfe_candidate": False,
        "is_ceiling_candidate": True, # 100% teto
        "initial_pan_x": 0.0,
        "initial_pan_y": -0.2,
        "initial_pan_z": 1.0,        # Topo da cúpula sonora
        "initial_spread": 0.9,
        "initial_lfe_send": 0.0,
    }
}


class DeepStemEngine:
    def __init__(self, cache_manager: Optional[StemCacheManager] = None):
        self.cache_manager = cache_manager or StemCacheManager()
        self._demucs_model = None

    def _ensure_demucs_model(self):
        """Carrega lazy o modelo Demucs em CPU com threads otimizadas e blindadas."""
        if self._demucs_model is not None:
            return self._demucs_model
        
        apply_process_shield(reserve_cores=2)
        import torch
        from demucs.pretrained import get_model
        log.info("Carregando modelo Demucs htdemucs...")
        model = get_model("htdemucs")
        model.cpu()
        model.eval()
        self._demucs_model = model
        return self._demucs_model

    def separate_track(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        file_hash: str,
        mode: str = "surgical",  # 'fast' ou 'surgical'
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> SeparationResult:
        """
        Executa separação de stems com segmentação controlada para proteção de RAM
        e prioridade estrita de CPU para não congelar o KDE Plasma.
        """
        t0 = time.time()

        # 1. Checar se já existe no cache
        if self.cache_manager.has_cached_stems(file_hash, mode):
            if progress_callback:
                progress_callback(1.0, "Carregando stems do cache ultra-rápido...")
            cached_stems = self.cache_manager.load_stems(file_hash, mode)
            if cached_stems:
                track_list: List[StemTrack] = []
                for name, data in cached_stems.items():
                    defn = STEM_DEFINITIONS.get(name, {
                        "display_name": name.capitalize(),
                        "color_hex": "#4A90E2",
                        "is_lfe_candidate": False,
                        "is_ceiling_candidate": False,
                    })
                    track_list.append(StemTrack(
                        name=name,
                        display_name=defn.get("display_name", name),
                        color_hex=defn.get("color_hex", "#4A90E2"),
                        audio_data=data,
                        sample_rate=sample_rate,
                        is_lfe_candidate=defn.get("is_lfe_candidate", False),
                        is_ceiling_candidate=defn.get("is_ceiling_candidate", False),
                        initial_pan_x=defn.get("initial_pan_x", 0.0),
                        initial_pan_y=defn.get("initial_pan_y", 0.0),
                        initial_pan_z=defn.get("initial_pan_z", 0.0),
                        initial_spread=defn.get("initial_spread", 0.2),
                        initial_lfe_send=defn.get("initial_lfe_send", 0.0),
                    ))
                return SeparationResult(
                    stems=track_list,
                    mode=mode,
                    file_hash=file_hash,
                    elapsed_time_s=time.time() - t0,
                    from_cache=True
                )

        apply_process_shield(reserve_cores=2)

        if cancel_check and cancel_check():
            raise InterruptedError("Separação cancelada pelo usuário.")

        # 2. Executar Estágio 1: Macro-Camadas via Demucs com Chunking Seguro
        if progress_callback:
            progress_callback(0.1, "Iniciando Demucs em CPU (Afinidade núcleos 2-15)...")

        model = self._ensure_demucs_model()
        import torch
        from demucs.apply import apply_model

        if audio_array.ndim == 1:
            audio_array = np.column_stack([audio_array, audio_array])

        # Se a taxa for superior a 48 kHz (ex: 96 kHz Hi-Res), downsample para 44.1 kHz para economizar 50% de RAM e CPU
        orig_sr = sample_rate
        demucs_sr = model.samplerate
        arr_for_demucs = audio_array
        if orig_sr != demucs_sr:
            import librosa
            arr_for_demucs = librosa.resample(arr_for_demucs.T, orig_sr=orig_sr, target_sr=demucs_sr).T

        tensor_in = torch.tensor(arr_for_demucs.T, dtype=torch.float32).unsqueeze(0)

        if progress_callback:
            progress_callback(0.25, "Inferência neural segmentada (baixo consumo de RAM)...")

        # Configurações de otimização de hardware no Xeon:
        # segment=10.0: processa fatias de 10s mantendo o pico de RAM estável (< 1.2 GB)
        # shifts=0 no fast, shifts=1 no surgical (evita reprocessamento desnecessário)
        shifts_val = 0 if mode == "fast" else 1
        segment_val = 10.0
        overlap_val = 0.25

        with torch.no_grad():
            sources = apply_model(
                model,
                tensor_in,
                shifts=shifts_val,
                split=True,
                segment=segment_val,
                overlap=overlap_val,
                device="cpu",
                progress=False,
                num_workers=0
            )[0]

        if cancel_check and cancel_check():
            raise InterruptedError("Separação cancelada pelo usuário.")

        # Extração das 4 macro-camadas [drums, bass, other, vocals]
        source_names = model.sources
        macro_stems: Dict[str, np.ndarray] = {}
        for idx, src_name in enumerate(source_names):
            stem_audio = sources[idx].numpy().T
            if orig_sr != demucs_sr:
                import librosa
                stem_audio = librosa.resample(stem_audio.T, orig_sr=demucs_sr, target_sr=orig_sr).T
            macro_stems[src_name] = stem_audio.astype(np.float32)

        stems_dict: Dict[str, np.ndarray] = {}

        if mode == "fast":
            stems_dict = macro_stems
        else:
            # 3. Estágio 2: Sub-divisão cirúrgica DSP de alta resolução
            if progress_callback:
                progress_callback(0.70, "Executando sub-divisão cirúrgica DSP de instrumentos...")

            # --- A. BATERIA / PERCUSSÃO (drums) ---
            drums = macro_stems.get("drums", np.zeros_like(audio_array))
            sos_kick = signal.butter(4, 120.0, btype="lowpass", fs=orig_sr, output="sos")
            sos_above_kick = signal.butter(4, 120.0, btype="highpass", fs=orig_sr, output="sos")
            kick = signal.sosfiltfilt(sos_kick, drums, axis=0)
            drums_midhigh = signal.sosfiltfilt(sos_above_kick, drums, axis=0)

            sos_cym = signal.butter(4, 5000.0, btype="highpass", fs=orig_sr, output="sos")
            sos_snare = signal.butter(4, 5000.0, btype="lowpass", fs=orig_sr, output="sos")
            cymbals_hihat = signal.sosfiltfilt(sos_cym, drums_midhigh, axis=0)
            snare = signal.sosfiltfilt(sos_snare, drums_midhigh, axis=0)

            stems_dict["kick"] = kick
            stems_dict["snare"] = snare
            stems_dict["cymbals_hihat"] = cymbals_hihat

            # --- B. GRAVE / BAIXO (bass) ---
            bass = macro_stems.get("bass", np.zeros_like(audio_array))
            # Crossover Linkwitz-Riley 4th order em 80 Hz (< 80 Hz = LFE puro)
            sos_lfe = signal.butter(4, 80.0, btype="lowpass", fs=orig_sr, output="sos")
            sos_melodic = signal.butter(4, 80.0, btype="highpass", fs=orig_sr, output="sos")
            sub_bass_lfe = signal.sosfiltfilt(sos_lfe, bass, axis=0)
            melodic_bass = signal.sosfiltfilt(sos_melodic, bass, axis=0)

            stems_dict["sub_bass_lfe"] = sub_bass_lfe
            stems_dict["melodic_bass"] = melodic_bass

            # --- C. VOZES (vocals) ---
            vocals = macro_stems.get("vocals", np.zeros_like(audio_array))
            # Isolamento coerente em fase para Lead Vocal (centro) e Backing Vocals (estéreo envolvente)
            mid = 0.5 * (vocals[:, 0] + vocals[:, 1])
            lead_vocal = np.column_stack([mid, mid])

            # Backing vocals: extração estéreo pura SEM inversão de polaridade (proibido [+side, -side])
            # Subtrai a maior parte do centro comum (85%), isolando backing vocals, harmonias e reverbs
            side_l = vocals[:, 0] - 0.85 * mid
            side_r = vocals[:, 1] - 0.85 * mid
            # Filtro passa-altas Linkwitz/Butterworth de 4ª ordem em 180 Hz para eliminar vazamento sub-grave
            sos_vocal_hp = signal.butter(4, 180.0, btype="highpass", fs=orig_sr, output="sos")
            backing_l = signal.sosfiltfilt(sos_vocal_hp, side_l)
            backing_r = signal.sosfiltfilt(sos_vocal_hp, side_r)
            backing_vocals = np.column_stack([backing_l, backing_r])

            stems_dict["lead_vocal"] = lead_vocal
            stems_dict["backing_vocals"] = backing_vocals

            # --- D. OUTROS / HARMONIA (other) ---
            other = macro_stems.get("other", np.zeros_like(audio_array))
            sos_air = signal.butter(4, 6000.0, btype="highpass", fs=orig_sr, output="sos")
            sos_body = signal.butter(4, 6000.0, btype="lowpass", fs=orig_sr, output="sos")
            air_ambience = signal.sosfiltfilt(sos_air, other, axis=0)
            guitar_keys = signal.sosfiltfilt(sos_body, other, axis=0)

            stems_dict["guitar_keys"] = guitar_keys
            stems_dict["air_ambience"] = air_ambience

        if cancel_check and cancel_check():
            raise InterruptedError("Separação cancelada pelo usuário.")

        # 4. Salvar no cache para reutilização instantânea
        if progress_callback:
            progress_callback(0.90, "Gravando stems no cache local...")

        self.cache_manager.save_stems(
            file_hash=file_hash,
            mode=mode,
            stems_dict=stems_dict,
            stems_meta=STEM_DEFINITIONS,
            sample_rate=orig_sr
        )

        track_list: List[StemTrack] = []
        for name, data in stems_dict.items():
            defn = STEM_DEFINITIONS.get(name, {
                "display_name": name.capitalize(),
                "color_hex": "#4A90E2",
                "is_lfe_candidate": False,
                "is_ceiling_candidate": False,
            })
            track_list.append(StemTrack(
                name=name,
                display_name=defn.get("display_name", name),
                color_hex=defn.get("color_hex", "#4A90E2"),
                audio_data=data,
                sample_rate=orig_sr,
                is_lfe_candidate=defn.get("is_lfe_candidate", False),
                is_ceiling_candidate=defn.get("is_ceiling_candidate", False),
                initial_pan_x=defn.get("initial_pan_x", 0.0),
                initial_pan_y=defn.get("initial_pan_y", 0.0),
                initial_pan_z=defn.get("initial_pan_z", 0.0),
                initial_spread=defn.get("initial_spread", 0.2),
                initial_lfe_send=defn.get("initial_lfe_send", 0.0),
            ))

        if progress_callback:
            progress_callback(1.0, "Separação concluída com sucesso.")

        elapsed = time.time() - t0
        log.info("Separação de stems (%s) finalizada em %.2f s", mode, elapsed)
        return SeparationResult(
            stems=track_list,
            mode=mode,
            file_hash=file_hash,
            elapsed_time_s=elapsed,
            from_cache=False
        )
