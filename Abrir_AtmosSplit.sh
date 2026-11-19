#!/usr/bin/env bash
# Duplo clique para executar o AtmosSplit com UI amigável
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/iniciar.sh" "$@"
