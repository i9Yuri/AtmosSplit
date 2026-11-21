"""Projeções temporárias medidas na sala, no PCM e no bitstream decodificado."""

import subprocess
from dataclasses import replace
import ac3forge
import numpy as np
import pytest

from src.playback.exporter import AudioExporter714, ExportFormat
from src.separation.stem_engine import StemTrack
from src.spatial.auto_director import SpatialPlacement
from src.spatial.binaural_hrtf import BinauralHRTFEngine
from src.spatial.live_player import LiveSpatialPlayer
from src.spatial.master_renderer import MasterRenderer714, RenderConfig
from src.spatial.micro_events import detect_micro_events
from src.spatial.timeline_manager import SpatialSection, SpatialTimelineManager

SR = 24000


def phrase_mix():
    t = np.arange(12*SR)/SR
    def bursts(name, notes):
        x = np.zeros_like(t)
        for at,duration,hz,amplitude in notes:
            u = t-at
            mask = (u >= 0) & (u < duration)
            envelope = np.minimum(1, np.minimum(u[mask], duration-u[mask])/.012)
            x[mask] += amplitude*np.sin(2*np.pi*hz*u[mask])*envelope
        return StemTrack(name, name, "#EEEEEE", x.astype("f")[:,None], SR)
    return [
        bursts("lead_vocal", [(at,.14,1350,.13) for at in (1.02,1.27,1.52)] +
               [(3.02,.72,890,.12),(6.06,1.00,1450,.19),(9.16,.52,720,.08)]),
        bursts("backing_vocals", [(3.91,.19,890,.105)]),
        bursts("snare", [(at,.085,550,.1) for at in (4.5,4.63,4.76)]),
        bursts("cymbals_hihat", [(6.1,.44,3720,.1)]),
        bursts("sub_bass_lfe", [(6.62,.40,55,.19)]),
        bursts("guitar_keys", [(6.,1.91,260,.06)]),
    ]


def session():
    stems = phrase_mix()
    poses = {s.name: SpatialPlacement(s.name,0.,1.,0.,0.,float(s.name=="sub_bass_lfe"),1.) for s in stems}
    sections = [SpatialSection(str(i),typ,a,b,poses.copy(),section_type=typ,tempo_bpm=120,beats_per_bar=4)
                for i,(typ,a,b) in enumerate([("verse",0.,6.),("climax",6.,12.)])]
    detect_micro_events(stems,sections,intensity=1.)
    tm = SpatialTimelineManager(12.,poses)
    tm.set_sections(sections)
    return stems,tm


def test_syllables_response_throw_fill_and_downbeat():
    _,tm=session()
    events = [e for s in tm.sections for e in s.micro_events]
    def selected(kind):
        return [e for e in events if e.kind==kind]
    syl=selected("syllable")
    assert [e.start_s for e in syl] == pytest.approx([1.27,1.52],abs=.015)
    assert syl[0].x>0>syl[1].x
    assert selected("response")[0].start_s == pytest.approx(3.91,abs=.015)
    assert selected("throw")[0].stem=="lead_vocal" and selected("throw")[0].start_s>6.
    assert selected("fill")[0].start_s == pytest.approx(4.5,abs=.02)
    assert selected("crash")[0].start_s == pytest.approx(6.1,abs=.02)
    assert selected("sub_drop")[0].start_s == pytest.approx(6.62,abs=.025)
    for when,side in [(1.33,1),(1.59,-1)]:
        poses=tm.get_interpolated_placements(when)
        assert poses["lead_vocal"].y==1 and side*poses["lead_vocal::micro"].x>.5
    for when in (.5,1.09,2.0,3.4,9.45):
        assert "lead_vocal::micro" not in tm.get_interpolated_placements(when)


def test_continuous_verse_and_irregular_dissimilar_notes_stay_anchored():
    stems,tm = session()
    t = np.arange(6*SR)/SR
    waves = np.zeros_like(t)
    for at,d,f in [(0.,1.7,560),(2.,.16,220),(2.21,.14,1600),(2.72,.16,5100)]:
        mask = (t>=at)&(t<at+d)
        waves[mask] = .12*np.sin(2*np.pi*f*t[mask])
    lead = replace(stems[0],audio_data=waves.astype("f"))
    detect_micro_events([lead],tm.sections[:1])
    assert not tm.sections[0].micro_events


