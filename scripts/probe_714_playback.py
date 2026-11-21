#!/usr/bin/env python3
"""Gera a identificação dos canais pela mesma cadeia de entrega usada no estúdio."""

import argparse
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

CHANNEL_NAMES_714 = [
    ("FL",  "Frontal Esquerdo",        440.0),   # A4
    ("FR",  "Frontal Direito",         554.37),  # C#5
    ("FC",  "Frontal Central",         659.25),  # E5
    ("LFE", "Subwoofer (LFE Grave)",    50.0),   # 50 Hz sub-bass
    ("BL",  "Traseiro Esquerdo",       330.0),   # E4
    ("BR",  "Traseiro Direito",        392.0),   # G4
    ("SL",  "Lateral Esquerdo",        493.88),  # B4
    ("SR",  "Lateral Direito",         587.33),  # D5
    ("TFL", "Teto Frontal Esquerdo",   880.0),   # A5 (Agudo para teto)
    ("TFR", "Teto Frontal Direito",   1046.50),  # C6
    ("TBL", "Teto Traseiro Esquerdo",  783.99),  # G5
    ("TBR", "Teto Traseiro Direito",   987.77)   # B5
]


def generate_714_channel_check(output_dir: Path, sr: int = 48000, step_seconds: float = 2.) -> None:
    from src.separation.process_shield import apply_process_shield
    apply_process_shield()
    import numpy as np
    from src.playback.exporter import AudioExporter714, ExportFormat

    if not .25 <= step_seconds <= 10:
        raise ValueError("Escolha entre 0,25 e 10 segundos por canal.")
    samples = round(sr * step_seconds)
    matrix = np.zeros((len(CHANNEL_NAMES_714)*samples, 12), dtype="f")
    t = np.arange(samples) / sr
    # Três pulsos com entrada e saída suaves. Pico de −20 dBFS.
    env = np.sin(np.pi*np.clip((t/step_seconds-.04)/.91, 0, 1))**2
    env *= np.sin(3*np.pi*t/step_seconds)**2
    for index, (code, name, hz) in enumerate(CHANNEL_NAMES_714):
        matrix[index*samples:(index+1)*samples, index] = .1*np.sin(2*np.pi*hz*t)*env
        print(f"{index*samples/sr:6.2f} s   {code:4}   {name}")
    for fmt, extension in ((ExportFormat.MP4_ATMOS_JOC_714, "mp4"),
                           (ExportFormat.MKV_LPCM_714, "mkv"), (ExportFormat.WAV_714, "wav")):
        path = output_dir / f"calibracao_jbl_714.{extension}"
        AudioExporter714.export(matrix, path, sr, fmt)
        print(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=_ROOT / "tests" / "multichannel_diagnostics")
    parser.add_argument("--step-seconds", type=float, default=2.)
    args = parser.parse_args()
    generate_714_channel_check(args.output_dir, step_seconds=args.step_seconds)
