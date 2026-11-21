"""
AtmosSplit — Subprocesso CLI Desacoplado para Separação de Stems
Roda isolado da interface Qt em nice 19 e afinidade de núcleos segura,
comunicando progresso via JSON no stdout.
"""

from __future__ import annotations

import sys
import os
import json
import argparse
import logging
from pathlib import Path

# Adiciona raiz ao sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from src.separation.process_shield import apply_process_shield


def emit_json(event_type: str, **kwargs):
    payload = {"type": event_type, **kwargs}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="AtmosSplit Background Separation Worker")
    parser.add_argument("--input", required=True, help="Caminho do arquivo de áudio")
    parser.add_argument("--hash", required=True, help="Hash SHA-256 do arquivo")
    parser.add_argument("--mode", default="surgical", choices=["surgical", "fast"], help="Modo de separação")
    args = parser.parse_args()

    # 1. Blindagem de Processo e Afinidade de CPU
    apply_process_shield(reserve_cores=2)
    from src.acquisition.file_source import load_audio_file
    from src.separation.stem_engine import DeepStemEngine

    input_path = Path(args.input)
    if not input_path.exists():
        emit_json("error", message=f"Arquivo não encontrado: {input_path}")
        sys.exit(1)

    try:
        emit_json("progress", value=0.05, message="Lendo amostras do arquivo de áudio...")
        source = load_audio_file(input_path, load_data_now=True)
        if source.audio_data is None:
            emit_json("error", message="Não foi possível decodificar dados de áudio.")
            sys.exit(1)

        if source.sha256_hash != args.hash:
            raise ValueError("O arquivo de origem mudou desde a abertura.")
        engine = DeepStemEngine()

        def progress_cb(pct: float, msg: str):
            emit_json("progress", value=round(pct, 3), message=msg)

        result = engine.separate_track(
            audio_array=source.audio_data,
            sample_rate=source.sample_rate,
            file_hash=args.hash,
            mode=args.mode,
            progress_callback=progress_cb
        )

        emit_json(
            "success",
            file_hash=result.file_hash,
            mode=result.mode,
            elapsed=round(result.elapsed_time_s, 2),
            from_cache=result.from_cache,
            stems_count=len(result.stems)
        )
        sys.exit(0)

    except Exception as ex:
        emit_json("error", message=str(ex))
        sys.exit(1)


if __name__ == "__main__":
    main()
