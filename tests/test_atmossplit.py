"""
AtmosSplit — Suíte de Testes Automatizados (pytest)
Cobre ingestão, hash, cache, acústica, VBAP 7.1.4, Live Player, renderização,
exportação, blindagem de hardware e novas melhorias de estabilidade.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
import numpy as np
import soundfile as sf

from src.acquisition.file_source import load_audio_file, calculate_file_sha256, AudioMetadata
from src.acquisition.probe_verifier import verify_audio_file
from src.separation.cache_manager import StemCacheManager
from src.separation.stem_engine import StemTrack
from src.spatial.acoustic_analyzer import AcousticAnalyzer
from src.spatial.auto_director import AutoAtmosDirector, DirectorPreset, SpatialPlacement
from src.spatial.vbap_engine import VBAP714Engine, SPEAKER_COORDINATES_714
from src.spatial.binaural_hrtf import BinauralHRTFEngine
from src.spatial.master_renderer import MasterRenderer714, RenderConfig
from src.spatial.live_player import LiveSpatialPlayer
from src.spatial.timeline_manager import SpatialTimelineManager, SpatialSection
from src.playback.exporter import AudioExporter714, ExportFormat
from src.ui.room_view_714 import RoomView714
from src.ui.timeline_widget import TimelineWidget


@pytest.fixture
def sample_stereo_wav(tmp_path: Path) -> Path:
    """Gera um arquivo WAV estéreo sintético de 2 segundos a 48 kHz."""
    sr = 48000
    duration_s = 2.0
    num_samples = int(duration_s * sr)
    t = np.linspace(0, duration_s, num_samples, endpoint=False)
    
    # Canal L: 440 Hz, Canal R: 880 Hz
    sig_l = np.sin(2 * np.pi * 440.0 * t) * 0.5
    sig_r = np.sin(2 * np.pi * 880.0 * t) * 0.5
    data = np.column_stack([sig_l, sig_r]).astype(np.float32)

    wav_file = tmp_path / "test_stereo.wav"
    sf.write(str(wav_file), data, sr, subtype="PCM_24")
    return wav_file


def test_file_source_and_sha256(sample_stereo_wav: Path):
    """Testa leitura de fonte e determinismo do hash SHA-256."""
    source = load_audio_file(sample_stereo_wav, load_data_now=True)
    assert source.sha256_hash is not None
    assert len(source.sha256_hash) == 64
    assert source.sample_rate == 48000
    assert source.audio_data is not None
    assert source.audio_data.shape[1] == 2
    assert source.metadata.duration_s > 1.9


def test_probe_verifier(sample_stereo_wav: Path):
    """Testa auditoria ffprobe."""
    res = verify_audio_file(sample_stereo_wav)
    assert res.is_valid is True
    assert res.channels == 2
    assert res.sample_rate == 48000
    assert "pcm" in res.codec_name.lower() or "wav" in res.format_name.lower()


def test_stem_cache_manager(tmp_path: Path):
    """Testa salvar e recuperar stems por hash."""
    cache_mgr = StemCacheManager(base_cache_dir=tmp_path / "cache")
    file_hash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    mode = "test_mode"

    sr = 48000
    num_samples = sr
    dummy_stems = {
        "vocals": np.ones((num_samples, 2), dtype=np.float32) * 0.2,
        "drums": np.ones((num_samples, 2), dtype=np.float32) * 0.4,
    }
    meta = {
        "vocals": {"display_name": "Vozes", "color_hex": "#00E5FF"},
        "drums": {"display_name": "Bateria", "color_hex": "#FF9100"},
    }

    assert cache_mgr.has_cached_stems(file_hash, mode) is False

    cache_mgr.save_stems(file_hash, mode, dummy_stems, meta, sample_rate=sr)
    assert cache_mgr.has_cached_stems(file_hash, mode) is True

    loaded = cache_mgr.load_stems(file_hash, mode)
    assert loaded is not None
    assert "vocals" in loaded
    assert "drums" in loaded
    assert loaded["vocals"].shape == (num_samples, 2)
    assert np.allclose(loaded["vocals"], dummy_stems["vocals"], atol=1e-4)


def test_cache_statistics_and_cleanup(tmp_path: Path):
    """Testa cálculo de tamanho em disco e limpeza atômica do cache."""
    cache_mgr = StemCacheManager(base_cache_dir=tmp_path / "cache_stats")
    assert cache_mgr.get_total_cache_size_bytes() == 0
    assert len(cache_mgr.list_cached_tracks()) == 0

    sr = 48000
    num_samples = sr
    stems = {"test": np.ones((num_samples, 2), dtype=np.float32) * 0.1}
    meta = {"test": {"display_name": "Test", "color_hex": "#112233"}}

    cache_mgr.save_stems("hash123", "fast", stems, meta, sr)
    size_bytes = cache_mgr.get_total_cache_size_bytes()
    assert size_bytes > 0
    tracks = cache_mgr.list_cached_tracks()
    assert len(tracks) == 1
    assert tracks[0]["stems_count"] == 1

    freed = cache_mgr.clear_cache()
    assert freed == size_bytes
    assert cache_mgr.get_total_cache_size_bytes() == 0
    assert len(cache_mgr.list_cached_tracks()) == 0


def test_vbap_714_constant_power():
    """Valida a conservação estrita de potência constante (norma L2 = 1.0) no VBAP 7.1.4."""
    vbap = VBAP714Engine()

    test_positions = [
        (0.0, 1.0, 0.0),    # Centro Frente (C)
        (-1.0, 1.0, 0.0),   # Frontal Esquerdo (FL)
        (1.0, 1.0, 0.0),    # Frontal Direito (FR)
        (-1.0, -1.0, 0.0),  # Traseiro Esquerdo (RL)
        (0.0, 0.0, 0.0),    # Centro absoluto da sala
        (-0.5, 0.5, 0.8),   # Posição elevada no teto
        (0.8, -0.4, 0.5),   # Traseiro direito elevado
    ]

    for x, y, z in test_positions:
        gains = vbap.calculate_gains(x, y, z, spread=0.1, lfe_send=0.0)
        assert len(gains) == 12
        # Somatório dos quadrados dos canais satélites (excluindo LFE canal 3) deve conservar potência
        power = sum(gains[i] ** 2 for i in range(12) if i != 3)
        assert power == pytest.approx(1.0, rel=1e-3), f"Falha na conservação de potência para ({x}, {y}, {z})"


def test_acoustic_analyzer_and_auto_director():
    """Valida análise espectral e geração determinística de montagem 7.1.4."""
    sr = 48000
    duration_s = 1.0
    num_samples = int(duration_s * sr)
    t = np.linspace(0, duration_s, num_samples, endpoint=False)

    # 1. Simular bumbo (sub-grave centrado em 60 Hz)
    kick_data = np.sin(2 * np.pi * 60.0 * t) * np.exp(-t * 5.0)
    kick_stereo = np.column_stack([kick_data, kick_data]).astype(np.float32)
    profile_kick = AcousticAnalyzer.analyze_stem("kick", kick_stereo, sr)

    assert profile_kick.sub_bass_energy_ratio > 0.4
    assert profile_kick.spectral_centroid_hz < 300.0

    # 2. Simular voz (médios 300 Hz, mono)
    vocal_data = np.sin(2 * np.pi * 300.0 * t) * 0.4
    vocal_stereo = np.column_stack([vocal_data, vocal_data]).astype(np.float32)
    profile_vocal = AcousticAnalyzer.analyze_stem("lead_vocal", vocal_stereo, sr)

    assert profile_vocal.low_mid_energy_ratio > 0.4
    assert profile_vocal.stereo_width_ratio < 0.1

    # 3. Diretor Automático
    profiles = {"kick": profile_kick, "lead_vocal": profile_vocal}
    placements = AutoAtmosDirector.generate_placements(profiles, DirectorPreset.BALANCED)

    assert "kick" in placements
    assert "lead_vocal" in placements
    assert placements["kick"].lfe_send > 0.5  # Bumbo deve ir para o Subwoofer
    assert placements["lead_vocal"].y > 0.8   # Voz deve ser ancorada na frente (Center)


def test_binaural_hrtf_engine():
    """Valida conversão de 7.1.4 multicanal para estéreo binaural com conservação e continuidade."""
    sr = 48000
    binaural = BinauralHRTFEngine(sample_rate=sr)

    # Criar matriz 12 canais com som apenas no canal Frontal Esquerdo (FL = canal 0)
    num_samples = 2048
    matrix_714 = np.zeros((num_samples, 12), dtype=np.float32)
    matrix_714[:, 0] = np.sin(2 * np.pi * 440.0 * np.linspace(0, 0.1, num_samples)) * 0.5

    stereo_out = binaural.process_714_to_binaural(matrix_714, keep_state=True)
    assert stereo_out.shape == (num_samples, 2)
    # Som no FL deve ter maior energia no canal esquerdo (L) do que no direito (R)
    rms_l = np.sqrt(np.mean(stereo_out[:, 0] ** 2))
    rms_r = np.sqrt(np.mean(stereo_out[:, 1] ** 2))
    assert rms_l > rms_r

    # Testar reset de estados
    binaural.reset_states()


def test_master_renderer_anti_clipping():
    """Valida renderizador mestre: soma coerente, limitador True Peak e sem clipping."""
    sr = 48000
    num_samples = sr
    t = np.linspace(0, 1.0, num_samples, endpoint=False)

    stem1 = StemTrack(
        name="stem1", display_name="S1", color_hex="#FFF",
        audio_data=np.column_stack([np.sin(2 * np.pi * 300 * t), np.sin(2 * np.pi * 300 * t)]).astype(np.float32) * 0.9,
        sample_rate=sr
    )
    stem2 = StemTrack(
        name="stem2", display_name="S2", color_hex="#FFF",
        audio_data=np.column_stack([np.sin(2 * np.pi * 300 * t), np.sin(2 * np.pi * 300 * t)]).astype(np.float32) * 0.9,
        sample_rate=sr
    )

    placements = {
        "stem1": SpatialPlacement("stem1", 0.0, 1.0, 0.0, 0.2, 0.0, volume_gain=1.0),
        "stem2": SpatialPlacement("stem2", 0.0, 1.0, 0.0, 0.2, 0.0, volume_gain=1.0),
    }

    renderer = MasterRenderer714()
    matrix_out = renderer.render_to_multichannel_714(
        [stem1, stem2],
        placements,
        config=RenderConfig(sample_rate=sr, apply_lufs_norm=True)
    )

    assert matrix_out.shape == (num_samples, 12)
    max_peak = np.max(np.abs(matrix_out))
    # True Peak Limiter deve garantir sinal estritamente <= 1.0
    assert max_peak <= 1.0001


def test_live_spatial_player():
    """Valida streaming dinâmico, cache de ganhos e snapshot atômico da GUI."""
    sr = 48000
    player = LiveSpatialPlayer(sample_rate=sr, block_size=1024)

    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    audio = np.column_stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)]).astype(np.float32) * 0.5
    stem = StemTrack(name="lead_vocal", display_name="Vocal", color_hex="#00E5FF", audio_data=audio, sample_rate=sr)

    placements = {
        "lead_vocal": SpatialPlacement("lead_vocal", 0.0, 0.8, 0.1, 0.2, 0.0, 1.0)
    }

    player.set_stems_and_placements([stem], placements)
    assert player.total_duration_s == pytest.approx(2.0, rel=1e-2)
    assert "lead_vocal" in player._cached_vbap_gains

    # Testar snapshot atômico
    cur_s, tot_s, vu_stems, sub_vu, is_p = player.get_ui_snapshot()
    assert tot_s == pytest.approx(2.0, rel=1e-2)
    assert cur_s == 0.0

    # Atualização dinâmica em tempo real
    player.update_placement("lead_vocal", 0.5, -0.5, 0.8)
    assert player.placements["lead_vocal"].z == 0.8

    # Simular seek
    player.seek(0.5)
    assert player.current_time_s == pytest.approx(1.0, rel=1e-2)

    # Testar ajuste de volume
    player.set_volume(0.8)
    assert player._master_volume == 0.8

    # Testar listagem de dispositivos
    devs = LiveSpatialPlayer.get_available_devices()
    assert isinstance(devs, list)


def test_exporter_multichannel_mkv_and_wav(tmp_path: Path):
    """Valida exportação em MKV LPCM 7.1.4 (12 canais) e WAV 12ch com metadados."""
    sr = 48000
    num_samples = sr * 2  # 2 segundos
    matrix_12ch = np.zeros((num_samples, 12), dtype=np.float32)
    for ch in range(12):
        matrix_12ch[:, ch] = np.sin(2 * np.pi * (300 + ch * 50) * np.linspace(0, 2, num_samples)) * 0.3

    # Criar metadados com capa simulada
    meta = AudioMetadata(
        title="Teste Espacial",
        artist="Artista IA",
        album="Álbum 7.1.4",
        cover_image_bytes=b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64  # Fake JPEG header
    )

    # 1. Exportar WAV 12ch
    wav_out = tmp_path / "test_out_12ch.wav"
    AudioExporter714.export(matrix_12ch, wav_out, sr, ExportFormat.WAV_714, metadata=meta)
    assert wav_out.exists()
    info_wav = sf.info(str(wav_out))
    assert info_wav.channels == 12
    assert info_wav.samplerate == sr

    # 2. Exportar MKV LPCM 7.1.4
    mkv_out = tmp_path / "test_out_714.mkv"
    AudioExporter714.export(matrix_12ch, mkv_out, sr, ExportFormat.MKV_LPCM_714, metadata=meta)
    assert mkv_out.exists()
    assert mkv_out.stat().st_size > 10000

    probe = verify_audio_file(mkv_out)
    assert probe.is_valid is True
    assert probe.channels == 12
    assert "pcm" in probe.codec_name.lower()


    # 3. Exportar MP4 Dolby Digital Plus + Dolby Atmos 7.1.4 (E-AC-3 JOC real)
    mp4_out = tmp_path / "test_out_wifi.mp4"
    AudioExporter714.export(matrix_12ch, mp4_out, sr, ExportFormat.MP4_ATMOS_JOC_714, metadata=meta)
    assert mp4_out.exists()
    assert mp4_out.stat().st_size > 10000

    probe_mp4 = verify_audio_file(mp4_out)
    assert probe_mp4.is_valid is True
    assert "eac3" in probe_mp4.codec_name.lower() or "ec-3" in probe_mp4.codec_name.lower()
    assert probe_mp4.is_atmos is True
    assert "atmos" in probe_mp4.profile.lower()
    # Duração deve ser a duração total (2 segundos neste teste sintético, não truncada)
    assert probe_mp4.duration_s >= 1.8

    # 4. Exportar bitstream bruto EC3 Dolby Atmos 7.1.4
    ec3_out = tmp_path / "test_out_atmos.ec3"
    AudioExporter714.export(matrix_12ch, ec3_out, sr, ExportFormat.EC3_ATMOS_714)
    assert ec3_out.exists()
    probe_ec3 = verify_audio_file(ec3_out)
    assert probe_ec3.is_valid is True
    assert probe_ec3.is_atmos is True


def test_exporter_anti_truncation_full_duration(tmp_path: Path):
    """Valida que uma música com mais de 10 segundos NÃO é truncada em 10s."""
    sr = 48000
    duration_s = 16.0  # 16 segundos (> 10s para comprovar correção do bug)
    num_samples = int(duration_s * sr)
    matrix_long = np.zeros((num_samples, 12), dtype=np.float32)
    matrix_long[:, 0] = np.sin(2 * np.pi * 440 * np.linspace(0, duration_s, num_samples)) * 0.2

    mp4_out = tmp_path / "test_long_song.mp4"
    AudioExporter714.export(matrix_long, mp4_out, sr, ExportFormat.MP4_EAC3_71)
    assert mp4_out.exists()

    probe = verify_audio_file(mp4_out)
    assert probe.is_valid is True
    # Duração real deve ser ~16s (e NÃO os 10s antigos!)
    assert probe.duration_s >= 15.5, f"Faixa foi truncada! Duração obtida: {probe.duration_s}s"


def test_room_view_radius_and_selection():
    """Valida projeção 3D pseudo-ortográfica: raio proporcional a Z e seleção de nós."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Validação da fórmula de raio: Z = 0 (11px) e Z = 1 (33px)
    r_floor = RoomView714.get_visual_radius(z=0.0, vu=0.0)
    r_mid = RoomView714.get_visual_radius(z=0.5, vu=0.0)
    r_ceiling = RoomView714.get_visual_radius(z=1.0, vu=0.0)

    assert r_floor == 11.0
    assert r_ceiling == 33.0
    assert r_mid == pytest.approx(22.0, rel=1e-2)
    assert r_ceiling == 3.0 * r_floor  # Exatamente 3x maior no teto!

    # 2. Testar reatividade com widget instanciado
    view = RoomView714()
    dummy_track = StemTrack("lead_vocal", "Voz Principal", "#00E5FF", np.zeros((100, 2)), 48000)
    dummy_plc = SpatialPlacement("lead_vocal", 0.0, 0.8, 0.0, 0.2, 0.0, 1.0)

    view.set_stems_and_placements([dummy_track], {"lead_vocal": dummy_plc})
    assert view.active_stem_name == "lead_vocal"

    ground_pt, sphere_pt = view._get_node_positions(dummy_plc)
    assert ground_pt.y() == sphere_pt.y()  # Em z=0, esfera repousa no chão

    # Elevar para z = 1.0
    dummy_plc.z = 1.0
    ground_pt_elev, sphere_pt_elev = view._get_node_positions(dummy_plc)
    assert sphere_pt_elev.y() < ground_pt_elev.y()  # Em z=1, esfera é elevada verticalmente


