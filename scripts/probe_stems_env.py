#!/usr/bin/env python3
"""
scripts/probe_stems_env.py
Auditoria e benchmark empírico de separação de stems no hardware alvo:
- CPU: Intel Xeon E5-2667 v2 (8c/16t, AVX, Ivy Bridge-EP)
- GPU: AMD Radeon RX 580 2048SP (Polaris, gfx803, 8GB VRAM)
- SO: Nobara Linux (KDE Plasma, Wayland + PipeWire)
"""

import sys
import os
import time
import json
import psutil
import shutil
import subprocess
from pathlib import Path

# Add project root to path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

def audit_system_environment():
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": sys.version,
        "executable": sys.executable,
        "cpu": {},
        "gpu": {},
        "ffmpeg": {},
        "packages": {}
    }

    # CPU Information
    report["cpu"]["count_logical"] = psutil.cpu_count(logical=True)
    report["cpu"]["count_physical"] = psutil.cpu_count(logical=False)
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line:
                    report["cpu"]["model_name"] = line.split(":", 1)[1].strip()
                    break
    except Exception as e:
        report["cpu"]["model_name"] = str(e)

    # Memory
    mem = psutil.virtual_memory()
    report["memory"] = {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2)
    }

    # GPU / Vulkan check
    try:
        lspci = subprocess.check_output(["lspci", "-k"], text=True)
        gpu_lines = [l for l in lspci.splitlines() if "VGA" in l or "Radeon" in l]
        report["gpu"]["pci"] = gpu_lines
    except Exception as e:
        report["gpu"]["pci_error"] = str(e)

    try:
        vk = subprocess.check_output(["vulkaninfo", "--summary"], text=True, stderr=subprocess.DEVNULL)
        report["gpu"]["vulkan_summary"] = [l.strip() for l in vk.splitlines() if "deviceName" in l or "driverName" in l]
    except Exception as e:
        report["gpu"]["vulkan_error"] = str(e)

    # FFmpeg & Codecs
    try:
        ff = subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0]
        report["ffmpeg"]["version"] = ff
        layouts = subprocess.check_output(["ffmpeg", "-layouts"], text=True)
        has_714 = "7.1.4" in layouts
        report["ffmpeg"]["supports_7_1_4_layout"] = has_714
        
        enc = subprocess.check_output(["ffmpeg", "-encoders"], text=True)
        report["ffmpeg"]["encoders"] = {
            "flac": "flac" in enc,
            "pcm_s24le": "pcm_s24le" in enc,
            "truehd": "truehd" in enc,
            "eac3": "eac3" in enc,
            "libfdk_aac": "libfdk_aac" in enc,
            "libopus": "libopus" in enc
        }
    except Exception as e:
        report["ffmpeg"]["error"] = str(e)

    # Packages check
    pkgs = ["torch", "torchaudio", "demucs", "soundfile", "scipy", "numpy", "librosa", "PySide6", "mutagen"]
    for p in pkgs:
        try:
            mod = __import__(p)
            ver = getattr(mod, "__version__", "installed")
            report["packages"][p] = {"status": "ok", "version": str(ver)}
        except Exception as err:
            report["packages"][p] = {"status": "error", "error": str(err)}

    # PyTorch Hardware / Acceleration Analysis
    try:
        import torch
        report["torch_info"] = {
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_count": torch.cuda.device_count(),
            "cpu_threads": torch.get_num_threads(),
            "cpu_capability": torch.backends.cpu.get_cpu_capability()
        }
        # Hardware diagnosis
        if not torch.cuda.is_available():
            report["hardware_recommendation"] = (
                "Radeon RX 580 (Polaris / gfx803) sem suporte ROCm upstream padrão no Linux. "
                "Execução em CPU Intel Xeon E5-2667 v2 (8c/16t a 3.30 GHz) com nice=19 e ionice=idle "
                "proporciona máxima estabilidade sem risco de GPU ring hang no KDE Plasma Wayland."
            )
        else:
            report["hardware_recommendation"] = "Aceleração GPU disponível."
    except Exception as e:
        report["torch_info"] = {"error": str(e)}

    return report


