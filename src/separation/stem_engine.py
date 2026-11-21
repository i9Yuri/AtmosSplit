"""
AtmosSplit — Orquestrador de Separação Profunda de Stems
Implementa pipeline multi-estágio:
- Estágio 1 (Macro-camadas via Demucs com segmentação temporal e controle estrito de RAM)
- Estágio 2 (Sub-divisão cirúrgica via DSP de fase linear)
- Cache transparente por SHA-256
- Blindagem térmica / CPU (Process Shield com afinidade de núcleos)
"""

from __future__ import annotations

import math
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any

import numpy as np
from scipy import signal

from .process_shield import get_shielded_thread_count
from .cache_manager import StemCacheManager
from .vocal_image import vocal_axis

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


def split_surgical(macro: dict[str, np.ndarray], rate: int) -> dict[str, np.ndarray]:
    """Subdivisão aditiva. A soma de cada par de bandas recupera o sinal original."""
    def lowpass(data: np.ndarray, hz: float) -> np.ndarray:
        if hz >= rate / 2 or len(data) < 2:
            return data.copy()
        sos = signal.butter(4, hz, fs=rate, output="sos")
        return signal.sosfiltfilt(sos, data, axis=0, padlen=min(15, len(data)-1)).astype("float32")

    drums, bass, vocals, other = (macro[k] for k in ("drums", "bass", "vocals", "other"))
    kick = lowpass(drums, 120)
    upper = drums - kick
    snare = lowpass(upper, 5000)
    sub = lowpass(bass, 80)
    body = lowpass(other, 6000)
    # O componente comum conserva a amplitude inteira de uma voz central.
    # O residual estéreo inclui as caudas laterais reais, inclusive em baixa frequência.
    axis = np.asarray(vocal_axis(vocals), dtype="f")
    if abs(axis[0]-axis[1]) < 1e-6:
        lead = np.repeat(vocals.mean(axis=1, keepdims=True), 2, axis=1)
    else:
        lead = (vocals @ axis)[:, None]*axis
    return dict(lead_vocal=lead, backing_vocals=vocals-lead, kick=kick, snare=snare,
                cymbals_hihat=upper-snare, sub_bass_lfe=sub, melodic_bass=bass-sub,
                guitar_keys=body, air_ambience=other-body)


def _tracks(arrays: dict[str, np.ndarray], rate: int) -> list[StemTrack]:
    tracks = []
    for name, data in arrays.items():
        fields = STEM_DEFINITIONS.get(name, {"display_name": name, "color_hex": "#70B6AD"})
        tracks.append(StemTrack(name=name, audio_data=data, sample_rate=rate, **fields))
    return tracks


