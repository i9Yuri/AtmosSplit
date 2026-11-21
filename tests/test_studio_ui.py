"""Regressões da estação nativa. Todo o áudio e o cache dos testes são temporários."""

import os
import time
import json

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QSettings, Qt, QTimer
from PySide6.QtWidgets import QApplication

from src.acquisition.file_source import calculate_file_sha256
from src.playback.exporter import ExportFormat
from src.separation.cache_manager import StemCacheManager
from src.ui.main_window import MainWindow
from src.ui.stem_card import StemControlCard
from src.ui.studio_jobs import pack_sections, unpack_sections
from src.ui import theme as T


@pytest.fixture
def studio(tmp_path):
    app = QApplication.instance() or QApplication(["studio-offscreen"])
    cache = StemCacheManager(tmp_path / "cache")
    settings = QSettings(str(tmp_path/"settings.ini"), QSettings.IniFormat)
    win = MainWindow(cache, settings, session_dir=tmp_path/"sessions")
    win.resize(1920, 1000)
    win.show()
    app.processEvents()
    yield win, app
    win.close()
    _wait(win, app)
    win.deleteLater()
    app.processEvents()


def _wait(win, app):
    deadline = time.monotonic() + 45
    while win._task is not None and time.monotonic() < deadline:
        app.processEvents(QEventLoop.AllEvents, 20)
        time.sleep(0.008)
    assert win._task is None, win.status_label.text()
    app.processEvents()


def test_empty_studio_fits_and_cancels_without_stale_process(studio, tmp_path):
    win, app = studio
    assert win.minimumSizeHint().width() <= 1366
    assert win.btn_open.isEnabled()
    assert not win.btn_play.isEnabled() and not win.export_btn.isEnabled()
    assert win.timeline_widget.lbl_active_info.text() == ""
    assert not win.timeline_widget.canvas.has_session
    assert win.room_view.width() > win.source_list.width()
    win._load_and_process_audio_path(str(tmp_path/"ausente.wav"))
    assert win.cancel_btn.isVisible() and not win.btn_open.isEnabled()
    win._cancel()
    _wait(win, app)
    assert "cancelada" in win.status_label.text().lower()
    assert not win.current_stems and win._proc is None
    win._load_and_process_audio_path(str(tmp_path/"ausente.wav"))
    _wait(win, app)
    assert "arquivo" in win.status_label.text().lower()
    assert win.btn_open.isEnabled() and win.status_label.property("error")


def test_studio_cached_file_edit_clone_render_and_restore(studio, tmp_path):
    win, app = studio
    rate = 24000
    t = np.arange(rate*2, dtype=np.float32)/rate
    voice = np.repeat((.18*np.sin(2*np.pi*1400*t))[:, None], 2, axis=1)
    other = np.repeat((.06*np.sin(2*np.pi*400*t))[:, None], 2, axis=1)
    wav = tmp_path/"Sessão curta.wav"
    sf.write(wav, voice + other, rate)
    digest = calculate_file_sha256(wav)
    win.cache_manager.save_stems(digest, "fast", {"vocals": voice, "other": other}, {}, rate)
    win.combo_mode.setCurrentIndex(win.combo_mode.findData("fast"))
    heartbeat = []
    timer = QTimer(win)
    timer.timeout.connect(lambda: heartbeat.append(time.monotonic()))
    timer.start(15)
    win._load_and_process_audio_path(str(wav))
    _wait(win, app)
    assert len(heartbeat) >= 2
    assert win.current_stems, win.status_label.text()
    assert win.live_player.total_duration_s == pytest.approx(2)
    assert win.btn_play.isEnabled() and win.export_btn.isEnabled()
    assert win.source_list.count() == 2
    assert "Confiança" in win.timeline_widget.lbl_active_info.text()
    assert win.timeline_widget.lbl_features.text() == win.timeline_manager.sections[0].description
    win._choose_source("vocals")
    win._inspector.btn_clone.click()
    assert win.room_view.active_stem_name == "vocals::2"
    win._inspector.slider_z.setValue(53)
    win._inspector.slider_spread.setValue(42)
    win._inspector.btn_mute.click()
    assert win.current_placements["vocals::2"].z == pytest.approx(.53)
    assert win.current_placements["vocals::2"].is_muted
    assert not win.current_placements["vocals"].is_muted
    win._seek(.8)
    win.timeline_widget.btn_split.click()
    assert win.timeline_manager.get_active_edit_section().start_time_s == pytest.approx(.8)
    data = pack_sections(win.timeline_manager.sections)
    assert pack_sections(unpack_sections(data)) == data
    win._save_arrangement()
    assert (tmp_path/"sessions"/f"{digest}_fast.json").is_file()
    out = tmp_path/"Master.wav"
    win._export(out, ExportFormat.WAV_714)
    _wait(win, app)
    assert out.exists(), win.status_label.text()
    assert sf.info(out).channels == 12 and sf.info(out).duration == pytest.approx(2)
    assert "LUFS" in win.status_label.text() and "dBTP" in win.status_label.text()
    win._load_and_process_audio_path(str(wav))
    _wait(win, app)
    assert "restaurada" in win.status_label.text().lower()
    assert pack_sections(win.timeline_manager.sections) == data
    win._choose_source("vocals::2")
    win._inspector.btn_delete.click()
    assert "vocals::2" not in win.current_placements
    assert all(item.data(Qt.UserRole) != "vocals::2" for item in win.source_list.findItems("", Qt.MatchContains))
    win.combo_profile.setCurrentIndex(win.combo_profile.findData("studio"))
    _wait(win, app)
    assert win.live_player.profile == "studio" and win.settings.value("monitor/profile") == "studio"
    # Reedições não empilham inspetores nem somam ganhos de uma publicação anterior.
    original = win.current_placements["vocals"].volume_gain
    for _ in range(16):
        win._choose_source("vocals")
        win._inspector.slider_z.setValue(25)
        win._inspector.slider_z.setValue(0)
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert len(win.findChildren(StemControlCard)) == 1
    assert win.current_placements["vocals"].volume_gain == pytest.approx(original)
    timer.stop()


