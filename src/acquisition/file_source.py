"""
AtmosSplit — Ingestão de Arquivos Locais
Lê arquivos FLAC, WAV, ALAC, MP3, M4A, Opus e OGG,
extrai metadados (tags e capa) e calcula o hash SHA-256 para cache de stems.
"""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

import soundfile as sf
import numpy as np

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
except ImportError:
    mutagen = None


@dataclass
class AudioMetadata:
    title: str = "Faixa Desconhecida"
    artist: str = "Artista Desconhecido"
    album: str = "Álbum Desconhecido"
    year: str = ""
    genre: str = ""
    duration_s: float = 0.0
    sample_rate: int = 44100
    channels: int = 2
    format_name: str = "Desconhecido"
    cover_image_bytes: Optional[bytes] = None


@dataclass
class AudioSource:
    file_path: Path
    sha256_hash: str
    metadata: AudioMetadata
    audio_data: Optional[np.ndarray] = None
    sample_rate: int = 44100


def calculate_file_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Calcula hash SHA-256 estável do arquivo para identificação e cache de stems."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_metadata_from_file(file_path: Path) -> AudioMetadata:
    """Extrai tags e metadados usando mutagen e soundfile."""
    meta = AudioMetadata()
    
    # Informações técnicas via soundfile
    try:
        info = sf.info(str(file_path))
        meta.duration_s = float(info.duration)
        meta.sample_rate = int(info.samplerate)
        meta.channels = int(info.channels)
        meta.format_name = str(info.format)
    except Exception:
        pass

    # Nome básico derivado do arquivo
    meta.title = file_path.stem

    if mutagen is None:
        return meta

    try:
        m = mutagen.File(str(file_path))
        if m is not None:
            # Título
            if "title" in m:
                meta.title = str(m["title"][0])
            elif "TIT2" in m:
                meta.title = str(m["TIT2"])
            elif "\xa9nam" in m:
                meta.title = str(m["\xa9nam"][0])

            # Artista
            if "artist" in m:
                meta.artist = str(m["artist"][0])
            elif "TPE1" in m:
                meta.artist = str(m["TPE1"])
            elif "\xa9ART" in m:
                meta.artist = str(m["\xa9ART"][0])

            # Álbum
            if "album" in m:
                meta.album = str(m["album"][0])
            elif "TALB" in m:
                meta.album = str(m["TALB"])
            elif "\xa9alb" in m:
                meta.album = str(m["\xa9alb"][0])

            # Ano / Data
            if "date" in m:
                meta.year = str(m["date"][0])
            elif "TDRC" in m:
                meta.year = str(m["TDRC"])
            elif "\xa9day" in m:
                meta.year = str(m["\xa9day"][0])

            # Capa de álbum
            if hasattr(m, "pictures") and m.pictures:
                meta.cover_image_bytes = m.pictures[0].data
            elif "covr" in m and m["covr"]:
                meta.cover_image_bytes = bytes(m["covr"][0])
            elif hasattr(m, "tags"):
                for tag_name, tag_val in m.tags.items():
                    if tag_name.startswith("APIC"):
                        meta.cover_image_bytes = tag_val.data
                        break
    except Exception:
        pass

    return meta


def load_audio_file(file_path: Path | str, load_data_now: bool = True, target_sr: Optional[int] = None) -> AudioSource:
    """
    Carrega o arquivo de áudio especificado, calculando o hash e metadados.
    Se load_data_now for True, carrega o array numpy float32 estéreo.
    """
    p = Path(file_path).resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")

    sha256 = calculate_file_sha256(p)
    meta = extract_metadata_from_file(p)

    audio_array = None
    sr = meta.sample_rate

    if load_data_now:
        audio_array, sr = sf.read(str(p), dtype="float32", always_2d=True)
        # Se for mono, duplicar para estéreo para compatibilidade com o pipeline
        if audio_array.shape[1] == 1:
            audio_array = np.repeat(audio_array, 2, axis=1)

    return AudioSource(
        file_path=p,
        sha256_hash=sha256,
        metadata=meta,
        audio_data=audio_array,
        sample_rate=sr
    )
