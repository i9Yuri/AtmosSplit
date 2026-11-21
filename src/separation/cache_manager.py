"""Cache local imutável. O manifesto publica uma geração completa dos stems."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


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


def _component(name: str) -> str:
    if not name or name in (".", "..") or Path(name).name != name:
        raise ValueError("Identificador de cache inválido.")
    return name


class StemCacheManager:
    def __init__(self, base_cache_dir: Path | None = None):
        cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        self.base_dir = base_cache_dir or cache_home / "atmossplit" / "stems_cache"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _cache_lock(self, exclusive: bool = False):
        # O descritor do diretório continua estável quando uma entrada é removida.
        directory = os.open(self.base_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(directory, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            os.close(directory)

    def get_track_cache_dir(self, file_hash: str, mode: str) -> Path:
        version = "_v2" if mode == "surgical" else ""
        return self.base_dir / f"{_component(file_hash)}_{_component(mode)}{version}"

    def get_manifest(self, file_hash: str, mode: str) -> list[CachedStemMetadata] | None:
        root = self.get_track_cache_dir(file_hash, mode)
        try:
            data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            if data["file_hash"] != file_hash or data["mode"] != mode:
                return None
            items = [CachedStemMetadata(**row) for row in data["stems"]]
            for item in items:
                path = (root / item.relative_path).resolve()
                if not path.is_relative_to(root.resolve()):
                    return None
                info = sf.info(path)
                if (info.samplerate != item.sample_rate or info.channels != item.channels
                        or info.frames <= 0 or abs(info.frames - item.duration_s * info.samplerate) > 1):
                    return None
            return items or None
        except (OSError, ValueError, TypeError, KeyError, sf.LibsndfileError):
            return None

    def has_cached_stems(self, file_hash: str, mode: str) -> bool:
        return self.get_manifest(file_hash, mode) is not None

    def save_stems(self, file_hash: str, mode: str, stems_dict: dict[str, np.ndarray],
                   stems_meta: dict[str, dict[str, Any]], sample_rate: int) -> list[CachedStemMetadata]:
        with self._cache_lock():
            root = self.get_track_cache_dir(file_hash, mode)
            root.mkdir(parents=True, exist_ok=True)
            with (root / ".writer").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                existing = self.get_manifest(file_hash, mode)
                if existing:
                    return existing
                # Um worker morto pode ter deixado apenas uma geração não publicada.
                for partial in root.glob(".pending-*"):
                    shutil.rmtree(partial, ignore_errors=True)
                stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
                generation = "audio-" + stage.name.removeprefix(".pending-")
                manifest = []
                try:
                    for name, audio in stems_dict.items():
                        meta = stems_meta.get(name, {})
                        filename = f"{_component(name)}.wav"
                        samples = audio[:, None] if audio.ndim == 1 else audio
                        # Stems podem exceder 0 dBFS antes do master. FLOAT preserva headroom.
                        sf.write(stage / filename, samples, sample_rate, subtype="FLOAT")
                        manifest.append(CachedStemMetadata(
                            name, meta.get("display_name", name), meta.get("color_hex", "#70B6AD"),
                            f"{generation}/{filename}", sample_rate, len(samples) / sample_rate,
                            samples.shape[1], meta.get("is_lfe_candidate", False),
                            meta.get("is_ceiling_candidate", False)))
                    payload = {"file_hash": file_hash, "mode": mode, "sample_rate": sample_rate,
                               "stems": [asdict(item) for item in manifest]}
                    (stage / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                    stage.rename(root / generation)
                    (root / generation / "manifest.json").replace(root / "manifest.json")
                finally:
                    if stage.exists():
                        shutil.rmtree(stage)
                return manifest

    def load_stems(self, file_hash: str, mode: str) -> dict[str, np.ndarray] | None:
        with self._cache_lock():
            items = self.get_manifest(file_hash, mode)
            if not items:
                return None
            root = self.get_track_cache_dir(file_hash, mode)
            try:
                return {item.stem_name: sf.read(root / item.relative_path, dtype="float32", always_2d=True)[0]
                        for item in items}
            except (OSError, sf.LibsndfileError):
                return None

    def list_cached_tracks(self) -> list[dict[str, Any]]:
        with self._cache_lock():
            return self._list_tracks()

    def _list_tracks(self) -> list[dict[str, Any]]:
        tracks = []
        for root in self.base_dir.iterdir():
            if root.is_symlink() or not root.is_dir():
                continue
            try:
                data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            size = 0
            for path in root.rglob("*"):
                try:
                    if path.is_file():
                        size += path.stat().st_size
                except FileNotFoundError:
                    continue  # Uma geração foi publicada durante o inventário.
            tracks.append(dict(folder_name=root.name, file_hash=data.get("file_hash", ""),
                               mode=data.get("mode", ""), stems_count=len(data.get("stems", [])),
                               size_bytes=size, size_mb=round(size / (1024**2), 2)))
        return tracks

    def get_total_cache_size_bytes(self) -> int:
        return sum(track["size_bytes"] for track in self.list_cached_tracks())

    def clear_cache(self, *, keep: tuple[str, str] | None = None) -> int:
        protected = self.get_track_cache_dir(*keep) if keep else None
        freed = 0
        with self._cache_lock(exclusive=True):
            for row in self._list_tracks():
                root = self.base_dir / row["folder_name"]
                if root != protected:
                    shutil.rmtree(root)
                    freed += row["size_bytes"]
        return freed