def test_closing_during_preview_preparation_keeps_event_loop_available(studio):
    from threading import Event

    win, app = studio
    started, release = Event(), Event()
    def prepare():
        started.set()
        release.wait(3)
    win._task = "profile"
    win._thread_job(prepare, lambda data: pytest.fail("Resultado cancelado não pode ser publicado"))
    try:
        assert started.wait(1)
        assert not win.close()
        assert win.isVisible() and win._thread.isInterruptionRequested()
        events = []
        QTimer.singleShot(0, lambda: events.append(True))
        app.processEvents()
        assert events and not release.is_set()
    finally:
        release.set()
    _wait(win, app)
    assert not win.isVisible() and win._thread is None


def test_cancel_reaps_worker_descendants(studio, tmp_path, monkeypatch):
    import sys
    import psutil
    from PySide6.QtCore import QProcess
    from src.ui import main_window

    win, app = studio
    marker = tmp_path/"child-pid"
    class Worker(QProcess):
        def setArguments(self, args):
            program = ("from pathlib import Path\nimport subprocess, sys, time\n"
                       "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
                       "Path(sys.argv[1]).write_text(str(child.pid))\ntime.sleep(20)\n")
            super().setArguments([*args[:2], "-c", program, str(marker)])
    monkeypatch.setattr(main_window, "QProcess", Worker)
    win._load_and_process_audio_path(str(tmp_path/"mock.wav"))
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    try:
        assert marker.exists()
        child = psutil.Process(int(marker.read_text()))
        win._cancel()
        _wait(win, app)
        assert not child.is_running()
    finally:
        if win._task:
            win._cancel()
            _wait(win, app)


