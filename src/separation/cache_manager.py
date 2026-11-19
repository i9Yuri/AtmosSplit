"""
AtmosSplit — Gerenciador de Cache de Stems
Salva e recupera stems isolados em disco indexados por SHA-256 e modo de separação,
permitindo reabrir faixas já processadas instantaneamente (< 0.5s).
Inclui auditoria de uso em disco e limpeza seletiva ou total.
"""

from __future__ import annotations

import os
import shutil
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List, Any

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)


@dataclass
class CachedStemMetadata:
    stem_name: str
    display_name: str
    color_hex: str
    relative_path: str
    sample_rate: int
    duration_s: float
    channels: int
    is_lfe_candidate: bool = False
    is_ceiling_candidate: bool = False


class StemCacheManager:
    def __init__(self, base_cache_dir: Optional[Path] = None):
        self.base_dir = base_cache_dir or Path(os.path.expanduser("~/.cache/atmossplit/stems_cache"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_track_cache_dir(self, file_hash: str, mode: str) -> Path:
        """Diretório específico da combinação Hash + Modo."""
        track_dir = self.base_dir / f"{file_hash}_{mode}"
        track_dir.mkdir(parents=True, exist_ok=True)
        return track_dir

    def has_cached_stems(self, file_hash: str, mode: str) -> bool:
        """Verifica se todos os stems e o manifesto de metadados existem no disco."""
        track_dir = self.get_track_cache_dir(file_hash, mode)
        manifest_path = track_dir / "manifest.json"
        if not manifest_path.exists():
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            stems = data.get("stems", [])
            if not stems:
                return False
            for s in stems:
                stem_file = track_dir / s["relative_path"]
                if not stem_file.exists() or stem_file.stat().st_size == 0:
                    return False
            return True
        except Exception:
            return False

    def save_stems(
        self,
        file_hash: str,
        mode: str,
        stems_dict: Dict[str, np.ndarray],
        stems_meta: Dict[str, Dict[str, Any]],
        sample_rate: int
    ) -> List[CachedStemMetadata]:
        """Salva stems em arquivos WAV PCM 24-bit e grava o manifesto de cache."""
        track_dir = self.get_track_cache_dir(file_hash, mode)
        manifest_items: List[CachedStemMetadata] = []

        for name, audio_data in stems_dict.items():
            meta = stems_meta.get(name, {})
            filename = f"{name}.wav"
            filepath = track_dir / filename
            
            # Garantir 2D (samples, channels)
            if audio_data.ndim == 1:
                audio_data = np.column_stack([audio_data, audio_data])
            elif audio_data.ndim == 2 and audio_data.shape[0] < audio_data.shape[1]:
                audio_data = audio_data.T

            sf.write(str(filepath), audio_data, sample_rate, subtype="PCM_24")

            dur = float(audio_data.shape[0]) / float(sample_rate)
            c_meta = CachedStemMetadata(
                stem_name=name,
                display_name=meta.get("display_name", name.capitalize()),
                color_hex=meta.get("color_hex", "#4A90E2"),
                relative_path=filename,
                sample_rate=sample_rate,
                duration_s=dur,
                channels=int(audio_data.shape[1]),
                is_lfe_candidate=meta.get("is_lfe_candidate", False),
                is_ceiling_candidate=meta.get("is_ceiling_candidate", False),
            )
            manifest_items.append(c_meta)

        # Salvar manifesto JSON
        manifest_path = track_dir / "manifest.json"
        manifest_data = {
            "file_hash": file_hash,
            "mode": mode,
            "sample_rate": sample_rate,
            "stems": [asdict(m) for m in manifest_items]
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        log.info("Stems salvos no cache: %s (%d faixas)", track_dir, len(manifest_items))
        return manifest_items

    def load_stems(self, file_hash: str, mode: str) -> Optional[Dict[str, np.ndarray]]:
        """Carrega todos os arrays de áudio dos stems do cache em memória."""
        if not self.has_cached_stems(file_hash, mode):
            return None

        track_dir = self.get_track_cache_dir(file_hash, mode)
        manifest_path = track_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        stems: Dict[str, np.ndarray] = {}
        for item in manifest_data.get("stems", []):
            stem_path = track_dir / item["relative_path"]
            data, sr = sf.read(str(stem_path), dtype="float32", always_2d=True)
            stems[item["stem_name"]] = data

        return stems

    def get_manifest(self, file_hash: str, mode: str) -> Optional[List[CachedStemMetadata]]:
        """Recupera metadados salvos sem precisar ler todo o áudio."""
        track_dir = self.get_track_cache_dir(file_hash, mode)
        manifest_path = track_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            return [CachedStemMetadata(**item) for item in manifest_data.get("stems", [])]
        except Exception:
            return None

    def get_total_cache_size_bytes(self) -> int:
        """Calcula tamanho total do cache em disco."""
        if not self.base_dir.exists():
            return 0
        total = 0
        for entry in self.base_dir.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
        return total

    def list_cached_tracks(self) -> List[Dict[str, Any]]:
        """Lista faixas em cache com tamanho e quantidade de stems."""
        if not self.base_dir.exists():
            return []
        items = []
        for child in self.base_dir.iterdir():
            if child.is_dir():
                manifest_path = child / "manifest.json"
                size_bytes = sum(f.stat().st_size for f in child.glob("*") if f.is_file())
                stems_count = 0
                mode = ""
                file_hash = ""
                if manifest_path.exists():
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as mf:
                            m_data = json.load(mf)
                            stems_count = len(m_data.get("stems", []))
                            mode = m_data.get("mode", "")
                            file_hash = m_data.get("file_hash", "")
                    except Exception:
                        pass
                items.append({
                    "folder_name": child.name,
                    "file_hash": file_hash,
                    "mode": mode,
                    "stems_count": stems_count,
                    "size_bytes": size_bytes,
                    "size_mb": round(size_bytes / (1024 * 1024), 2)
                })
        return items

    def clear_cache(self) -> int:
        """Limpa todo o cache e retorna o total de bytes liberados."""
        freed = self.get_total_cache_size_bytes()
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
        return freed