def test_process_shield_and_cpu_affinity():
    """Valida blindagem de hardware: afinidade, reserva de núcleos e bloqueio de GPU."""
    from src.separation.process_shield import apply_process_shield, apply_cpu_affinity
    import os
    import psutil

    allowed = apply_cpu_affinity(reserve_cores=2)
    assert len(allowed) > 0
    # Núcleos 0 e 1 não devem estar na lista se a máquina tiver mais de 4 núcleos
    if psutil.cpu_count(logical=True) > 4:
        assert 0 not in allowed
        assert 1 not in allowed

    apply_process_shield(reserve_cores=2)
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert os.environ.get("HIP_VISIBLE_DEVICES") == ""


def test_stereo_mirroring_placement_and_render():
    """Valida espelhamento estéreo (is_stereo): pratos e ambiência balanceados em ambos os lados."""
    sr = 48000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # Sinal de pratos/chimbal em estéreo
    cymbal_l = np.sin(2 * np.pi * 8000.0 * t) * 0.4
    cymbal_r = np.sin(2 * np.pi * 8500.0 * t) * 0.4
    cymbal_audio = np.column_stack([cymbal_l, cymbal_r]).astype(np.float32)

    stem_cymbal = StemTrack("cymbals", "Pratos & Chocalhos", "#FFD700", cymbal_audio, sr)

    # 1. Posição padrão gerada pelo AutoAtmosDirector deve ter is_stereo = True
    profile = AcousticAnalyzer.analyze_stem("cymbals", cymbal_audio, sr)
    placements = AutoAtmosDirector.generate_placements({"cymbals": profile}, DirectorPreset.BALANCED)
    plc = placements["cymbals"]

    assert plc.is_stereo is True
    assert plc.z > 0.7  # Canais de teto ativados
    assert abs(plc.x) > 0.3  # Posição lateral surround

    # 2. Renderizar com MasterRenderer714 e checar equilíbrio energético L e R
    renderer = MasterRenderer714()
    matrix = renderer.render_to_multichannel_714([stem_cymbal], placements, RenderConfig(sample_rate=sr, apply_lufs_norm=False))

    # Canais 7.1.4:
    # FL=0, FR=1, C=2, LFE=3, BL=4, BR=5, SL=6, SR=7, TFL=8, TFR=9, TBL=10, TBR=11
    left_energy = np.sum(matrix[:, [0, 4, 6, 8, 10]] ** 2)
    right_energy = np.sum(matrix[:, [1, 5, 7, 9, 11]] ** 2)

    assert left_energy > 0
    assert right_energy > 0
    # O balanço estéreo deve ser equilibrado (não apenas no lado direito!)
    ratio = min(left_energy, right_energy) / max(left_energy, right_energy)
    assert ratio > 0.75, f"Desbalanceamento estéreo excessivo! Ratio L/R: {ratio}"


