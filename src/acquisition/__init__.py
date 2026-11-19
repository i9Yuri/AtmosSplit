"""
AtmosSplit — Módulo de Aquisição de Áudio
"""
from .file_source import AudioSource, load_audio_file
from .probe_verifier import verify_audio_file, AudioProbeResult
from .search_source import SearchSourceEngine, SearchResultItem

__all__ = [
    "AudioSource",
    "load_audio_file",
    "verify_audio_file",
    "AudioProbeResult",
    "SearchSourceEngine",
    "SearchResultItem",
]
