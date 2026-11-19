#!/usr/bin/env bash
# AtmosSplit — Launcher com isolamento de ambiente e prioridade de CPU
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Enforcar variáveis de ambiente seguras no Wayland / KDE Plasma
export QT_QPA_PLATFORM="wayland;xcb"
export QT_ENABLE_HIGHDPI_SCALING="1"

# Ambiente virtual isolado do projeto
VENV_PYTHON="$HERE/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[!] Ambiente virtual .venv não encontrado em $VENV_PYTHON."
    exit 1
fi

# NOTA ARQUITETURAL DE DESEMPENHO:
# A interface Qt (Wayland) e o player de áudio (sounddevice/PipeWire) rodam com prioridade normal
# (nice 0) para resposta visual imediata a 60 FPS e ausência de estalos de buffer.
# Os cálculos pesados de IA (Demucs) são executados em subprocesso isolado pelo worker_cli com
# nice -n 19, ionice -c 2 -n 7 e afinidade estrita reservando os núcleos 0 e 1 para o SO.
if [ $# -gt 0 ]; then
    exec "$VENV_PYTHON" -m src.ui.main_window "$@"
else
    exec "$VENV_PYTHON" -m src.ui.main_window
fi