def test_spatial_timeline_manager_split_and_interpolation():
    """Valida divisão de trechos (split), renomeação e interpolação Hermite contínua."""
    init_placements = {
        "vocals": SpatialPlacement("vocals", x=0.0, y=0.9, z=0.1, spread=0.1, lfe_send=0.0, volume_gain=1.0)
    }
    mgr = SpatialTimelineManager(total_duration_s=120.0, initial_placements=init_placements)
    assert len(mgr.sections) == 1
    assert mgr.sections[0].name == "Música Completa"

    # 1. Dividir em t = 40s (ex: Refrão)
    sec_refrao = mgr.split_section_at(40.0, new_name="Refrão")
    assert sec_refrao is not None
    assert len(mgr.sections) == 2
    assert mgr.sections[0].end_time_s == 40.0
    assert mgr.sections[1].start_time_s == 40.0
    assert mgr.sections[1].end_time_s == 120.0

    # Modificar o posicionamento das vozes no Refrão: mandar para o fundo e teto!
    sec_refrao.placements["vocals"].y = -0.8
    sec_refrao.placements["vocals"].z = 0.9

    # 2. Testar interpolação suave na fronteira (t = 39.5s a 40.5s)
    # Em t = 10s: deve ser o verso frontal original (y = 0.9, z = 0.1)
    p_verse = mgr.get_interpolated_placements(10.0)["vocals"]
    assert p_verse.y == pytest.approx(0.9, rel=1e-3)
    assert p_verse.z == pytest.approx(0.1, rel=1e-3)

    # Em t = 60s: deve ser o refrão no fundo (y = -0.8, z = 0.9)
    p_chorus = mgr.get_interpolated_placements(60.0)["vocals"]
    assert p_chorus.y == pytest.approx(-0.8, rel=1e-3)
    assert p_chorus.z == pytest.approx(0.9, rel=1e-3)

    # Exatamente na fronteira de transição (t = 40.0s): deve estar no meio do caminho sem saltos
    p_mid = mgr.get_interpolated_placements(40.0)["vocals"]
    assert -0.8 < p_mid.y < 0.9
    assert 0.1 < p_mid.z < 0.9

    # 3. Renomear e Excluir
    mgr.rename_section(sec_refrao.id, "Refrão Épico")
    assert mgr.get_section_by_id(sec_refrao.id).name == "Refrão Épico"

    # Excluir a seção criada
    assert mgr.remove_section(sec_refrao.id) is True
    assert len(mgr.sections) == 1
    assert mgr.sections[0].end_time_s == 120.0


