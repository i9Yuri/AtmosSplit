"""
AtmosSplit — Ponte DLNA/UPnP para TV Samsung Tizen + JBL Bar 1000
Permite cast do áudio espacial para a TV e automação KEY_PICTURE_OFF para apagar a tela.
Integra-se ao ecossistema existente com o AtmosHunter e servidor Rygel.
"""

from __future__ import annotations

import os
import sys
import json
import logging
import threading
from pathlib import Path
from typing import Optional, Tuple, Any

log = logging.getLogger(__name__)


class SamsungDLNABridge:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_file = (config_dir or Path(os.path.expanduser("~/.config/atmoshunter"))) / "tv_samsung.json"
        self._cached_tv_ip: Optional[str] = None

    def get_configured_tv_ip(self) -> Optional[str]:
        """Lê o IP da TV Samsung configurado pelo AtmosHunter."""
        if self._cached_tv_ip:
            return self._cached_tv_ip
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ip = data.get("ip") or data.get("tv_ip")
                    if ip:
                        self._cached_tv_ip = ip
                        return ip
            except Exception:
                pass
        return None

    def turn_off_tv_screen(self) -> bool:
        """
        Envia o comando KEY_PICTURE_OFF para a TV Samsung Tizen via WebSocket seguro (porta 8002).
        A música continua tocando pela soundbar com a tela 100% apagada.
        """
        atmoshunter_core = Path("/home/yuri/Desktop/Yuri/Projects/Zenith/AtmosHunter")
        if atmoshunter_core.exists() and str(atmoshunter_core) not in sys.path:
            sys.path.insert(0, str(atmoshunter_core))

        try:
            from core.tv_control import SamsungTVController
            ctl = SamsungTVController()
            if ctl.is_configured():
                threading.Thread(target=ctl.picture_off, daemon=True).start()
                log.info("Comando Picture Off disparado para a TV Samsung.")
                return True
        except Exception as ex:
            log.debug("Aviso ao tentar desligar tela da TV: %s", ex)

        return False

    def cast_file_to_soundbar(self, file_path: Path | str, auto_picture_off: bool = True) -> bool:
        """
        Inicia cast do arquivo multicanal para a TV/Soundbar via DLNA/UPnP.
        Utiliza o micro-servidor HTTP Range e renderers descobertos no ecossistema AtmosHunter.
        """
        p = Path(file_path).resolve()
        if not p.exists():
            return False

        atmoshunter_core = Path("/home/yuri/Desktop/Yuri/Projects/Zenith/AtmosHunter")
        if atmoshunter_core.exists() and str(atmoshunter_core) not in sys.path:
            sys.path.insert(0, str(atmoshunter_core))

        try:
            from core.dlna_bridge import discover_renderers, play_on_renderer, LibraryItem
            renderers = discover_renderers()
            if not renderers:
                log.info("Nenhum renderer DLNA ativo respondendo no momento.")
                return False

            tv_ip = self.get_configured_tv_ip()
            target_renderer = None
            if tv_ip:
                for r in renderers:
                    if r.ip == tv_ip:
                        target_renderer = r
                        break

            # Se não encontrou TV pelo IP, usa a primeira TV encontrada ou JBL
            if not target_renderer:
                for r in renderers:
                    if getattr(r, "is_tv", False):
                        target_renderer = r
                        break
            if not target_renderer:
                target_renderer = renderers[0]

            item = LibraryItem(
                path=p,
                title=p.stem,
                filename=p.name,
                size_bytes=p.stat().st_size,
                size_label=f"{round(p.stat().st_size / (1024*1024), 1)} MB",
                is_video_wrapped=p.suffix.lower() == ".mp4",
                is_atmos=True,
                is_surround=True
            )

            def _cast_worker():
                try:
                    success, msg = play_on_renderer(item, target_renderer)
                    log.info("DLNA Cast resultado: %s - %s", success, msg)
                    if success and auto_picture_off:
                        self.turn_off_tv_screen()
                except Exception as ex:
                    log.warning("Erro no thread de cast DLNA: %s", ex)

            threading.Thread(target=_cast_worker, daemon=True).start()
            return True

        except Exception as ex:
            log.debug("Ponte DLNA do AtmosHunter indisponível: %s", ex)
            return False
