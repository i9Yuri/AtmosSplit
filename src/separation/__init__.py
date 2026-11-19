"""
AtmosSplit — Módulo de Separação de Stems por IA e DSP Cirúrgico
"""
from .process_shield import apply_process_shield, get_shielded_thread_count
from .cache_manager import StemCacheManager, CachedStemMetadata
from .stem_engine import DeepStemEngine, StemTrack, SeparationResult

__all__ = [
    "apply_process_shield",
    "get_shielded_thread_count",
    "StemCacheManager",
    "CachedStemMetadata",
    "DeepStemEngine",
    "StemTrack",
    "SeparationResult",
]
