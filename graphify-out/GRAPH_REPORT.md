# Graph Report - AtmosSplit  (2026-11-20)

## Corpus Check
- 55 files · ~54,481 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 880 nodes · 2615 edges · 32 communities (27 shown, 5 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 371 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8bc50146`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main_window.py
- file_source.py
- TimelineTrackCanvas
- SpatialPlacement
- test_music_and_master.py
- 7. Histórico de Versões e Decisões Críticas Recentes
- exporter.py
- MainWindow
- apply_process_shield
- cache_manager.py
- monitor_callback.c
- StemControlCard
- BinauralHRTFEngine
- test_atmossplit.py
- StemCacheManager
- numpy
- NativePort
- numpy
- AtmosSplit — Estúdio de áudio espacial 7.1.4
- cache_manager.py
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh
- search_source.py
- subprocess
- BinauralHRTFEngine
- StemTrack
- Transport
- LiveSpatialPlayer
- stem_engine.py
- test_music_and_master.py
- test_native_monitor_seek_updates_and_drains_on_device_thread

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 84 edges
2. `SpatialPlacement` - 68 edges
3. `RoomView714` - 54 edges
4. `SpatialTimelineManager` - 51 edges
5. `StemTrack` - 50 edges
6. `LiveSpatialPlayer` - 47 edges
7. `MasterRenderer714` - 35 edges
8. `TimelineTrackCanvas` - 34 edges
9. `SpatialEvent` - 33 edges
10. `execute()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `Adicionado & Aprimorado (IA Maestro com Arranjo Estrutural Autônomo, Efeito Vocal Throw 7.1.4 e Timeline Profissional Estilo DAW)` --references--> `MasterRenderer714`  [INFERRED]
  CHANGELOG.md → src/spatial/master_renderer.py
- `3. Da faixa ao arranjo` --references--> `SpatialEvent`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/micro_events.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `AutoAtmosDirector`  [INFERRED]
  CHANGELOG.md → src/spatial/auto_director.py
- `7. Histórico de Versões e Decisões Críticas Recentes` --references--> `BinauralHRTFEngine`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/binaural_hrtf.py
- `Corrigido & Aprimorado (Correção Dimensional do Demucs htdemucs, Anti-Travamento e Menu de Contexto 3D)` --references--> `AudioDSPState`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py

## Import Cycles
- None detected.

## Communities (32 total, 5 thin omitted)

### Community 0 - "main_window.py"
Cohesion: 0.06
Nodes (23): smooth(), SpatialEvent, SpatialSection, SpeakerPosition714, event_details(), event_row(), event_title(), MicroEventLane (+15 more)

### Community 1 - "file_source.py"
Cohesion: 0.15
Nodes (6): AudioSource, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), populate_audio(), test_file_source_and_sha256()

### Community 2 - "TimelineTrackCanvas"
Cohesion: 0.05
Nodes (6): SpatialTimelineManager, TimelineTrackCanvas, TimelineWidget, test_spatial_timeline_manager_split_and_interpolation(), test_timeline_interactive_boundary_drag_and_minimap(), test_timeline_millisecond_zoom_and_ruler()

### Community 3 - "SpatialPlacement"
Cohesion: 0.09
Nodes (9): Adicionado & Aprimorado (Animação 3D em Tempo Real da Sala 7.1.4, Inteligência Cirúrgica de 9 Camadas e Vocal Throw Desbloqueado), Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio), SpatialPlacement, RoomView714, test_cpython_none_refcount_shield_and_zero_paint_leak(), test_dynamic_playback_ui_preview_and_movement(), test_room_view_radius_and_selection(), test_room_view_signals_and_keyboard_shortcuts() (+1 more)

### Community 4 - "test_music_and_master.py"
Cohesion: 0.12
Nodes (14): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), MasterRenderer714, _energy(), integrated(), _k_filter(), MasterReport, MixMeter, true_peak() (+6 more)

### Community 5 - "7. Histórico de Versões e Decisões Críticas Recentes"
Cohesion: 0.16
Nodes (4): 7. Histórico de Versões e Decisões Críticas Recentes, _clock(), _immunize_cpython_none_refcount(), test_live_spatial_player()

### Community 6 - "exporter.py"
Cohesion: 0.05
Nodes (24): [1.3.1] - 2026-11-19, Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura), generate_714_channel_check(), AudioMetadata, DirectFrameBridge, AudioExporter714, ExportFormat, ExportResult (+16 more)

### Community 7 - "MainWindow"
Cohesion: 0.06
Nodes (10): _label(), MainWindow, install(), finished(), delivered(), install(), finished(), _panel() (+2 more)

### Community 8 - "apply_process_shield"
Cohesion: 0.16
Nodes (6): apply_cpu_affinity(), apply_process_shield(), get_shielded_thread_count(), main(), _terminate_descendants(), test_process_shield_and_cpu_affinity()

### Community 10 - "monitor_callback.c"
Cohesion: 0.17
Nodes (10): monitor_acknowledged(), monitor_consumed(), monitor_has_space(), monitor_port_free(), monitor_port_new(), monitor_publish(), monitor_push(), monitor_ring_free() (+2 more)

### Community 11 - "StemControlCard"
Cohesion: 0.19
Nodes (4): Adicionado & Corrigido (Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos), __getattr__(), StemControlCard, test_stem_card_pan_and_quick_position_snaps()

### Community 12 - "BinauralHRTFEngine"
Cohesion: 0.12
Nodes (7): [1.3.0] - 2026-11-19, Adicionado & Otimizado, Corrigido & Otimizado (Arquitetura DSP 100% Lock-Free e Eliminação de Congelamentos no Sistema), BinauralHRTFEngine, AudioDSPState, test_micro_render_monitor_and_joc_decode(), test_binaural_delay_survives_partial_blocks_and_seek()