def test_master_renderer_dynamic_timeline():
    """Valida que MasterRenderer714 renderiza automação dinâmica ao longo do tempo."""
    sr = 48000
    duration_s = 4.0
    num_samples = int(duration_s * sr)
    t = np.linspace(0, duration_s, num_samples, endpoint=False)
    vocal_audio = np.column_stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)]).astype(np.float32) * 0.4
    stem_vocal = StemTrack("lead_vocal", "Vocal", "#00E5FF", vocal_audio, sr)

    init_plcs = {
        "lead_vocal": SpatialPlacement("lead_vocal", x=0.0, y=0.9, z=0.1, spread=0.1, lfe_send=0.0, volume_gain=1.0)
    }
    timeline_mgr = SpatialTimelineManager(total_duration_s=duration_s, initial_placements=init_plcs)
    # Dividir no meio (t = 2.0s) e mover o vocal para a traseira esquerda no trecho 2
    sec2 = timeline_mgr.split_section_at(2.0, "Parte 2")
    sec2.placements["lead_vocal"].x = -0.7
    sec2.placements["lead_vocal"].y = -0.7

    renderer = MasterRenderer714()
    matrix = renderer.render_to_multichannel_714(
        [stem_vocal],
        init_plcs,
        config=RenderConfig(sample_rate=sr, apply_lufs_norm=False),
        timeline_manager=timeline_mgr
    )

    assert matrix.shape == (num_samples, 12)
    # Na primeira metade (t < 2.0s), canal Center (canal 2) e Frontais devem dominar
    first_half = matrix[:int(1.5 * sr), :]
    center_energy_1 = np.sum(first_half[:, 2] ** 2)
    rear_energy_1 = np.sum(first_half[:, 4] ** 2)
    assert center_energy_1 > rear_energy_1

    # Na segunda metade (t > 2.5s), satélite traseiro esquerdo (BL = canal 4) deve dominar
    second_half = matrix[int(2.5 * sr):, :]
    center_energy_2 = np.sum(second_half[:, 2] ** 2)
    rear_energy_2 = np.sum(second_half[:, 4] ** 2)
    assert rear_energy_2 > center_energy_2


