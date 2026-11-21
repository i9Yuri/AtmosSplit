"""Busca opcional de áudio. A importação e o processamento local funcionam offline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .probe_verifier import verify_audio_file

CATALOG = "https://tracks.monochrome.st"


@dataclass
class SearchResultItem:
    title: str
    artist: str
    album: str
    source_type: str
    format_label: str
    size_bytes: int
    duration_s: float
    download_url_or_id: str
    score: float = 1.


class SearchSourceEngine:
    def __init__(self, cache_dir: Path | None = None):
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home()/".cache"))
        self.cache_dir = cache_dir or root/"atmossplit"/"downloads"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_monochrome_hires(self, query: str, limit: int = 5) -> list[SearchResultItem]:
        url = CATALOG+"/search/tracks?"+urlencode({"q": query, "limit": limit})
        try:
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=7) as response:
                rows = json.loads(response.read(2_000_000)).get("tracks", [])
            results = []
            for row in rows[:limit]:
                tid = str(row.get("trackId") or row.get("id") or "")
                if not re.fullmatch(r"[\w-]{1,96}", tid, re.ASCII) or not row.get("title"):
                    continue
                artists = row.get("artistNames") or [a["name"] for a in row.get("artists", [])]
                duration = float(row.get("duration") or 0)
                results.append(SearchResultItem(row["title"], ", ".join(artists), row.get("releaseTitle", ""),
                               "hires_direct", "Catálogo FLAC", int(row.get("size") or 0),
                               duration/1000 if duration > 10000 else duration, tid))
            return results
        except (URLError, OSError, ValueError, TypeError, KeyError):
            return []

    def search_ytdlp_best(self, query: str, limit: int = 5) -> list[SearchResultItem]:
        exe = shutil.which("yt-dlp")
        if not exe:
            return []
        try:
            data = subprocess.check_output([exe, "--ignore-config", "--flat-playlist", "--dump-json",
                                            "--no-warnings", "--", f"ytsearch{limit}:{query}"],
                                           text=True, stderr=subprocess.DEVNULL, timeout=18)
            results = []
            for line in data.splitlines():
                row = json.loads(line)
                identifier = str(row.get("id", ""))
                if re.fullmatch(r"[\w-]{11}", identifier, re.ASCII):
                    results.append(SearchResultItem(row.get("title", query), row.get("uploader") or "",
                                   "", "ytdlp", "Áudio da plataforma", 0,
                                   float(row.get("duration") or 0), identifier))
            return results
        except (subprocess.SubprocessError, ValueError, OSError):
            return []

    def search(self, query: str) -> list[SearchResultItem]:
        query = query.strip()
        return (self.search_monochrome_hires(query, 4) or self.search_ytdlp_best(query)) if query else []

    def download_to_file(self, item: SearchResultItem,
                         progress_cb: Callable[[float, str], None] | None = None) -> Path:
        identifier = item.download_url_or_id
        if not re.fullmatch(r"[\w-]{1,96}", identifier, re.ASCII):
            raise ValueError("Identificador de faixa inválido.")
        key = hashlib.sha256(f"{item.source_type}/{identifier}".encode()).hexdigest()[:12]
        label = re.sub(r"[^\w .()-]", "_", f"{item.artist} - {item.title}")[:45].strip()
        target = self.cache_dir / f"{label} [{key}].flac"
        if target.is_file() and verify_audio_file(target).is_valid:
            return target
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as folder:
            staged = Path(folder)/"audio.flac"
            if item.source_type == "hires_direct":
                with urlopen(f"{CATALOG}/track/{identifier}", timeout=20) as response, staged.open("wb") as f:
                    shutil.copyfileobj(response, f, 131072)
            elif item.source_type == "ytdlp" and len(identifier) == 11:
                exe = shutil.which("yt-dlp")
                if not exe:
                    raise FileNotFoundError("yt-dlp indisponível para esta fonte.")
                subprocess.run([exe, "--ignore-config", "--no-playlist", "-x", "--audio-format", "flac",
                                "-o", str(Path(folder)/"audio.%(ext)s"), "--",
                                f"https://www.youtube.com/watch?v={identifier}"], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
            else:
                raise ValueError("Fonte de áudio desconhecida.")
            result = verify_audio_file(staged)
            if not result.is_valid or result.codec_name != "flac":
                raise ValueError("O provedor não entregou uma faixa FLAC decodificável.")
            staged.replace(target)
        if progress_cb:
            progress_cb(1., "Faixa pronta.")
        return target
