"""Testes de áudio medem amostras, recorrência e sinais decodificados."""

import ac3forge
import numpy as np
import pytest
from scipy import signal

from src.playback.exporter import AudioExporter714, ExportFormat
from src.separation.stem_engine import StemTrack, split_surgical
from src.spatial.auto_director import DirectorPreset, SpatialPlacement
from src.spatial.binaural_hrtf import BinauralHRTFEngine
from src.spatial.live_player import LiveSpatialPlayer
from src.spatial.master_renderer import MasterRenderer714, RenderConfig
from src.spatial.metering import true_peak
from src.spatial.music_structure import analyze_structure
from src.spatial.song_intelligence import SongStructureIntelligence
from src.spatial.timeline_manager import SpatialTimelineManager


def track(name, audio, rate):
    return StemTrack(name, name, "#88CCBB", audio.astype("f"), rate)


def song(bpm=120, meter=4):
    """Quatro frases A/B/A/B com compassos em quantidades distintas, B reaparece no fim."""
    sr = 12000
    beat = round(sr*60/bpm)
    pickup = round(sr*.14)
    bars = np.array([0, 3, 8, 12, 16])
    edges = pickup+bars*beat*meter
    n = edges[-1]
    x = np.arange(n)/sr
    harmony = np.zeros((n, 2))
    vocal = np.zeros(n)
    drums = np.zeros(n)
    for i, (start, end) in enumerate(zip(edges, edges[1:])):
        xt = x[start:end]
        if i % 2:
            harmony[start:end, 0] = .19*(np.sin(2*np.pi*330*xt)+.7*np.sin(2*np.pi*494*xt))
            harmony[start:end, 1] = .18*(np.sin(2*np.pi*392*xt)+.7*np.sin(2*np.pi*494*xt))
            vocal[start:end] = .16*np.sin(2*np.pi*960*xt)
        else:
            harmony[start:end] = (.08*np.sin(2*np.pi*196*xt))[:, None]
            vocal[start:end] = .03*np.sin(2*np.pi*620*xt)
        for j, k in enumerate(range(start, end, beat)):
            u = np.arange(min(1000, n-k))/sr
            gain = .78 if j % meter == 0 else .22
            drums[k:k+len(u)] = gain*np.exp(-u*44)*np.sin(2*np.pi*85*u)
    stems = [track("lead_vocal", vocal[:, None], sr), track("guitar_keys", harmony, sr),
             track("kick", drums[:, None], sr)]
    return stems, n/sr, edges[1:-1]/sr, harmony+(vocal+drums)[:, None]


@pytest.mark.parametrize("bpm,meter", [(120, 4), (100, 3)])
def test_recurring_phrases_snap_to_observed_downbeats(bpm, meter):
    stems, duration, expected, mix = song(bpm, meter)
    sections = SongStructureIntelligence.analyze_and_arrange(stems, duration, mix_audio=mix, mix_sample_rate=12000)
    found = [s.start_time_s for s in sections[1:]]
    assert found == pytest.approx(expected, abs=.12)
    assert sections[-1].end_time_s == duration
    assert sections[0].tempo_bpm == pytest.approx(bpm, abs=3)
    assert sections[0].beats_per_bar == meter
    assert sections[0].family == sections[2].family != sections[1].family
    assert sections[1].family == sections[3].family
    assert sections[1].section_type == "chorus" and sections[3].section_type == "climax"
    for s in sections:
        assert 0 < s.confidence <= 1 and s.description
        assert s.placements["lead_vocal"].y >= .95 and s.placements["lead_vocal"].z == 0
    steady = SongStructureIntelligence.redirect(sections, stems, DirectorPreset.BALANCED, 0.)
    assert steady[0].placements == steady[-1].placements
    assert sections[1].placements["guitar_keys"].z > sections[2].placements["guitar_keys"].z


