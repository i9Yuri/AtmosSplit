"""
AtmosSplit — Integração com DirectFrame (HDMI eARC Passthrough)
Abre arquivos multicanal diretamente no motor do DirectFrame ou mpv nativo.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class DirectFrameBridge:
    def __init__(self, directframe_dir: Optional[Path] = None):
        self.directframe_dir = directframe_dir or Path("/home/yuri/Desktop/Yuri/Projects/DirectFrame")

    def is_directframe_available(self) -> bool:
        """Verifica se o projeto DirectFrame está presente no workspace."""
        main_py = self.directframe_dir / "main.py"
        return main_py.exists() and main_py.is_file()

    def play_multichannel_file(self, file_path: Path | str) -> bool:
        """
        Dispara a reprodução do arquivo MKV/WAV multicanal.
        Prioriza o DirectFrame com passthrough HDMI; fallback para mpv do sistema.
        """
        p = Path(file_path).resolve()
        if not p.exists():
            return False

        # Se DirectFrame estiver disponível, podemos abrir passando o caminho
        if self.is_directframe_available():
            venv_python = self.directframe_dir / ".venv" / "bin" / "python"
            run_cmd = str(venv_python) if venv_python.exists() else sys.executable
            main_py = self.directframe_dir / "main.py"
            try:
                subprocess.Popen(
                    [run_cmd, str(main_py), str(p)],
                    cwd=str(self.directframe_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                pass

        # Fallback para mpv nativo com passthrough HDMI e suporte multicanal 7.1.4
        mpv_bin = shutil.which("mpv")
        if mpv_bin:
            cmd = [
                mpv_bin,
                "--audio-spdif=ac3,eac3,truehd,dts-hd,dts",
                "--audio-channels=7.1.4,7.1,auto",
                "--audio-exclusive=yes",
                str(p)
            ]
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass

        return False
