"""Publica o master PCM ou JOC por substituição atômica no destino."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf

from ..acquisition.file_source import AudioMetadata
from .joc_encoder import JocMeasurements, encode_joc


class ExportFormat(str, Enum):
    MP4_ATMOS_JOC_714 = "mp4_atmos_joc_714"
    MP4_EAC3_71 = "mp4_atmos_joc_714"
    MKV_ATMOS_JOC_714 = "mkv_atmos_joc_714"
    MKV_EAC3_71 = "mkv_atmos_joc_714"
    MKV_LPCM_714 = "mkv_lpcm_714"
    WAV_714 = "wav_714"
    EC3_ATMOS_714 = "ec3_atmos_714"
    TRUEHD_71 = "truehd_71"


def _ffmpeg(args: list[str], timeout: int | None = None) -> None:
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", *args]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-1800:] or "Falha no FFmpeg.")


@dataclass(frozen=True)
class ExportResult:
    path: Path
    joc: JocMeasurements | None


class AudioExporter714:
    @classmethod
    def export(cls, multichannel_matrix: np.ndarray, output_path: Path | str, sample_rate: int = 48000,
               export_format: ExportFormat = ExportFormat.MP4_ATMOS_JOC_714,
               metadata: AudioMetadata | None = None) -> Path:
        return cls.export_verified(multichannel_matrix, output_path, sample_rate, export_format, metadata).path

    @staticmethod
    def export_verified(multichannel_matrix: np.ndarray, output_path: Path | str, sample_rate: int = 48000,
                        export_format: ExportFormat = ExportFormat.MP4_ATMOS_JOC_714,
                        metadata: AudioMetadata | None = None) -> ExportResult:
        audio = np.asarray(multichannel_matrix)
        if sample_rate <= 0 or audio.ndim != 2 or audio.shape[1] != 12 or len(audio) == 0:
            raise ValueError("O master precisa conter áudio 7.1.4 e taxa positiva.")
        for i in range(0, len(audio), 65536):
            if not np.isfinite(audio[i:i+65536]).all():
                raise ValueError("O master contém amostras não finitas.")
        fmt = ExportFormat(export_format)
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        duration = len(audio)/sample_rate
        joc = None
        with tempfile.TemporaryDirectory(prefix=".atmossplit-", dir=out.parent) as folder:
            work = Path(folder)
            if fmt in (ExportFormat.WAV_714, ExportFormat.MKV_LPCM_714, ExportFormat.TRUEHD_71):
                source = work / "master.wav"
                # WAVEX inclui a máscara WAVEFORMATEXTENSIBLE para os doze canais.
                _write_wave(source, audio, sample_rate)
            else:
                source = work / "master.ec3"
                joc = encode_joc(audio, source, sample_rate, 768)
            if fmt in (ExportFormat.WAV_714, ExportFormat.EC3_ATMOS_714):
                source.replace(out)
                return ExportResult(out, joc)
            # Uma imagem por segundo aproximadamente. A duração de cada pacote de vídeo
            # fecha a duração real, inclusive quando a faixa termina entre segundos.
            fps = Fraction(max(1, round(duration))*sample_rate, len(audio)).limit_denominator(60000)
            rate = f"{fps.numerator}/{fps.denominator}"
            video = ["-f", "lavfi", "-i", f"color=c=0x101818:s=1280x720:r={rate}:d={duration:.9f}"]
            if metadata and metadata.cover_image_bytes:
                raw, cover = work / "art", work / "cover.png"
                raw.write_bytes(metadata.cover_image_bytes)
                try:
                    _ffmpeg(["-protocol_whitelist", "file,pipe", "-i", str(raw), "-vf",
                             "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
                             "-frames:v", "1", str(cover)], timeout=12)
                    video = ["-loop", "1", "-framerate", rate, "-t", f"{duration:.9f}", "-i", str(cover)]
                except (RuntimeError, subprocess.TimeoutExpired):
                    pass
            codec = ["-c:a", "copy"]
            if fmt == ExportFormat.MKV_LPCM_714:
                codec = ["-c:a", "pcm_s24le", "-channel_layout", "7.1.4",
                         "-metadata:s:a:0", "CHANNEL_LAYOUT=FL+FR+FC+LFE+BL+BR+SL+SR+TFL+TFR+TBL+TBR"]
            elif fmt == ExportFormat.TRUEHD_71:
                codec = ["-af", "pan=7.1|FL=c0|FR=c1|FC=c2|LFE=c3|BL<c4+0.7*c10|"
                         "BR<c5+0.7*c11|SL<c6+0.7*c8|SR<c7+0.7*c9", "-c:a", "truehd", "-strict", "-2"]
            mp4 = fmt == ExportFormat.MP4_ATMOS_JOC_714
            staged = work / ("delivery.mp4" if mp4 else "delivery.mkv")
            args = [*video, "-i", str(source), "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-threads:v", "2", "-preset", "ultrafast", "-tune", "stillimage",
                    "-pix_fmt", "yuv420p", *codec]
            if fmt in (ExportFormat.MKV_LPCM_714, ExportFormat.TRUEHD_71):
                args.extend(["-t", f"{duration:.9f}"])
            if mp4:
                args.extend(["-movflags", "+faststart"])
            if metadata:
                for key in ("title", "artist", "album"):
                    value = getattr(metadata, key)
                    if value:
                        args.extend(["-metadata", f"{key}={value}"])
            _ffmpeg([*args, str(staged)])
            staged.replace(out)
        return ExportResult(out, joc)


def _write_wave(path: Path, audio: np.ndarray, rate: int) -> None:
    # libsndfile atribui máscara zero a WAVEX > 8 canais; gravamos a máscara canônica
    # no campo dwChannelMask do fmt extensível publicado por libsndfile.
    sf.write(path, audio, rate, format="WAVEX", subtype="PCM_24")
    import struct
    with path.open("r+b") as stream:
        stream.seek(12)
        while header := stream.read(8):
            tag, length = struct.unpack("<4sI", header)
            if tag == b"fmt " and length >= 40:
                stream.seek(20, 1)
                stream.write(struct.pack("<I", 0x2D63F))
                return
            stream.seek(length+(length % 2), 1)
    raise ValueError("Cabeçalho WAV extensível ausente.")