def test_without_pulse_keeps_real_harmonic_change():
    sr = 8000
    t = np.arange(sr*23)/sr
    changepoint = 11.3
    harmonic = np.where(t < changepoint, np.sin(2*np.pi*200*t), np.sin(2*np.pi*370*t))
    parts, pulse = analyze_structure([track("guitar_keys", harmonic*.15, sr)], len(t)/sr)
    assert pulse.bpm == 0
    assert [s.start for s in parts[1:]] == pytest.approx([changepoint], abs=.35)
    uniform, pulse = analyze_structure([track("guitar_keys", np.zeros_like(t), sr)], len(t)/sr)
    assert len(uniform) == 1 and uniform[0].kind == "uniform" and pulse.bpm == 0


def test_surgical_additive_and_centered_vocal():
    rng = np.random.default_rng(2026)
    macro = {key: rng.normal(0, .08, (16384, 2)).astype("f") for key in ("vocals", "drums", "bass", "other")}
    macro["vocals"][:, 1] = macro["vocals"][:, 0]
    parts = split_surgical(macro, 48000)
    for original, keys in (("vocals", ("lead_vocal", "backing_vocals")), ("bass", ("sub_bass_lfe", "melodic_bass")),
                           ("drums", ("kick", "snare", "cymbals_hihat")), ("other", ("guitar_keys", "air_ambience"))):
        np.testing.assert_allclose(sum(parts[k] for k in keys), macro[original], atol=2e-7)
    np.testing.assert_allclose(parts["lead_vocal"], macro["vocals"])
    assert np.max(np.abs(parts["backing_vocals"])) < 1e-6