def _resample(data: np.ndarray, source_rate: int, rate: int) -> np.ndarray:
    if source_rate == rate:
        return data
    divisor = math.gcd(source_rate, rate)
    return signal.resample_poly(data, rate // divisor, source_rate // divisor, axis=0)


class DeepStemEngine:
    def __init__(self, cache_manager: Optional[StemCacheManager] = None):
        self.cache_manager = cache_manager or StemCacheManager()
        self._demucs_model = None

    def _ensure_demucs_model(self):
        """Carrega lazy o modelo Demucs em CPU com threads otimizadas e blindadas."""
        if self._demucs_model is not None:
            return self._demucs_model
        
        import torch
        from demucs.apply import BagOfModels
        from demucs.pretrained import get_model
        torch.set_num_threads(get_shielded_thread_count())
        try:
            from demucs.hf import load_safetensors_model
            from huggingface_hub import hf_hub_download
            weights = hf_hub_download("adefossez/HTDemucs", "955717e8.safetensors", local_files_only=True)
        except (ImportError, OSError):
            checkpoints = Path(torch.hub.get_dir()) / "checkpoints"
            if not (checkpoints / "955717e8-8726e21a.th").is_file():
                raise FileNotFoundError("Pesos htdemucs ausentes do cache local (955717e8).") from None
            model = get_model("955717e8", repo=checkpoints)
        else:
            model = BagOfModels([load_safetensors_model(weights)])
        model.cpu()
        model.eval()
        self._demucs_model = model
        return self._demucs_model

    def load_cached_result(self, file_hash: str, mode: str) -> SeparationResult | None:
        start = time.monotonic()
        manifest = self.cache_manager.get_manifest(file_hash, mode)
        if not manifest:
            return None
        arrays = self.cache_manager.load_stems(file_hash, mode)
        if not arrays:
            return None
        return SeparationResult(_tracks(arrays, manifest[0].sample_rate), mode, file_hash,
                                time.monotonic() - start, True)

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
        cached = self.load_cached_result(file_hash, mode)
        if cached:
            return cached
        if mode not in ("fast", "surgical"):
            raise ValueError("Modo de separação desconhecido.")

        if cancel_check and cancel_check():
            raise InterruptedError("Separação cancelada pelo usuário.")

        # 2. Inferência local com o segmento nativo do modelo.
        if progress_callback:
            progress_callback(0.15, "Preparando o modelo Demucs em CPU…")
        model = self._ensure_demucs_model()
        import torch
        from demucs.apply import apply_model

        if audio_array.ndim == 1:
            audio_array = np.column_stack([audio_array, audio_array])

        # Se a taxa for superior a 48 kHz (ex: 96 kHz Hi-Res), downsample para 44.1 kHz para economizar 50% de RAM e CPU
        orig_sr = sample_rate
        demucs_sr = model.samplerate
        arr_for_demucs = _resample(audio_array, orig_sr, demucs_sr)
        tensor_in = torch.from_numpy(np.ascontiguousarray(arr_for_demucs.T, dtype=np.float32)).unsqueeze(0)

        shifts_val = 0
        segment_val = None
        overlap_val = 0.25
        sub_models = getattr(model, "models", (model,))
        total_chunks = 0
        for sub_model in sub_models:
            seg = float(segment_val if segment_val is not None else getattr(sub_model, "segment", 7.8))
            seg_len = int(demucs_sr * seg)
            stride = int((1 - overlap_val) * seg_len)
            total_chunks += len(range(0, tensor_in.shape[-1], stride))
        completed = 0
        inference_started = time.monotonic()

        def on_chunk(event: dict) -> None:
            nonlocal completed
            if cancel_check and cancel_check():
                raise InterruptedError("Separação cancelada pelo usuário.")
            if event.get("state") == "end" and progress_callback:
                completed += 1
                elapsed = time.monotonic() - inference_started
                remaining = math.ceil(elapsed * (total_chunks - completed) / completed)
                minutes, seconds = divmod(remaining, 60)
                eta = f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"
                ratio = completed / total_chunks
                progress_callback(
                    0.70 if completed == total_chunks else 0.15 + 0.55 * ratio,
                    f"Separando faixas neurais: trecho {completed}/{total_chunks} ({ratio:.0%}) — restante: {eta}",
                )

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
                num_workers=0,
                callback=on_chunk if progress_callback or cancel_check else None,
            )[0]

        if cancel_check and cancel_check():
            raise InterruptedError("Separação cancelada pelo usuário.")

        # Extração das 4 macro-camadas [drums, bass, other, vocals]
        if progress_callback:
            message = ("Subdividindo camadas acústicas 7.1.4 (DSP Cirúrgico)…" if mode == "surgical"
                       else "Preparando as quatro faixas separadas…")
            progress_callback(0.78, message)
        source_names = model.sources
        macro_stems: Dict[str, np.ndarray] = {}
        for idx, src_name in enumerate(source_names):
            stem_audio = sources[idx].numpy().T
            macro_stems[src_name] = _resample(stem_audio, demucs_sr, orig_sr)[:len(audio_array)]
        stems_dict = macro_stems if mode == "fast" else split_surgical(macro_stems, orig_sr)

        if cancel_check and cancel_check():
            raise InterruptedError("Separação cancelada pelo usuário.")

        # 4. Salvar no cache para reutilização instantânea
        if progress_callback:
            progress_callback(0.84, "Gravando stems no cache de alta performance…")

        self.cache_manager.save_stems(
            file_hash=file_hash,
            mode=mode,
            stems_dict=stems_dict,
            stems_meta=STEM_DEFINITIONS,
            sample_rate=orig_sr
        )

        track_list = _tracks(stems_dict, orig_sr)

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
