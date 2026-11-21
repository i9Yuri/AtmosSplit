"""
AtmosSplit — Ingestão de Arquivos Locais
Lê arquivos FLAC, WAV, ALAC, MP3, M4A, Opus e OGG,
extrai metadados (tags e capa) e calcula o hash SHA-256 para cache de stems.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
import hashlib
from pathlib import Path
from dataclasses import dataclass
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
    except (OSError, sf.LibsndfileError):
        from .probe_verifier import verify_audio_file
        probe = verify_audio_file(file_path)
        if not probe.is_valid:
            raise ValueError(probe.error_message or "Arquivo sem áudio.")
        meta.sample_rate, meta.channels = probe.sample_rate, probe.channels
        meta.format_name, meta.duration_s = probe.codec_name, probe.duration_s

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

    source = AudioSource(p, sha256, meta, sample_rate=meta.sample_rate)
    return populate_audio(source, target_sr) if load_data_now else source


def populate_audio(source: AudioSource, target_sr: int | None = None) -> AudioSource:
    """Decodifica uma fonte já identificada sem reler as tags nem recalcular o hash."""
    p, sr = source.file_path, source.metadata.sample_rate
    data = None
    if source.metadata.channels <= 2:
        try:
            data, sr = sf.read(p, dtype="float32", always_2d=True)
        except (OSError, sf.LibsndfileError):
            pass
    if data is None:
        with tempfile.TemporaryDirectory(prefix="atmossplit_decode_") as folder:
            wave = Path(folder) / "stereo.wav"
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                   "-i", str(p), "-map", "0:a:0", "-ac", "2", "-c:a", "pcm_f32le",
                   "-ar", str(target_sr or sr), str(wave)]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode:
                raise ValueError(result.stderr.decode(errors="replace")[-800:])
            data, sr = sf.read(wave, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    if target_sr and target_sr != sr:
        from scipy.signal import resample_poly
        divisor = math.gcd(sr, target_sr)
        data = resample_poly(data, target_sr//divisor, sr//divisor, axis=0)
        sr = target_sr
    if not len(data):
        raise ValueError("A faixa não contém amostras de áudio.")
    source.audio_data, source.sample_rate = data, sr
    return source