### Community 13 - "test_atmossplit.py"
Cohesion: 0.12
Nodes (10): AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, SongStructureIntelligence, test_acoustic_analyzer_and_auto_director(), test_immersion_360_lead_vocal_anchored(), test_surgical_stems_intelligence_and_room_mute_visuals() (+2 more)

### Community 14 - "StemCacheManager"
Cohesion: 0.22
Nodes (5): CachedStemMetadata, _component(), StemCacheManager, test_cache_statistics_and_cleanup(), test_stem_cache_manager()

### Community 15 - "numpy"
Cohesion: 0.10
Nodes (15): vocal_axis(), _envelope(), MixPlan, MixSource, placement_pair(), prepare_sources(), _presence(), Projection (+7 more)

### Community 16 - "NativePort"
Cohesion: 0.18
Nodes (7): native_output(), attach(), run(), NativePort, NativeRing, test_native_ring_capacity_partial_reads_and_seek_reclamation(), consume()

### Community 17 - "numpy"
Cohesion: 0.24
Nodes (10): _add_mix(), analyze_structure(), _frames(), MusicalPart, _novelty(), Pulse, _pulse(), _relative() (+2 more)

### Community 18 - "AtmosSplit — Estúdio de áudio espacial 7.1.4"
Cohesion: 0.11
Nodes (16): 1. Auditoria dos Projetos Vizinhos Reaproveitáveis, 2. Benchmark Empírico de Separação de Stems (CPU Xeon vs. GPU RX 580), 3. Verificação de saída no estúdio 2.0, 4. Reproduzir a calibração, ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4, 1. Visão geral, 2. Mapa do código, 3. Da faixa ao arranjo (+8 more)

### Community 19 - "cache_manager.py"
Cohesion: 0.21
Nodes (4): DeepStemEngine, emit_json(), main(), progress_cb()

### Community 20 - "iniciar.sh"
Cohesion: 0.29
Nodes (6): CUDA_VISIBLE_DEVICES, HF_HUB_OFFLINE, HIP_VISIBLE_DEVICES, QT_ENABLE_HIGHDPI_SCALING, QT_QPA_PLATFORM, iniciar.sh script

### Community 23 - "search_source.py"
Cohesion: 0.12
Nodes (11): [1.3.2] - 2026-11-19, Corrigido & Aprimorado (Dolby Atmos Real com Joint Object Coding / E-AC-3 JOC & 12 Objetos Espaciais 7.1.4), AudioProbeResult, verify_audio_file(), SearchResultItem, SearchSourceEngine, _emit(), execute() (+3 more)

### Community 24 - "subprocess"
Cohesion: 0.36
Nodes (3): audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark()

### Community 25 - "BinauralHRTFEngine"
Cohesion: 0.06
Nodes (24): [1.2.0] - 2026-11-19, [1.4.0] - 2026-11-19, [1.5.0] - 2026-11-19, [1.6.0] - 2026-11-19, [1.6.1] - 2026-11-19, [1.6.2] - 2026-11-19, [1.7.0] - 2026-11-19, [1.7.1] - 2026-11-19 (+16 more)

### Community 26 - "StemTrack"
Cohesion: 0.25
Nodes (11): StemTrack, detect_micro_events(), _observe(), test_stem_card_duplicate_button_and_signal(), phrase_mix(), bursts(), session(), test_continuous_verse_and_irregular_dissimilar_notes_stay_anchored() (+3 more)

### Community 28 - "LiveSpatialPlayer"
Cohesion: 0.26
Nodes (6): LiveSpatialPlayer, build(), load(), test_live_player_crash_proof_and_zero_lock_contention(), test_lock_free_dsp_and_timeline_crossfade_audio_callback(), test_audio_clock_resampling_shared_automation_and_monitors()

### Community 29 - "stem_engine.py"
Cohesion: 0.20
Nodes (5): _resample(), SeparationResult, split_surgical(), _tracks(), test_surgical_additive_and_centered_vocal()

### Community 30 - "test_music_and_master.py"
Cohesion: 0.35
Nodes (8): RenderConfig, song(), test_editing_preserves_mir_bar_grid_and_proportions(), test_mono_and_mirrored_consume_equal_power_and_lfe_is_bandlimited(), test_phase_or_pan_imbalance_preserves_lead_at_center(), test_vocal_presence_profile_and_linked_true_peak(), test_without_pulse_keeps_real_harmonic_change(), track()

## Knowledge Gaps
- **5 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`, `CUDA_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES`, `HF_HUB_OFFLINE`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 248 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `main_window.py`, `TimelineTrackCanvas`, `SpatialPlacement`, `7. Histórico de Versões e Decisões Críticas Recentes`, `exporter.py`, `StemControlCard`, `test_atmossplit.py`, `StemCacheManager`, `cache_manager.py`, `StemTrack`, `LiveSpatialPlayer`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `MainWindow` (e.g. with `DirectFrameBridge` and `ExportFormat`) actually correct?**
  _`MainWindow` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`, `CUDA_VISIBLE_DEVICES` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.057967313585291114 - nodes in this community are weakly interconnected._
- **Why does `SpatialPlacement` connect `SpatialPlacement` to `main_window.py`, `TimelineTrackCanvas`, `test_music_and_master.py`, `7. Histórico de Versões e Decisões Críticas Recentes`, `MainWindow`, `StemControlCard`, `test_atmossplit.py`, `numpy`, `StemTrack`, `LiveSpatialPlayer`, `test_music_and_master.py`, `test_native_monitor_seek_updates_and_drains_on_device_thread`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `TimelineTrackCanvas` be split into smaller, more focused modules?**
  _Cohesion score 0.05098934550989345 - nodes in this community are weakly interconnected._