def test_room_view_stereo_pucks_and_toggle():
    """Valida interação visual com nós estéreo gêmeos e toggle de espelhamento."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    view = RoomView714()

    stem = StemTrack("cymbals", "Pratos", "#FFD700", np.zeros((100, 2)), 48000)
    plc = SpatialPlacement("cymbals", x=0.6, y=0.0, z=0.8, spread=0.4, lfe_send=0.0, volume_gain=1.0, is_stereo=True)

    view.set_stems_and_placements([stem], {"cymbals": plc})

    # 1. Hit testing deve detectar nós L e R
    pt_l = view._room_to_widget_coords(-0.6, 0.0)
    target_l = view._find_stem_at_pos(pt_l)
    assert target_l is not None
    assert target_l[0] == "cymbals"
    assert target_l[1] == "L"

    pt_r = view._room_to_widget_coords(0.6, 0.0)
    target_r = view._find_stem_at_pos(pt_r)
    assert target_r is not None
    assert target_r[0] == "cymbals"
    assert target_r[1] == "R"

    # 2. Testar alternância de espelhamento estéreo
    assert plc.is_stereo is True
    view.toggle_stereo_mirror("cymbals")
    assert plc.is_stereo is False

    view.toggle_stereo_mirror("cymbals")
    assert plc.is_stereo is True


def test_exporter_etsi_ts_103_420_coordinates(tmp_path: Path):
    """
    Valida que a codificação Dolby Atmos E-AC-3 JOC via ac3forge segue estritamente
    a norma ETSI TS 103 420 (§4.2.1) para os 12 canais 7.1.4:
    - X: 0.0 (Esq), 0.5 (Centro), 1.0 (Dir)
    - Y: 0.0 (Frente / TV), 0.5 (Laterais/Ouvinte), 1.0 (Traseira)
    - Z: 0.0 (Ouvido), 1.0 (Teto)
    Comprova que a Voz / Centro (Obj 2) NÃO sai mais no módulo traseiro esquerdo!
    """
    import ac3forge

    sr = 48000
    spf = ac3forge.SAMPLES_PER_FRAME
    matrix_12ch = np.zeros((spf, 12), dtype=np.float32)
    # Sinal no canal Center (canal 2)
    matrix_12ch[:, 2] = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.032, spf)) * 0.5

    temp_ec3 = tmp_path / "test_etsi.ec3"
    AudioExporter714._encode_eac3_joc_stream(matrix_12ch, temp_ec3, sample_rate=sr, bitrate_kbps=768)
    assert temp_ec3.exists()

    with open(temp_ec3, "rb") as f:
        stream_bytes = f.read()

    dec = ac3forge.Eac3Decoder()
    unit = dec.decode_access_unit(stream_bytes[:3072])
    assert unit is not None
    assert unit.object_metadata is not None
    objs = unit.object_metadata.objects
    assert len(objs) == 12

    # Obj 0: Frontal Esquerdo (FL) -> x=0.0, y=0.0, z=0.0
    assert objs[0].position.x == pytest.approx(0.0, abs=0.05)
    assert objs[0].position.y == pytest.approx(0.0, abs=0.05)
    assert objs[0].position.z == pytest.approx(0.0, abs=0.05)

    # Obj 1: Frontal Direito (FR) -> x=1.0, y=0.0, z=0.0
    assert objs[1].position.x == pytest.approx(1.0, abs=0.05)
    assert objs[1].position.y == pytest.approx(0.0, abs=0.05)

    # Obj 2: FRONTAL CENTRAL (FC - Lead Vocal) -> x=0.5, y=0.0 (FRENTE E CENTRO!)
    assert objs[2].position.x == pytest.approx(0.5, abs=0.05), "FC deve estar no centro (x=0.5)!"
    assert objs[2].position.y == pytest.approx(0.0, abs=0.05), "FC deve estar na parede frontal (y=0.0), NÃO na traseira!"

    # Obj 4: Traseiro Esquerdo (BL - Módulo destacável esquerdo) -> x=0.0, y=1.0
    assert objs[4].position.x == pytest.approx(0.0, abs=0.05)
    assert objs[4].position.y == pytest.approx(1.0, abs=0.05)

    # Obj 8: Teto Frontal Esquerdo (TFL) -> x=0.0, y=0.0, z=1.0 (Teto)
    assert objs[8].position.z == pytest.approx(1.0, abs=0.05)


def test_immersion_360_lead_vocal_anchored():
    """
    Valida que no preset IMMERSION_360 (Imersão 360°), a voz principal e o bumbo
    permanecem estritamente ancorados na frente (Center/Front) para foco vocal profissional,
    enquanto instrumentos, harmonias e ambiências criam o campo envolvente 360°.
    """
    sr = 48000
    dummy_audio = np.zeros((sr, 2), dtype=np.float32)

    profiles = {
        "lead_vocal": AcousticAnalyzer.analyze_stem("lead_vocal", dummy_audio, sr),
        "backing_vocals": AcousticAnalyzer.analyze_stem("backing_vocals", dummy_audio, sr),
        "kick": AcousticAnalyzer.analyze_stem("kick", dummy_audio, sr),
        "air_ambience": AcousticAnalyzer.analyze_stem("air_ambience", dummy_audio, sr),
    }

    plcs = AutoAtmosDirector.generate_placements(profiles, DirectorPreset.IMMERSION_360)

    # 1. Lead Vocal DEVE estar ancorado na frente
    assert plcs["lead_vocal"].x == pytest.approx(0.0, abs=0.05)
    assert plcs["lead_vocal"].y >= 0.85
    assert plcs["lead_vocal"].is_stereo is False

    # 2. Bumbo DEVE estar ancorado na frente
    assert plcs["kick"].x == pytest.approx(0.0, abs=0.05)
    assert plcs["kick"].y >= 0.70
    assert plcs["kick"].is_stereo is False

    # 3. Backing Vocals abrem em estéreo envolvente traseiro/lateral
    assert plcs["backing_vocals"].is_stereo is True
    assert plcs["backing_vocals"].y < 0.0

    # 4. Ambiência aérea sobe ao teto com 360°
    assert plcs["air_ambience"].is_stereo is True
    assert plcs["air_ambience"].z >= 0.85


def test_k_weighted_lufs_loudness_and_true_peak():
    """
    Valida o medidor de sonoridade ITU-R BS.1770-4 K-weighting e o limiter True Peak (-1.0 dBTP).
    """
    sr = 48000
    num_samples = sr * 2
    t = np.linspace(0, 2.0, num_samples, endpoint=False)

    # Onda senoidal de 1 kHz a 0 dBFS no canal Center
    matrix = np.zeros((num_samples, 12), dtype=np.float32)
    matrix[:, 2] = np.sin(2 * np.pi * 1000.0 * t) * 0.9

    lufs = MasterRenderer714._calculate_k_weighted_lufs(matrix, sr=sr)
    # 1 kHz a 0.9 peak tem ~ -4.0 a -3.0 LUFS
    assert -10.0 < lufs < 0.0

    renderer = MasterRenderer714()
    # Aplicar normalização para -18 LUFS com teto -1.0 dBTP
    norm_matrix = renderer._apply_integrated_loudness_target(matrix, target_lufs=-18.0, sr=sr)
    limited_matrix = renderer._apply_transparent_limiter(norm_matrix, ceiling_db=-1.0)

    # True peak máximo deve respeitar -1.0 dBTP (10^(-1/20) ~= 0.8913)
    max_peak = float(np.max(np.abs(limited_matrix)))
    assert max_peak <= 0.892, f"Pico excedeu o teto True Peak: {max_peak}"


def test_stem_card_pan_and_quick_position_snaps():
    """Valida controles táteis de Pan, Posição Frente/Trás e botões de 1-Clique na UI."""
    from PySide6.QtWidgets import QApplication
    from src.ui.stem_card import StemControlCard
    import sys

    app = QApplication.instance() or QApplication(sys.argv)

    stem = StemTrack("lead_vocal", "Voz Principal", "#00E5FF", np.zeros((100, 2)), 48000)
    plc = SpatialPlacement("lead_vocal", x=0.0, y=0.9, z=0.0, spread=0.0, lfe_send=0.0, volume_gain=1.0)

    card = StemControlCard(stem, plc)

    # 1. Testar formatação de textos
    assert StemControlCard._format_pan_text(0.0) == "Centro"
    assert "Esq" in StemControlCard._format_pan_text(-0.7)
    assert "Dir" in StemControlCard._format_pan_text(0.7)
    assert StemControlCard._format_pos_y_text(0.9) == "Frente"
    assert StemControlCard._format_pos_y_text(-0.8) == "Trás"

    # 2. Testar snap para Esquerda (Canal Lateral/Frontal Esquerdo)
    card._snap_left()
    assert plc.x == pytest.approx(-0.7, abs=0.01)

    # 3. Testar snap para Direita (Canal Lateral/Frontal Direito)
    card._snap_right()
    assert plc.x == pytest.approx(0.7, abs=0.01)

    # 4. Testar snap para Trás (Satélites Surround Traseiros)
    card._snap_rear()
    assert plc.y == pytest.approx(-0.75, abs=0.01)

    # 5. Testar snap para Centro (Palco / TV Frontal)
    card._snap_center()
    assert plc.x == pytest.approx(0.0, abs=0.01)
    assert plc.y >= 0.90

    # 6. Testar sincronização ultrarrápida de coordenadas
    card.sync_coords_from_placement(-0.5, 0.2, 0.8)
    assert card.slider_pan.value() == -50
    assert card.slider_pos_y.value() == 20
    assert card.slider_z.value() == 80


def test_live_player_crash_proof_and_zero_lock_contention():
    """Valida que o LiveSpatialPlayer calcula ganhos fora da trava e nunca encerra o processo por exceções."""
    sr = 48000
    player = LiveSpatialPlayer(sample_rate=sr)

    stem = StemTrack("vocals", "Voz", "#00E5FF", np.zeros((sr, 2), dtype=np.float32), sr)
    plc = SpatialPlacement("vocals", x=0.0, y=0.9, z=0.0, spread=0.0, lfe_send=0.0, volume_gain=1.0)
    player.set_stems_and_placements([stem], {"vocals": plc})

    # Atualizações em alta frequência (simulando arraste de mouse a 120 Hz) não devem travar
    for i in range(100):
        t = i / 100.0
        player.update_placement("vocals", x=float(np.sin(t)), y=float(np.cos(t)), z=0.5)

    assert "vocals" in player._cached_vbap_gains_l
    assert len(player._cached_vbap_gains_l["vocals"]) == 12

    # Testar callback blindado contra falhas graves
    outdata = np.ones((512, 2), dtype=np.float32)
    # Mesmo com estado inconsistente forçado, o callback não deve propagar exceção
    player._current_sample = 999999999
    player._audio_callback(outdata, 512, None, None)
    # Callback deve zerar outdata e não falhar
    assert np.all(outdata == 0)


def test_lock_free_dsp_and_timeline_crossfade_audio_callback():
    """Valida motor de áudio 100% Lock-Free e crossfade vetorial instantâneo entre seções."""
    from src.spatial.timeline_manager import SpatialTimelineManager
    import threading

    sr = 48000
    player = LiveSpatialPlayer(sample_rate=sr, block_size=1024)

    stems = [
        StemTrack("lead_vocal", "Voz Principal", "#00E5FF", np.ones((sr * 10, 2), dtype=np.float32) * 0.5, sr),
        StemTrack("drums", "Bateria", "#ED8936", np.ones((sr * 10, 2), dtype=np.float32) * 0.3, sr)
    ]
    plcs = {
        "lead_vocal": SpatialPlacement("lead_vocal", 0.0, 0.95, 0.0, 0.0, 0.0, 1.0),
        "drums": SpatialPlacement("drums", 0.5, 0.0, 0.2, 0.2, 0.1, 1.0, is_stereo=True)
    }

    player.set_stems_and_placements(stems, plcs)
    mgr = SpatialTimelineManager(10.0, plcs)
    mgr.split_section_at(5.0)
    # Na seção 2, move vocal para trás à esquerda
    mgr.sections[1].placements["lead_vocal"].x = -0.7
    mgr.sections[1].placements["lead_vocal"].y = -0.5
    player.set_timeline_manager(mgr)

    player._is_playing = True

    # 1. Valida que as seções possuem ganhos pré-calculados
    assert len(mgr.sections[0].cached_gains_l) == 2
    assert len(mgr.sections[1].cached_gains_l) == 2

    # 2. Testa crossfade vetorial direto
    gl_mid, gr_mid = mgr.get_interpolated_gains_at_time(5.0, "lead_vocal")
    assert gl_mid is not None
    assert len(gl_mid) == 12

    # 3. Execução concorrente do callback e atualizações do mouse (sem travas / sem contenção)
    outdata = np.zeros((1024, 2), dtype=np.float32)
    for i in range(20):
        player.update_placement("lead_vocal", x=float(np.sin(i*0.2)), y=float(np.cos(i*0.2)), z=0.3)
        player._audio_callback(outdata, 1024, None, None)
        assert np.any(outdata != 0), "Áudio deve ser gerado continuamente sem bloqueio!"

    player._is_playing = False