def _micro_session(studio, tmp_path):
    """Faixa vocal de três notas curtas e dois eventos locais com rotas conhecidas."""
    from src.spatial.auto_director import DirectorPreset, SpatialPlacement
    from src.spatial.micro_events import SpatialEvent
    from src.spatial.timeline_manager import SpatialTimelineManager

    win, _ = studio
    rate = 24_000
    t = np.arange(2*rate, dtype="f") / rate
    voice = np.zeros_like(t)
    for start in (.3, .57, .84):
        mask = (t >= start) & (t < start+.13)
        voice[mask] = .28*np.sin(2*np.pi*1200*t[mask]) * np.hanning(np.count_nonzero(mask))
    voice = np.repeat(voice[:, None], 2, axis=1)
    other = np.repeat((.04*np.sin(2*np.pi*440*t))[:, None], 2, axis=1)
    wav = tmp_path/"Frase.wav"
    sf.write(wav, voice+other, rate)
    digest = calculate_file_sha256(wav)
    win.cache_manager.save_stems(digest, "fast", {"vocals": voice, "other": other}, {}, rate)
    win.combo_mode.setCurrentIndex(win.combo_mode.findData("fast"))
    tl = SpatialTimelineManager(2., {
        "vocals": SpatialPlacement("vocals", 0, 1, 0, 0, 0, 1),
        "other": SpatialPlacement("other", .7, .95, 0, 0, 0, .8, is_stereo=True),
    })
    sec = tl.sections[0]
    sec.name = "Refrão editado"
    sec.section_type = "chorus"
    sec.micro_events = (
        SpatialEvent(.28, .73, .018, .06, "vocals", "throw", .70, -1, .05, .60, -.60, .94, 1.10, .10, 0, .94, .70),
        SpatialEvent(1.30, 1.55, .012, .04, "other", "motif", -.85, .10, .18, -.72, -.78, .48, .59, .22, 0, .84, .70),
    )
    data = {"version": 1, "preset": DirectorPreset.BALANCED.value, "intensity": 70,
            "manual": False, "sections": pack_sections(tl.sections)}
    win.session_dir.mkdir(parents=True)
    path = win.session_dir / f"{digest}_fast.json"
    path.write_text(json.dumps(data), encoding="utf8")
    return wav, path, sec.micro_events


def test_micro_event_lane_room_bypass_and_render(studio, tmp_path, monkeypatch, native_output):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolTip

    win, app = studio
    wav, path, events = _micro_session(studio, tmp_path)
    win._load_and_process_audio_path(str(wav))
    _wait(win, app)
    lane = win.timeline_widget.canvas.micro_lane
    assert lane.isVisible() and lane.count == 2, win.status_label.text()
    pos = QPoint(round(lane.canvas.time_to_x(.4)), 6)
    QTest.mouseClick(lane, Qt.LeftButton, pos=pos)
    assert win.live_player.current_time_s == pytest.approx(.298, abs=1/48000)
    assert win.room_view.micro_events == (events[0],)
    assert "Projeção vocal" in win.event_caption.text()
    assert "BL + BR" in win.event_caption.toolTip() and "TBL + TBR" in win.event_caption.toolTip()
    QCoreApplication.sendEvent(lane, QHelpEvent(QEvent.ToolTip, pos, lane.mapToGlobal(pos)))
    assert "Confiança 94%" in QToolTip.text()
    QToolTip.hideText()
    key = "vocals::micro"
    pose = win.room_view.projections[key]
    assert key not in win.room_view.stems and key not in win.current_placements
    active = win.room_view.active_stem_name
    pixel = win.room_view._get_node_positions(abs(pose.x), pose.y, pose.z)[1].toPoint()
    QTest.mousePress(win.room_view, Qt.LeftButton, pos=pixel)
    assert not win.room_view._is_dragging
    QTest.mouseRelease(win.room_view, Qt.LeftButton, pos=pixel)
    win.room_view._move(key, 0., 1., 0.)
    assert pose.y < -.9 and win.room_view.active_stem_name == active
    QTest.keyClick(lane, Qt.Key_Right)
    assert "Motivo" in win.event_caption.text()
    QTest.keyClick(lane, Qt.Key_Left)
    assert win.room_view.micro_events == (events[0],)
    on = tmp_path/"Com projeção.wav"
    off = tmp_path/"Sem projeção.wav"
    win._export(on, ExportFormat.WAV_714)
    _wait(win, app)
    assert on.is_file(), win.status_label.text()
    wet = np.empty((4000, 12), "f")
    offset = round(.315*48_000)
    win.live_player._dsp_state.plan.mix(offset, wet)
    win.timeline_widget.btn_micro.click()
    assert not win.timeline_manager.sections[0].micro_enabled
    assert lane.count == 2 and not lane.active_at(.4)
    assert not win.room_view.projections and not win.event_caption.text()
    dry = np.empty_like(wet)
    win.live_player._dsp_state.plan.mix(offset, dry)
    assert np.linalg.norm(wet[:, 4:6]) > np.linalg.norm(dry[:, 4:6]) + .02
    win._export(off, ExportFormat.WAV_714)
    _wait(win, app)
    assert off.is_file(), win.status_label.text()
    rendered_on, sr = sf.read(on, dtype="float32")
    rendered_off, _ = sf.read(off, dtype="float32")
    assert sr == 48_000 and rendered_on.shape == rendered_off.shape
    segment = slice(offset, offset+len(wet))
    assert np.linalg.norm(rendered_on[segment, 4:6]) > np.linalg.norm(rendered_off[segment, 4:6]) + .02
    win._load_and_process_audio_path(str(wav))
    _wait(win, app)
    assert not win.timeline_widget.btn_micro.isChecked()
    assert not json.loads(path.read_text())["sections"][0]["micro_enabled"]
    assert win.timeline_manager.sections[0].micro_events == events
    win.intensity.setValue(0)
    win.btn_direct.click()
    _wait(win, app)
    sec = win.timeline_manager.sections[0]
    assert not sec.micro_enabled and len(sec.micro_events) == 2
    assert all(ev.intensity == 0 for ev in sec.micro_events)
    win.timeline_widget.btn_micro.click()
    win._seek(.4)
    assert not win.room_view.projections
    win.intensity.setValue(92)
    win.btn_direct.click()
    _wait(win, app)
    assert win.room_view.projections[key].volume_gain > 0
    assert win.timeline_manager.sections[0].micro_events[0].intensity == pytest.approx(.92)
    # Alimenta o cursor com blocos efetivamente consumidos pelo callback nativo.
    # O modo de movimento reduzido conserva o marcador e uma legenda legível após a sílaba.
    player = win.live_player
    win._seek(.67)
    consume = native_output(player)
    output = np.empty((player.block_size, 2), "f")
    with monkeypatch.context() as patch:
        patch.setattr(player, "_is_playing", True)
        win.reduced_motion.setChecked(True)
        for _ in range(5):
            assert player._produce(player._transport, player._dsp_state, player.binaural)
            consume(output)
            win._poll_audio_state()
            if player.current_time_s < .73:
                assert key in win.room_view.projections and "Projeção vocal" in win.event_caption.text()
            else:
                assert not win.room_view.projections and win.event_caption.text().startswith("Anterior")
    win._poll_audio_state()
    assert not win.event_caption.text()