def generate_synthetic_polyphonic_test_audio(output_wav: Path, duration_s: float = 30.0, sr: int = 44100):
    """
    Gera um áudio de teste de 30s com camadas polifônicas distintas para benchmarking:
    - Bumbo (Kick): transitório percussivo senoidal com sweep descendente de 150 Hz -> 40 Hz a cada batida (120 BPM).
    - Caixa (Snare): rajada de ruído filtrado em 200-5000 Hz nas batidas 2 e 4.
    - Pratos (Hi-hat/Shakers): ruído passa-alta > 7000 Hz em semicolcheias.
    - Baixo (Bass): onda dente-de-serra filtrada em 55-180 Hz com linha de baixo.
    - Voz simulada (Vocals): formantes centrados em 300, 1000, 2500 Hz modulados por vibrato de 5 Hz.
    - Piano / Guitarra: acordes harmônicos com decaimento exponencial.
    """
    import numpy as np
    import soundfile as sf

    num_samples = int(duration_s * sr)
    t = np.linspace(0, duration_s, num_samples, endpoint=False)
    audio = np.zeros((num_samples, 2), dtype=np.float32)

    bpm = 120
    beat_duration = 60.0 / bpm
    total_beats = int(duration_s / beat_duration)

    # 1. Bumbo (Kick) no tempo 1 e 3
    kick = np.zeros(num_samples, dtype=np.float32)
    kick_len = int(0.25 * sr)
    t_kick = np.linspace(0, 0.25, kick_len, endpoint=False)
    env_kick = np.exp(-15 * t_kick)
    freq_kick = 50 + 100 * np.exp(-30 * t_kick)
    sig_kick = np.sin(2 * np.pi * freq_kick * t_kick) * env_kick

    # 2. Caixa (Snare) no tempo 2 e 4
    snare = np.zeros(num_samples, dtype=np.float32)
    snare_len = int(0.20 * sr)
    t_snare = np.linspace(0, 0.20, snare_len, endpoint=False)
    env_snare = np.exp(-18 * t_snare)
    noise_snare = (np.random.rand(snare_len) * 2 - 1).astype(np.float32) * env_snare * 0.7
    tone_snare = np.sin(2 * np.pi * 180 * t_snare) * env_snare * 0.3
    sig_snare = noise_snare + tone_snare

    # 3. Hi-Hat a cada 1/2 tempo
    hihat = np.zeros(num_samples, dtype=np.float32)
    hh_len = int(0.06 * sr)
    t_hh = np.linspace(0, 0.06, hh_len, endpoint=False)
    env_hh = np.exp(-50 * t_hh)
    sig_hh = (np.random.rand(hh_len) * 2 - 1).astype(np.float32) * env_hh * 0.35

    for b in range(total_beats):
        pos = int(b * beat_duration * sr)
        if b % 2 == 0:  # Kick
            end_pos = min(pos + kick_len, num_samples)
            kick[pos:end_pos] += sig_kick[:end_pos - pos] * 0.8
        else:           # Snare
            end_pos = min(pos + snare_len, num_samples)
            snare[pos:end_pos] += sig_snare[:end_pos - pos] * 0.7

        # Hi-hat na cabeça do tempo e no contratempo
        end_pos_hh = min(pos + hh_len, num_samples)
        hihat[pos:end_pos_hh] += sig_hh[:end_pos_hh - pos] * 0.4
        off_pos = pos + int(0.5 * beat_duration * sr)
        if off_pos < num_samples:
            end_off = min(off_pos + hh_len, num_samples)
            hihat[off_pos:end_off] += sig_hh[:end_off - off_pos] * 0.3

    # 4. Baixo harmônico (Bass line)
    bass = np.zeros(num_samples, dtype=np.float32)
    bass_freqs = [65.41, 65.41, 82.41, 73.42]  # C2, C2, E2, D2
    for b in range(total_beats):
        f0 = bass_freqs[b % len(bass_freqs)]
        pos = int(b * beat_duration * sr)
        dur = int(beat_duration * 0.85 * sr)
        end_pos = min(pos + dur, num_samples)
        t_note = np.linspace(0, (end_pos - pos) / sr, end_pos - pos, endpoint=False)
        env_note = (1.0 - np.exp(-30 * t_note)) * np.exp(-2.5 * t_note)
        sig_note = (np.sin(2 * np.pi * f0 * t_note) +
                    0.5 * np.sin(2 * np.pi * f0 * 2 * t_note) +
                    0.25 * np.sin(2 * np.pi * f0 * 3 * t_note)) * env_note
        bass[pos:end_pos] += sig_note.astype(np.float32) * 0.55

    # 5. Voz simulada (Formantes vocais)
    vocal = np.zeros(num_samples, dtype=np.float32)
    vocal_notes = [220.0, 261.63, 293.66, 329.63]  # A3, C4, D4, E4
    for b in range(0, total_beats, 2):
        f0 = vocal_notes[(b // 2) % len(vocal_notes)]
        pos = int(b * beat_duration * sr)
        dur = int(beat_duration * 1.9 * sr)
        end_pos = min(pos + dur, num_samples)
        t_voc = np.linspace(0, (end_pos - pos) / sr, end_pos - pos, endpoint=False)
        vibrato = 1.0 + 0.015 * np.sin(2 * np.pi * 5.0 * t_voc)
        env_voc = np.sin(np.pi * np.linspace(0, 1, end_pos - pos))
        # Formantes A: ~800 Hz, ~1200 Hz, ~2800 Hz
        sig_voc = (np.sin(2 * np.pi * f0 * vibrato * t_voc) * 0.4 +
                   np.sin(2 * np.pi * 800.0 * t_voc) * 0.35 +
                   np.sin(2 * np.pi * 1200.0 * t_voc) * 0.2 +
                   np.sin(2 * np.pi * 2800.0 * t_voc) * 0.1) * env_voc
        vocal[pos:end_pos] += sig_voc.astype(np.float32) * 0.65

    # 6. Piano / Guitarra harmônica (Chords)
    chords = np.zeros(num_samples, dtype=np.float32)
    chord_freqs = [
        [261.63, 329.63, 392.00],  # C major
        [220.00, 261.63, 329.63],  # A minor
        [174.61, 220.00, 261.63],  # F major
        [196.00, 246.94, 293.66],  # G major
    ]
    for b in range(0, total_beats, 4):
        c_freq = chord_freqs[(b // 4) % len(chord_freqs)]
        pos = int(b * beat_duration * sr)
        dur = int(beat_duration * 3.8 * sr)
        end_pos = min(pos + dur, num_samples)
        t_c = np.linspace(0, (end_pos - pos) / sr, end_pos - pos, endpoint=False)
        env_c = np.exp(-1.2 * t_c)
        sig_c = sum(np.sin(2 * np.pi * freq * t_c) for freq in c_freq) * env_c * (0.3 / len(c_freq))
        chords[pos:end_pos] += sig_c.astype(np.float32)

    # Montagem Estéreo com Panning realista
    # Centro: Kick, Snare, Bass, Vocal
    # Laterais: Hi-hat (35% R), Chords (40% L/R)
    audio[:, 0] = kick * 0.7 + snare * 0.6 + bass * 0.6 + vocal * 0.7 + hihat * 0.2 + chords * 0.6
    audio[:, 1] = kick * 0.7 + snare * 0.6 + bass * 0.6 + vocal * 0.7 + hihat * 0.4 + chords * 0.4

    # Normalizar para evitar clipping
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = (audio / peak) * 0.92

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_wav), audio, sr, subtype="PCM_24")
    return output_wav


def run_benchmark():
    print("=" * 60)
    print("ATMOSSPLIT — FASE 0: BENCHMARK EMPÍRICO DE IA & AMBIENTE")
    print("=" * 60)

    env_report = audit_system_environment()
    print(f"[*] CPU: {env_report['cpu'].get('model_name', 'Unknown')}")
    print(f"[*] Threads Lógicas: {env_report['cpu'].get('count_logical')}")
    print(f"[*] RAM Total: {env_report.get('memory', {}).get('total_gb')} GB")
    print(f"[*] GPU: {env_report['gpu'].get('vulkan_summary')}")
    print(f"[*] Suporte FFmpeg Layout 7.1.4: {env_report['ffmpeg'].get('supports_7_1_4_layout')}")
    print(f"[*] Diagnóstico Hardware: {env_report.get('hardware_recommendation')}")

    # Gerar áudio de teste de 30s
    benchmark_dir = _ROOT / "tests" / "benchmark_data"
    test_wav = benchmark_dir / "test_polyphonic_30s.wav"
    
    print("\n[*] Gerando áudio de teste polifônico de 30s...")
    try:
        generate_synthetic_polyphonic_test_audio(test_wav, duration_s=30.0, sr=44100)
        print(f"[+] Áudio gerado em: {test_wav} ({round(os.path.getsize(test_wav)/(1024*1024), 2)} MB)")
    except Exception as e:
        print(f"[!] Erro ao gerar áudio com soundfile: {e}")
        return env_report

    # Teste de Estágio 2: Sub-divisão cirúrgica DSP (Zero latência, CPU otimizada)
    print("\n[*] Testando Estágio 2 (Sub-Divisão Cirúrgica de Frequência & Crossover)...")
    import numpy as np
    import soundfile as sf
    from scipy import signal

    data, sr = sf.read(str(test_wav))
    t0 = time.time()
    mem_before = psutil.Process().memory_info().rss / (1024 * 1024)

    # 1. Crossover de Sub-Grave puro LFE (< 80 Hz Linkwitz-Riley 4th order)
    sos_lp = signal.butter(4, 80.0, btype='lowpass', fs=sr, output='sos')
    sos_hp = signal.butter(4, 80.0, btype='highpass', fs=sr, output='sos')
    sub_lfe = signal.sosfiltfilt(sos_lp, data, axis=0)
    melodic_bass = signal.sosfiltfilt(sos_hp, data, axis=0)

    # 2. Decomposição Mid / Side para isolar Vocal Principal no centro vs. Coro/Ambiência nos lados
    mid = 0.5 * (data[:, 0] + data[:, 1])
    side = 0.5 * (data[:, 0] - data[:, 1])

    # 3. Isolamento de Pratos / Chocalhos / Frequências Aéreas (> 6000 Hz) para Teto
    sos_air = signal.butter(4, 6000.0, btype='highpass', fs=sr, output='sos')
    air_layer = signal.sosfiltfilt(sos_air, data, axis=0)

    t1 = time.time()
    mem_after = psutil.Process().memory_info().rss / (1024 * 1024)
    dsp_time = t1 - t0
    dsp_mem = mem_after - mem_before

    print(f"[+] Sub-divisão cirúrgica DSP concluída em {dsp_time:.3f} s (RAM delta: {dsp_mem:.2f} MB)")
    env_report["benchmark_dsp"] = {
        "execution_time_s": round(dsp_time, 3),
        "memory_delta_mb": round(dsp_mem, 2),
        "stems_extracted": ["sub_lfe_80hz", "melodic_bass", "mid_center_vocal", "side_ambience", "air_highs_ceiling"]
    }

    # Salvar relatório JSON intermediário
    output_report_json = _ROOT / "ENVIRONMENT_REPORT.json"
    with open(output_report_json, "w", encoding="utf-8") as f:
        json.dump(env_report, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Relatório de sondagem salvo em: {output_report_json}")

    return env_report

if __name__ == "__main__":
    run_benchmark()
