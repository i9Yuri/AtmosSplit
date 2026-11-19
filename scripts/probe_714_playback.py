#!/usr/bin/env python3
"""
scripts/probe_714_playback.py
Gera arquivos de teste de diagnóstico de 12 canais (Dolby Atmos 7.1.4)
e avalia a compatibilidade de layouts e codecs no Linux -> eARC -> JBL Bar 1000MK2.
"""

import sys
import os
import json
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
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

def generate_714_channel_check(output_dir: Path, sr: int = 48000):
    import numpy as np
    import soundfile as sf

    output_dir.mkdir(parents=True, exist_ok=True)
    num_channels = 12
    step_duration_s = 2.0  # 2 segundos por canal
    total_duration_s = step_duration_s * num_channels
    total_samples = int(total_duration_s * sr)

    data = np.zeros((total_samples, num_channels), dtype=np.float32)

    print(f"[*] Gerando matriz multicanal 7.1.4 (12 canais, {total_duration_s:.1f}s, {sr}Hz)...")
    for ch_idx, (code, name, freq) in enumerate(CHANNEL_NAMES_714):
        start_sample = int(ch_idx * step_duration_s * sr)
        end_sample = int((ch_idx + 1) * step_duration_s * sr)
        ch_samples = end_sample - start_sample
        t = np.linspace(0, step_duration_s, ch_samples, endpoint=False)

        # Tom senoidal com envelope em sino e pulsos de identificação
        env = np.sin(np.pi * np.linspace(0, 1, ch_samples))
        # 3 bips distintos dentro dos 2 segundos
        beep_mod = (np.sin(2 * np.pi * 3.0 * t) > 0.0).astype(np.float32)
        signal = np.sin(2 * np.pi * freq * t) * env * (0.6 + 0.4 * beep_mod)
        
        # Para LFE, tom puro de 50 Hz com alto ganho sem clipping
        if code == "LFE":
            signal = np.sin(2 * np.pi * 50.0 * t) * env * 0.9

        data[start_sample:end_sample, ch_idx] = signal.astype(np.float32) * 0.85
        print(f"    - Canal {ch_idx+1:2d} ({code:3s}): {name:24s} [{freq:6.1f} Hz]")

    # 1. WAV 12 Canais descompactado
    wav_path = output_dir / "test_714_channels.wav"
    sf.write(str(wav_path), data, sr, subtype="PCM_24")
    print(f"[+] Arquivo WAV 12ch gerado: {wav_path} ({round(os.path.getsize(wav_path)/(1024*1024), 2)} MB)")

    # 2. Formato A: MKV com LPCM 7.1.4 e Layout Canônico via FFmpeg
    # Layout 7.1.4: FL+FR+FC+LFE+BL+BR+SL+SR+TFL+TFR+TBL+TBR
    mkv_lpcm_path = output_dir / "test_714_lpcm.mkv"
    cmd_mkv = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=24:r=24",
        "-i", str(wav_path),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "pcm_s24le", "-channel_layout", "7.1.4",
        "-shortest", str(mkv_lpcm_path)
    ]
    try:
        subprocess.check_call(cmd_mkv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Formato A (MKV LPCM 7.1.4): {mkv_lpcm_path} ({round(os.path.getsize(mkv_lpcm_path)/(1024*1024), 2)} MB)")
    except Exception as e:
        print(f"[!] Erro ao gerar MKV LPCM 7.1.4: {e}")

    # 3. Formato B: FLAC 12 Canais MKA
    mka_flac_path = output_dir / "test_714_flac.mka"
    cmd_flac = [
        "ffmpeg", "-y", "-i", str(wav_path),
        "-c:a", "flac",
        str(mka_flac_path)
    ]
    try:
        subprocess.check_call(cmd_flac, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Formato B (FLAC 12ch MKA): {mka_flac_path} ({round(os.path.getsize(mka_flac_path)/(1024*1024), 2)} MB)")
    except Exception as e:
        print(f"[!] Erro ao gerar FLAC MKA: {e}")

    # 4. Formato C: TrueHD 7.1 (Discreto 8 canais de alta fidelidade)
    # Teto mapeado com matriz nas caixas surround para upmixing pelo MultiBeam da JBL Bar 1000
    mkv_truehd_path = output_dir / "test_71_truehd.mkv"
    cmd_truehd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=24:r=24",
        "-i", str(wav_path),
        "-filter_complex", "[1:a]pan=7.1|FL=c0|FR=c1|FC=c2|LFE=c3|BL=c4+0.7*c10|BR=c5+0.7*c11|SL=c6+0.7*c8|SR=c7+0.7*c9[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "truehd", "-strict", "-2",
        "-shortest", str(mkv_truehd_path)
    ]
    try:
        subprocess.check_call(cmd_truehd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Formato C (TrueHD 7.1 com matriz de altura): {mkv_truehd_path} ({round(os.path.getsize(mkv_truehd_path)/(1024*1024), 2)} MB)")
    except Exception as e:
        print(f"[!] Erro ao gerar TrueHD: {e}")

    # 5. Formato D: E-AC-3 7.1 (Dolby Digital Plus 7.1 a 1024 kbps - máxima compatibilidade eARC Samsung)
    mkv_eac3_path = output_dir / "test_71_eac3.mkv"
    cmd_eac3 = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=24:r=24",
        "-i", str(wav_path),
        "-filter_complex", "[1:a]pan=7.1|FL=c0|FR=c1|FC=c2|LFE=c3|BL=c4+0.7*c10|BR=c5+0.7*c11|SL=c6+0.7*c8|SR=c7+0.7*c9[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "eac3", "-b:a", "1024k",
        "-shortest", str(mkv_eac3_path)
    ]
    try:
        subprocess.check_call(cmd_eac3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Formato D (E-AC-3 7.1 1024k): {mkv_eac3_path} ({round(os.path.getsize(mkv_eac3_path)/(1024*1024), 2)} MB)")
    except Exception as e:
        print(f"[!] Erro ao gerar E-AC-3: {e}")

    # Auditar via ffprobe
    audit_results = {}
    for p in [wav_path, mkv_lpcm_path, mka_flac_path, mkv_truehd_path, mkv_eac3_path]:
        if p.exists():
            try:
                probe = subprocess.check_output([
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_streams", "-show_format", str(p)
                ], text=True)
                audit_results[p.name] = json.loads(probe)
            except Exception as ex:
                audit_results[p.name] = {"error": str(ex)}

    with open(output_dir / "probe_714_results.json", "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Auditoria ffprobe salva em: {output_dir / 'probe_714_results.json'}")

if __name__ == "__main__":
    generate_714_channel_check(_ROOT / "tests" / "multichannel_diagnostics")