def test_mono_and_mirrored_consume_equal_power_and_lfe_is_bandlimited():
    sr = 24000
    t = np.arange(sr)/sr
    sig = .2*np.sin(2*np.pi*1550*t)
    p = SpatialPlacement("other", .72, 1., 0., .3, .9, 1.)
    renderer = MasterRenderer714()
    cfg = RenderConfig(sample_rate=sr, apply_limiter=False, apply_lufs_norm=False, profile="studio")
    stem = track("other", sig, sr)
    mono = renderer.render_to_multichannel_714([stem], {"other": p}, cfg)
    p.is_stereo = True
    stereo = renderer.render_to_multichannel_714([stem], {"other": p}, cfg)
    assert np.sum(stereo**2) / np.sum(mono**2) == pytest.approx(1., abs=.001)
    assert np.abs(stereo[sr//8:, 3]).max() < .0001


def test_vocal_presence_profile_and_linked_true_peak():
    sr = 24000
    t = np.arange(2*sr)/sr
    voice = .14*np.sin(2*np.pi*1650*t)
    music = np.column_stack([.24*np.sin(2*np.pi*f*t)+.12*np.sin(2*np.pi*350*t) for f in (1920, 2120)])
    voice[:sr//2] = 0.
    stems = [track("lead_vocal", voice, sr), track("guitar_keys", music, sr)]
    placement = dict(lead_vocal=SpatialPlacement("lead_vocal", 0, 1, 0, .03, 0, 1),
                     guitar_keys=SpatialPlacement("guitar_keys", .8, .1, .3, .3, 0, 1, is_stereo=True))
    renderer = MasterRenderer714()
    scores = []
    for profile in ("studio", "jbl"):
        mix = renderer.render_to_multichannel_714(stems, placement, RenderConfig(sample_rate=sr, profile=profile))
        report = renderer.last_report
        assert report.integrated_lufs == pytest.approx(-18, abs=.2)
        assert true_peak(mix) <= 10**(-1/20)+.0001
        assert report.vocal_balance_db is not None
        scores.append(report.presence_balance_db)
    assert 1. < scores[1]-scores[0] <= 3.7


def test_true_peak_and_bs1770_gate_excluding_lfe():
    sr = 48000
    t = np.arange(sr)/sr
    # Pico entre amostras, com margem digital aparente de cerca de 3 dB.
    hot = np.zeros((sr, 12), dtype="f")
    hot[:, 2] = 1.19*np.sin(2*np.pi*(sr/4)*t + np.pi/4)
    hot[:, 3] = .6*np.sin(2*np.pi*60*t)
    assert np.max(abs(hot)) < .85 and true_peak(hot) > 1.1
    renderer = MasterRenderer714()
    safe = renderer._apply_transparent_limiter(hot, -1)
    assert true_peak(safe) == pytest.approx(10**(-1/20), abs=.0002)
    reference = renderer._calculate_k_weighted_lufs(hot)
    hot[:, 3] = 0.
    assert renderer._calculate_k_weighted_lufs(hot) == pytest.approx(reference)
    # A pausa longa altera somente os blocos parciais nas bordas do programa.
    assert renderer._calculate_k_weighted_lufs(np.tile(np.vstack([hot, hot, hot, np.zeros_like(hot)]), (2, 1))) == pytest.approx(reference, abs=.5)


def test_binaural_delay_survives_partial_blocks_and_seek():
    rng = np.random.default_rng(53)
    matrix = .03*rng.standard_normal((5721, 12)).astype("f")
    hrtf = BinauralHRTFEngine()
    expected = hrtf.process_714_to_binaural(matrix)
    hrtf.reset_states()
    actual = np.concatenate([hrtf.process_714_to_binaural(block) for block in np.array_split(matrix, [7, 501, 4000])])
    np.testing.assert_allclose(actual, expected, atol=5e-7)


def test_joc_center_object_and_lfe_bed_remain_discrete(tmp_path):
    sr = 48000
    n = 29*ac3forge.SAMPLES_PER_FRAME
    t = np.arange(n)/sr
    pcm = np.zeros((n, 12), "f")
    pcm[:, 3] = .6*np.sin(2*np.pi*55*t)
    pcm[:, 2] = .32*np.sin(2*np.pi*1550*t)
    pcm[:, 8] = .2*np.sin(2*np.pi*2940*t)
    result = AudioExporter714.export_verified(pcm, tmp_path/"jbl.ec3", sr, ExportFormat.EC3_ATMOS_714)
    assert result.joc.decoded_true_peak_dbtp <= -1.+.001 and result.joc.trim_db <= 0
    path = result.path
    decoder = ac3forge.Eac3Decoder()
    units = [decoder.decode_access_unit(x) for x in ac3forge.split_access_units(path.read_bytes())]
    assert all(len(u.object_audio) == 11 and u.object_metadata.program.lfe for u in units)
    assert all(u.dialnorm == 31 and u.compr is None for u in units)
    recovered = np.concatenate([np.array(u.channels).T for u in units])
    objects = np.concatenate([np.array(u.object_audio).T for u in units])
    assert true_peak(recovered) <= .892 and true_peak(objects) <= .892
    def amplitude(x, hz):
        samples = x[5000:-5000]
        return abs(np.mean(samples*np.exp(-2j*np.pi*hz*np.arange(len(samples))/sr)))*2
    labels = units[0].channel_labels
    center, lfe = recovered[:, labels.index("C")], recovered[:, labels.index("LFE")]
    assert amplitude(center, 1550) > .28 and amplitude(lfe, 55) > .50
    assert amplitude(center, 55) < .005 and amplitude(lfe, 1550) < .002
    # Interoperabilidade do bed em um segundo decoder. FFmpeg escreve os seis
    # canais na ordem WAVE (FL, FR, FC, LFE, SL, SR).
    import subprocess
    wave = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-c:a", "pcm_f32le",
                                    "-f", "f32le", "pipe:1"])
    decoded = np.frombuffer(wave, dtype="<f4").reshape(-1, 6)
    assert amplitude(decoded[:, 2], 1550) > .28 and amplitude(decoded[:, 3], 55) > .50
    assert amplitude(decoded[:, 2], 55) < .005 and amplitude(decoded[:, 3], 1550) < .002
    ratio = 20*np.log10(amplitude(objects[:, 2], 1550)/amplitude(objects[:, 7], 2940))
    assert ratio == pytest.approx(20*np.log10(.32/.2), abs=1.8)


def test_audio_clock_resampling_shared_automation_and_monitors(native_output):
    sr = 48000
    t = np.arange(44100)/44100
    audio = .07*np.sin(2*np.pi*510*t)
    stems = [track("vocals", audio, 44100), track("other", np.column_stack([audio, -audio]), 44100)]
    plcs = {"vocals": SpatialPlacement("vocals", 0, .9, .2, .2, 0, 1),
            "other": SpatialPlacement("other", .7, -.7, .8, .4, .1, .7, is_stereo=True)}
    timeline = SpatialTimelineManager(1., plcs)
    second = timeline.split_section_at(.5)
    second.placements["vocals"].is_solo = True
    second.placements["vocals"].x = -.8
    matrix = MasterRenderer714().render_to_multichannel_714(stems, plcs, RenderConfig(
        sample_rate=sr, apply_limiter=False, apply_lufs_norm=False), timeline)
    expected = BinauralHRTFEngine(sr).process_714_to_binaural(matrix)
    reports = []
    player = LiveSpatialPlayer(sr, 720, on_playback_progress=lambda *args: reports.append(args))
    player.set_stems_and_placements(stems, plcs)
    player.set_timeline_manager(timeline)
    assert len(matrix) == sr and player.total_duration_s == 1.
    player._is_playing = True
    produced = []
    transport = player._transport
    consume = native_output(player)
    while not transport.finished:
        assert player._produce(transport, player._dsp_state, player.binaural)
        frames = min(720, sr-transport.cursor)
        output = np.zeros((frames, 2), "f")
        consume(output)
        produced.append(output)
    np.testing.assert_allclose(np.concatenate(produced), expected, atol=1e-6)
    assert not reports and player.underruns == 0
    assert player.get_ui_snapshot()[0] == 1. and reports == [(1., 1.)]

@pytest.mark.parametrize("right", [-1., 0.])
def test_phase_or_pan_imbalance_preserves_lead_at_center(right):
    sr = 16000
    tone = (.25*np.sin(2*np.pi*1380*np.arange(sr)/sr)).astype("f")
    vocal = np.column_stack([tone, right*tone])
    macro = {k: np.zeros_like(vocal) for k in ("other", "bass", "drums")}
    macro["vocals"] = vocal
    parts = split_surgical(macro, sr)
    np.testing.assert_allclose(parts["lead_vocal"]+parts["backing_vocals"], vocal, atol=1e-7)
    scene = {"lead_vocal": SpatialPlacement("lead_vocal", 0, 1, 0, 0, 0, 1)}
    pcm = MasterRenderer714().render_to_multichannel_714([track("lead_vocal", parts["lead_vocal"], sr)],
            scene, RenderConfig(sample_rate=sr, apply_limiter=False, apply_lufs_norm=False))
    assert np.mean(pcm[:, 2]**2) == pytest.approx(np.mean(vocal**2), rel=.001)
    assert np.max(np.abs(parts["backing_vocals"])) < 1e-6


def test_mux_keeps_last_transient_faststart_and_fractional_duration(tmp_path):
    import subprocess
    sr = 48000
    n = 16*ac3forge.SAMPLES_PER_FRAME
    matrix = np.zeros((n, 12), "f")
    matrix[-80, 2] = .4
    mp4 = AudioExporter714.export(matrix, tmp_path/"tail.mp4", sr, ExportFormat.MP4_ATMOS_JOC_714)
    contents = mp4.read_bytes()
    assert 0 < contents.index(b"moov") < contents.index(b"mdat")
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(mp4), "-map", "0:a:0",
                                   "-c:a", "copy", "-f", "eac3", "pipe:1"])
    dec = ac3forge.Eac3Decoder()
    units = [dec.decode_access_unit(b) for b in ac3forge.split_access_units(raw)]
    out = np.concatenate([u.object_audio[2] for u in units])
    assert n <= len(out) <= n+2*ac3forge.SAMPLES_PER_FRAME
    assert np.max(abs(out[n-100:])) > .2


