"""Separação local. Os workers aplicam a afinidade antes de importar NumPy/Torch."""

from importlib import import_module

from .process_shield import apply_process_shield, get_shielded_thread_count

__all__ = ["apply_process_shield", "get_shielded_thread_count", "StemCacheManager",
           "CachedStemMetadata", "DeepStemEngine", "StemTrack", "SeparationResult"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    module = "cache_manager" if name in ("StemCacheManager", "CachedStemMetadata") else "stem_engine"
    return getattr(import_module(f".{module}", __name__), name)