def test_legacy_session_discovers_micro_events_once_and_keeps_manual_edit(studio, tmp_path):
    win, app = studio
    wav, path, _ = _micro_session(studio, tmp_path)
    data = json.loads(path.read_text())
    sec = data["sections"][0]
    del sec["micro_events"], sec["micro_enabled"]
    sec["placements"]["other"]["y"] = -.42
    data["manual"] = True
    path.write_text(json.dumps(data))
    win._load_and_process_audio_path(str(wav))
    _wait(win, app)
    section = win.timeline_manager.sections[0]
    assert win.session.get("micro_migrated"), win.status_label.text()
    assert win._manual and section.name == "Refrão editado" and section.placements["other"].y == -.42
    assert any(ev.kind == "syllable" for ev in section.micro_events)
    win._save_arrangement()
    saved = json.loads(path.read_text())
    assert saved["sections"][0]["micro_events"]
    # Uma lista vazia explícita representa uma detecção sem eventos e não reabre o detector.
    saved["sections"][0]["micro_events"] = []
    path.write_text(json.dumps(saved))
    win._load_and_process_audio_path(str(wav))
    _wait(win, app)
    assert not win.session.get("micro_migrated") and win._manual
    assert win.timeline_manager.sections[0].micro_events == ()


def test_theme_toggle_amoled_and_light(studio):
    win, app = studio
    assert win._current_theme in ("amoled", "light")
    initial_theme = win._current_theme
    other_theme = "light" if initial_theme == "amoled" else "amoled"

    # Alterna via botão discreto no cabeçalho
    win.btn_theme.click()
    app.processEvents()
    assert win._current_theme == other_theme
    assert T.CURRENT_THEME == other_theme
    assert win.settings.value("ui/theme") == other_theme
    assert ("Claro" if other_theme == "light" else "AMOLED") in win.btn_theme.text()

    # Alterna de volta via ação do menu de sessão
    win.theme_action.trigger()
    app.processEvents()
    assert win._current_theme == initial_theme
    assert T.CURRENT_THEME == initial_theme
    assert win.settings.value("ui/theme") == initial_theme
