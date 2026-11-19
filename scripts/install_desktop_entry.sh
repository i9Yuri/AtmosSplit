#!/usr/bin/env bash
# Instala o atalho de duplo clique do AtmosSplit na Área de Trabalho e no menu
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "$HERE/iniciar.sh"
chmod +x "$HERE/Abrir_AtmosSplit.sh"
chmod +x "$HERE/AtmosSplit.desktop"

# 1. Instalar na Área de Trabalho do Usuário (Desktop principal)
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$HERE/AtmosSplit.desktop" "$DESKTOP_DIR/AtmosSplit.desktop"
    chmod +x "$DESKTOP_DIR/AtmosSplit.desktop"
    # Marcar como confiável no KDE Plasma se gio estiver disponível
    if command -v gio &>/dev/null; then
        gio set "$DESKTOP_DIR/AtmosSplit.desktop" metadata::trusted true 2>/dev/null || true
    fi
    echo "[+] Atalho de 2 cliques instalado na Área de Trabalho: $DESKTOP_DIR/AtmosSplit.desktop"
fi

# 2. Instalar no menu de aplicativos
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cp "$HERE/AtmosSplit.desktop" "$APPS_DIR/AtmosSplit.desktop"
chmod +x "$APPS_DIR/AtmosSplit.desktop"
echo "[+] Atalho instalado no menu de aplicativos: $APPS_DIR/AtmosSplit.desktop"
