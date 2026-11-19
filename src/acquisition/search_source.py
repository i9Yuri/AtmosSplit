"""
AtmosSplit — Busca Integrada de Faixas Musicais
Reaproveita o ecossistema do AtmosHunter (Soulseek + Hi-Res Direct)
e utiliza yt-dlp como fallback para obter áudio de alta fidelidade.
"""

from __future__ import annotations

import sys
import os
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Callable

import requests


@dataclass
class SearchResultItem:
    title: str
    artist: str
    album: str
    source_type: str        # 'hires_direct' | 'soulseek' | 'ytdlp'
    format_label: str       # 'FLAC 24-bit' | 'E-AC-3 Atmos' | 'Original Audio'
    size_bytes: int
    duration_s: float
    download_url_or_id: str
    score: float = 1.0


class SearchSourceEngine:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(os.path.expanduser("~/.cache/atmossplit/downloads"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_monochrome_hires(self, query: str, limit: int = 5) -> List[SearchResultItem]:
        """Busca rápida na API Monochrome Hi-Res Direct do AtmosHunter."""
        results: List[SearchResultItem] = []
        try:
            url = f"https://api.monochrome.tf/search?q={requests.utils.quote(query)}"
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", {}).get("items", [])
                for item in items[:limit]:
                    title = item.get("title", "")
                    artist = item.get("artist", {}).get("name", "")
                    album = item.get("album", {}).get("title", "")
                    track_id = str(item.get("id", ""))
                    dur = float(item.get("duration", 0))
                    results.append(SearchResultItem(
                        title=title,
                        artist=artist,
                        album=album,
                        source_type="hires_direct",
                        format_label="FLAC Hi-Res 24-bit",
                        size_bytes=int(dur * 44100 * 2 * 3),  # Estimativa ~FLAC 24-bit
                        duration_s=dur,
                        download_url_or_id=track_id,
                        score=0.95
                    ))
        except Exception:
            pass
        return results

    def search_ytdlp_best(self, query: str, limit: int = 5) -> List[SearchResultItem]:
        """Busca faixas de áudio via yt-dlp (como no Vitrola)."""
        results: List[SearchResultItem] = []
        ytdlp_bin = shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")
        if not os.path.isfile(ytdlp_bin) and not shutil.which("yt-dlp"):
            return results

        cmd = [
            ytdlp_bin,
            f"ytsearch{limit}:{query}",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings"
        ]

        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=8)
            for line in out.splitlines():
                if not line.strip():
                    continue
                import json
                info = json.loads(line)
                title = info.get("title", query)
                uploader = info.get("uploader", "Artista Desconhecido")
                duration = float(info.get("duration") or 0.0)
                url_id = info.get("url") or info.get("id") or ""
                results.append(SearchResultItem(
                    title=title,
                    artist=uploader,
                    album="Single / Web",
                    source_type="ytdlp",
                    format_label="Áudio Original (Opus/AAC/FLAC)",
                    size_bytes=int(duration * 20000),
                    duration_s=duration,
                    download_url_or_id=url_id,
                    score=0.80
                ))
        except Exception:
            pass

        return results

    def search(self, query: str) -> List[SearchResultItem]:
        """Orquestra busca paralela / combinada priorizando lossless."""
        query = query.strip()
        if not query:
            return []

        hires_res = self.search_monochrome_hires(query, limit=4)
        if hires_res:
            return hires_res

        # Fallback para yt-dlp
        return self.search_ytdlp_best(query, limit=5)

    def download_to_file(self, item: SearchResultItem, progress_cb: Optional[Callable[[float, str], None]] = None) -> Path:
        """Baixa a faixa selecionada e salva em disco pronta para separação."""
        target_path = self.cache_dir / f"{item.artist} - {item.title}.flac".replace("/", "-")
        if target_path.exists() and target_path.stat().st_size > 10000:
            if progress_cb:
                progress_cb(1.0, "Carregado do cache local.")
            return target_path

        ytdlp_bin = shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")
        url = item.download_url_or_id
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"

        cmd = [
            ytdlp_bin,
            "-x",
            "--audio-format", "flac",
            "--audio-quality", "0",
            "-o", str(target_path),
            url
        ]

        if progress_cb:
            progress_cb(0.3, "Baixando fluxo de áudio de alta qualidade...")

        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if progress_cb:
            progress_cb(1.0, "Download concluído.")

        return target_path