def test_native_monitor_seek_updates_and_drains_on_device_thread(monkeypatch):
    import threading
    import time
    from src.spatial.native_monitor import ffi
    from src.spatial import live_player

    opened = threading.Event()
    drained = threading.Event()
    closed = threading.Event()
    heard = []
    reports = []

    class DeviceStream:
        def __init__(self, *, callback, userdata, blocksize, **kwargs):
            self.callback, self.userdata = callback, userdata
            self.buffer = np.empty((blocksize//2, 2), dtype="f")
            self.running = True
            assert ffi.typeof(callback).kind == "function"

        def start(self):
            def device():
                while self.running:
                    self.callback(ffi.NULL, ffi.from_buffer("float[]", self.buffer), len(self.buffer),
                                  ffi.NULL, 0, self.userdata)
                    heard.append(float(np.abs(self.buffer).max()))
                    opened.set()
                    time.sleep(.002)
            self.thread = threading.Thread(target=device, daemon=True)
            self.thread.start()

        def stop(self):
            self.running = False
            self.thread.join()
            drained.set()

        def close(self):
            closed.set()

        def abort(self):
            self.running = False
            self.thread.join()

    monkeypatch.setattr(live_player.sd, "_StreamBase", DeviceStream)
    sr = 24000
    tone = .08*np.sin(2*np.pi*514*np.arange(sr)/sr)
    player = LiveSpatialPlayer(sr, block_size=256, on_playback_progress=lambda *_: reports.append(threading.get_ident()))
    p = SpatialPlacement("vocals", 0, 1, 0, .1, 0, 1)
    player.set_stems_and_placements([track("vocals", tone, sr)], {"vocals": p})
    player.play()
    try:
        assert opened.wait(5), player.last_error
        for i in range(15):
            player.update_placement("vocals", .04*i, 1, .01*i)
            player.seek_seconds(.2+i*.013)
            time.sleep(.004)
        assert not reports
        assert drained.wait(5), player.last_error
        assert closed.wait(1)
        assert player.current_time_s == 1.
        assert player.get_ui_snapshot()[0] == 1. and reports == [threading.get_ident()]
        assert max(heard) > .02
    finally:
        player.stop()


def test_editing_preserves_mir_bar_grid_and_proportions():
    stems, length, _, mix = song()
    arrangement = SongStructureIntelligence.analyze_and_arrange(stems, length, mix_audio=mix, mix_sample_rate=12000)
    timeline = SpatialTimelineManager(length)
    timeline.set_sections(arrangement)
    section = timeline.sections[1]
    bars = section.downbeats_s
    split = timeline.split_section_at(bars[2])
    assert split.family == section.family and split.tempo_bpm == section.tempo_bpm
    assert split.placements is not section.placements and split.downbeats_s == bars[2:]
    assert timeline.adjust_boundary(1, bars[2]+.055)
    assert section.downbeats_s+split.downbeats_s == bars
    assert timeline.remove_section(split.id) and section.downbeats_s == bars
    timeline.set_duration(length*.99)
    assert section.downbeats_s == pytest.approx(np.asarray(bars)*.99)
    assert section.tempo_bpm == pytest.approx(120/.99, rel=.02)


def test_native_ring_capacity_partial_reads_and_seek_reclamation():
    import weakref
    from src.spatial.native_monitor import NativePort, NativeRing, ffi
    port = NativePort()
    first = NativeRing(8, 30)
    port.publish(first)
    fifo = np.arange(48, dtype="f").reshape(3,8,2)
    for block in fifo:
        assert first.push(block)
    assert not first.available and not first.push(fifo[0])

    def consume(n):
        out = np.empty((n,2), dtype="f")
        port.lib.monitor_callback(ffi.NULL, ffi.from_buffer("float[]", out), n, ffi.NULL, 0, port.ptr)
        return out
    np.testing.assert_array_equal(consume(5), fifo.reshape(-1,2)[:5])
    actual = consume(22)
    np.testing.assert_array_equal(actual[:19], fifo.reshape(-1,2)[5:])
    assert not actual[19:].any() and first.underruns==1 and first.consumed==24
    old = weakref.ref(first)
    replacement = NativeRing(8,8)
    port.publish(replacement)
    del first
    port.collect()
    assert old() is not None
    assert replacement.push(fifo[2])
    np.testing.assert_array_equal(consume(8), fifo[2])
    port.collect()
    assert old() is None and replacement.consumed==8