def test_micro_render_monitor_and_joc_decode(tmp_path, native_output):
    stems,tm=session()
    cfg=RenderConfig(sample_rate=SR,apply_limiter=False,apply_lufs_norm=False,profile="studio")
    renderer=MasterRenderer714()
    def pcm():
        return renderer.render_to_multichannel_714(stems,tm.sections[0].placements,cfg,tm)
    mix=pcm()
    for sec in tm.sections:
        sec.micro_enabled=False
    base=pcm()
    for sec in tm.sections:
        sec.micro_enabled=True
    delta=mix-base
    def rms(arr): return np.sqrt(np.mean(arr**2))
    for a,b,ch in [(1.32,1.37,5),(1.56,1.62,4),(3.95,4.01,5),(6.34,6.42,4),(6.72,6.8,3)]:
        assert rms(delta[round(a*SR):round(b*SR), ch])>.009, (a,ch)
    for a,b in [(1.,1.16),(2.,2.50),(3.02,3.72),(9.18,9.58)]:
        np.testing.assert_allclose(mix[round(a*SR):round(b*SR)],base[round(a*SR):round(b*SR)], atol=1e-6)
    for a,b in [(1.,1.75),(3.0,4.15),(6.26,7.)]:
        np.testing.assert_allclose(mix[round(a*SR):round(b*SR),2],base[round(a*SR):round(b*SR),2],atol=.0008)
    player=LiveSpatialPlayer(SR,512,profile="studio")
    player.set_stems_and_placements(stems,tm.sections[0].placements)
    player.set_timeline_manager(tm)
    consume=native_output(player)
    output=np.empty((len(mix),2),"f")
    for i in range(0,len(mix),512):
        assert player._produce(player._transport,player._dsp_state,player.binaural)
        consume(output[i:i+512])
    np.testing.assert_allclose(output,BinauralHRTFEngine(SR).process_714_to_binaural(mix),atol=1e-6)
    delivery=AudioExporter714.export_verified(mix,tmp_path/"events.mp4",SR,ExportFormat.MP4_ATMOS_JOC_714)
    assert delivery.joc.decoded_true_peak_dbtp <= -1.
    raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(delivery.path),"-map","0:a",
                                 "-c","copy","-f","eac3","pipe:1"])
    decoder=ac3forge.Eac3Decoder()
    units=[decoder.decode_access_unit(frame) for frame in ac3forge.split_access_units(raw)]
    objects=np.concatenate([np.asarray(u.object_audio).T for u in units])
    bed=np.concatenate([np.asarray(u.channels).T for u in units])
    def power(arr,ch,a,b,hz):
        x=arr[round(a*48000):round(b*48000),ch]
        return 2*abs(np.mean(x*np.exp(-2j*np.pi*hz*np.arange(len(x))/48000)))
    # OAM de BL/BR nos índices 3/4, TFL/TFR/TBL/TBR nos 7 a 10.
    for a,b,hz,ch in [(1.32,1.38,1350,4),(1.56,1.63,1350,3),(3.95,4.04,890,4),
                       (6.34,6.42,1450,3),(6.16,6.23,3720,7),(6.37,6.43,3720,10)]:
        assert power(objects,ch,a,b,hz)>.015, (a,ch)
    assert power(bed,units[0].channel_labels.index("LFE"),6.7,6.84,55)>.10
    assert power(bed,units[0].channel_labels.index("C"),6.7,6.84,55)<.008


def test_harmonic_offbeats_swell_and_bass_accent():
    duration = 8.
    t = np.arange(int(SR*duration))/SR
    def instrument(name, wave):
        return StemTrack(name,name,"#cccccc",wave.astype("f"),SR)
    notes = np.zeros_like(t)
    for a,hz in ((1.25,420),(1.5,660),(1.75,520),(2.,880)):
        idx = (t>=a)&(t<a+.16)
        notes[idx] = .18*np.sin(2*np.pi*hz*t[idx])
    air = .16*np.clip((t-3.02)/.9,0,1)*np.clip((4.2-t)/.18,0,1)*np.sin(2*np.pi*3500*t)
    bass = .23*((t>5.51)&(t<5.75))*np.sin(2*np.pi*140*t)
    stems = [instrument("guitar_keys",notes), instrument("air_ambience",air), instrument("melodic_bass",bass)]
    s = SpatialSection("verse","Verso",0.,duration,{},section_type="verse",tempo_bpm=120,downbeats_s=(0,2,4,6))
    detect_micro_events(stems,[s],1.)
    kinds={e.kind:e for e in s.micro_events}
    assert {"motif","swell","bass_accent"} == kinds.keys()
    assert kinds["swell"].end_s-kinds["swell"].start_s>.5
    assert kinds["bass_accent"].lfe_send == 0
    assert kinds["motif"].start_s == pytest.approx(1.25,abs=.03)
