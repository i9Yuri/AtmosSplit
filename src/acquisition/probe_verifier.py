"""
AtmosSplit — Verificação Honesta de Arquivos de Áudio via ffprobe
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class AudioProbeResult:
    is_valid: bool
    format_name: str
    codec_name: str
    channels: int
    channel_layout: str
    sample_rate: int
    bit_rate: int
    duration_s: float
    profile: str = ""
    is_atmos: bool = False
    raw_info: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


def verify_audio_file(file_path: Path | str) -> AudioProbeResult:
    """Executa ffprobe para auditoria transparente do formato e canais."""
    p = Path(file_path).resolve()
    if not p.exists():
        return AudioProbeResult(
            is_valid=False,
            format_name="",
            codec_name="",
            channels=0,
            channel_layout="",
            sample_rate=0,
            bit_rate=0,
            duration_s=0.0,
            error_message="Arquivo não existe no disco."
        )

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(p)
    ]

    try:
        raw_out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        info = json.loads(raw_out)
    except Exception as exc:
        return AudioProbeResult(
            is_valid=False,
            format_name="",
            codec_name="",
            channels=0,
            channel_layout="",
            sample_rate=0,
            bit_rate=0,
            duration_s=0.0,
            error_message=f"Falha ao executar ffprobe: {exc}"
        )

    # Identificar a stream de áudio principal
    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        return AudioProbeResult(
            is_valid=False,
            format_name=info.get("format", {}).get("format_name", ""),
            codec_name="",
            channels=0,
            channel_layout="",
            sample_rate=0,
            bit_rate=0,
            duration_s=0.0,
            raw_info=info,
            error_message="Nenhuma stream de áudio encontrada no arquivo."
        )

    st = audio_streams[0]
    fmt = info.get("format", {})

    codec = st.get("codec_name", "")
    profile = st.get("profile", "")
    channels = int(st.get("channels", 0))
    layout = st.get("channel_layout", "")
    sample_rate = int(st.get("sample_rate", 0))
    
    # Bitrate pode estar na stream ou no contêiner
    bit_rate = int(st.get("bit_rate") or fmt.get("bit_rate") or 0)
    duration = float(fmt.get("duration") or st.get("duration") or 0.0)
    format_name = fmt.get("format_name", "")

    prof_low = profile.lower()
    is_atmos = ("atmos" in prof_low) or ("joc" in prof_low)

    return AudioProbeResult(
        is_valid=True,
        format_name=format_name,
        codec_name=codec,
        channels=channels,
        channel_layout=layout,
        sample_rate=sample_rate,
        bit_rate=bit_rate,
        duration_s=duration,
        profile=profile,
        is_atmos=is_atmos,
        raw_info=info
    )
