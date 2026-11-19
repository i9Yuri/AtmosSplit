# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 40 files · ~49,714 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 662 nodes · 1686 edges · 30 communities (20 shown, 10 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 286 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8c778395`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main_window.py
- file_source.py
- TimelineTrackCanvas
- RoomView714
- DirectorPreset
- test_atmossplit.py
- verify_audio_file
- MainWindow
- .stop
- test_live_spatial_player
- exporter.py
- StemControlCard
- BinauralHRTFEngine
- StemTrack
- StemCacheManager
- .set_stems_and_placements
- AudioDSPState
- AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral
- ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4
- AtmosSplit — Montador Espacial Dolby Atmos 7.1.4
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh
- BinauralHRTFEngine
- DirectFrameBridge
- SpatialTimelineManager
- StemTrack
- SpatialPlacement
- test_lock_free_dsp_and_timeline_crossfade_audio_callback
- 7. Histórico de Versões e Decisões Críticas Recentes

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 80 edges
2. `SpatialPlacement` - 48 edges
3. `RoomView714` - 47 edges
4. `SpatialTimelineManager` - 42 edges
5. `StemTrack` - 40 edges
6. `LiveSpatialPlayer` - 38 edges
7. `StemControlCard` - 35 edges
8. `TimelineTrackCanvas` - 28 edges
9. `MasterRenderer714` - 27 edges
10. `7. Histórico de Versões e Decisões Críticas Recentes` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` --references--> `start_stream()`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py
- `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` --references--> `close_stream()`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py
- `Adicionado & Aprimorado (IA Maestro com Arranjo Estrutural Autônomo, Efeito Vocal Throw 7.1.4 e Timeline Profissional Estilo DAW)` --references--> `MasterRenderer714`  [INFERRED]
  CHANGELOG.md → src/spatial/master_renderer.py
- `4. Restrições Críticas de Hardware, SO e Ambiente` --references--> `MainWindow`  [INFERRED]
  PROJECT_CONTEXT.md → src/ui/main_window.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `AutoAtmosDirector`  [INFERRED]
  CHANGELOG.md → src/spatial/auto_director.py

## Import Cycles
- None detected.

## Communities (30 total, 10 thin omitted)

### Community 0 - "main_window.py"
Cohesion: 0.05
Nodes (15): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), CachedStemMetadata, apply_cpu_affinity(), apply_process_shield(), get_shielded_thread_count() (+7 more)

### Community 1 - "file_source.py"
Cohesion: 0.14
Nodes (5): AudioSource, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), sample_stereo_wav()

### Community 3 - "RoomView714"
Cohesion: 0.06
Nodes (8): Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio), VBAP714Engine, _immunize_cpython_none_refcount(), RoomView714, test_cpython_none_refcount_shield_and_zero_paint_leak(), test_room_view_radius_and_selection(), test_room_view_signals_and_keyboard_shortcuts(), test_room_view_stereo_pucks_and_toggle()

### Community 4 - "DirectorPreset"
Cohesion: 0.18
Nodes (6): AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, test_acoustic_analyzer_and_auto_director(), test_immersion_360_lead_vocal_anchored()

### Community 5 - "test_atmossplit.py"
Cohesion: 0.16
Nodes (8): [1.5.0] - 2026-11-19, Corrigido & Aprimorado (Mixagem Profissional Dolby Atmos & Correção de Mapeamento ETSI TS 103 420), test_binaural_hrtf_engine(), test_exporter_etsi_ts_103_420_coordinates(), test_song_structure_intelligence_and_vocal_throw(), test_stem_card_duplicate_button_and_signal(), test_stem_card_pan_and_quick_position_snaps(), test_vbap_714_constant_power()

### Community 6 - "verify_audio_file"
Cohesion: 0.22
Nodes (4): verify_audio_file(), test_exporter_anti_truncation_full_duration(), test_file_source_and_sha256(), test_probe_verifier()

### Community 7 - "MainWindow"
Cohesion: 0.05
Nodes (5): SearchResultItem, SearchSourceEngine, MainWindow, _do_clear(), run_app()

### Community 8 - ".stop"
Cohesion: 0.17
Nodes (3): LiveSpatialPlayer, close_stream(), start_stream()

### Community 10 - "exporter.py"
Cohesion: 0.19
Nodes (4): AudioMetadata, AudioExporter714, ExportFormat, test_exporter_multichannel_mkv_and_wav()

### Community 12 - "BinauralHRTFEngine"
Cohesion: 0.14
Nodes (3): [1.3.0] - 2026-11-19, Adicionado & Otimizado, BinauralHRTFEngine

### Community 13 - "StemTrack"
Cohesion: 0.15
Nodes (8): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), MasterRenderer714, RenderConfig, test_k_weighted_lufs_loudness_and_true_peak(), test_master_renderer_anti_clipping(), test_master_renderer_dynamic_timeline(), test_spatial_placement_cloning_and_multichannel_render(), test_stereo_mirroring_placement_and_render()

### Community 14 - "StemCacheManager"
Cohesion: 0.13
Nodes (3): StemCacheManager, test_cache_statistics_and_cleanup(), test_stem_cache_manager()

### Community 17 - "AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral"
Cohesion: 0.20
Nodes (9): 1. Visão Geral e Objetivo do Sistema, 2. Mapa Estrutural do Repositório, 3. Pipeline Passo a Passo, 4. Restrições Críticas de Hardware, SO e Ambiente, 5. Configurações Globais e Dependências, 6. Instruções Críticas para IAs que Modificarem Este Código, AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral, Comandos de Execução e Testes (+1 more)

### Community 18 - "ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4"
Cohesion: 0.33
Nodes (5): 1. Auditoria dos Projetos Vizinhos Reaproveitáveis, 2. Benchmark Empírico de Separação de Stems (CPU Xeon vs. GPU RX 580), 3. Verificação Real de Saída e Reprodução 7.1.4, 4. Conclusão da Fase 0 e Diretriz do Exportador, ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4

### Community 19 - "AtmosSplit — Montador Espacial Dolby Atmos 7.1.4"
Cohesion: 0.15
Nodes (12): 1. Ingestão & Busca Flexível, 2. Destrinchador Multi-Estágio com IA & DSP Cirúrgico, 3. Planta Interativa 2D / 3D da Sala 7.1.4, 4. Automação Espacial Dinâmica por Trechos (Timeline), 5. Dolby Atmos Real com Joint Object Coding (E-AC-3 JOC via `ac3forge`), AtmosSplit — Montador Espacial Dolby Atmos 7.1.4, 🚀 Como Executar, 📦 Formatos de Exportação Suportados (+4 more)

### Community 20 - "iniciar.sh"
Cohesion: 0.50
Nodes (3): QT_ENABLE_HIGHDPI_SCALING, QT_QPA_PLATFORM, iniciar.sh script

### Community 25 - "BinauralHRTFEngine"
Cohesion: 0.07
Nodes (22): [1.2.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, [1.6.0] - 2026-11-19, [1.6.1] - 2026-11-19, [1.6.2] - 2026-11-19, [1.7.0] - 2026-11-19 (+14 more)

### Community 28 - "SpatialTimelineManager"
Cohesion: 0.10
Nodes (5): SpatialSection, SpatialTimelineManager, test_spatial_timeline_manager_split_and_interpolation(), test_timeline_interactive_boundary_drag_and_minimap(), test_timeline_millisecond_zoom_and_ruler()

### Community 30 - "StemTrack"
Cohesion: 0.24
Nodes (3): StemTrack, SectionDescriptor, SongStructureIntelligence

### Community 37 - "7. Histórico de Versões e Decisões Críticas Recentes"
Cohesion: 0.18
Nodes (3): Adicionado & Corrigido (Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos), 7. Histórico de Versões e Decisões Críticas Recentes, _install_crash_shield()

## Knowledge Gaps
- **2 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 256 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `main_window.py`, `file_source.py`, `TimelineTrackCanvas`, `RoomView714`, `DirectorPreset`, `.stop`, `test_live_spatial_player`, `exporter.py`, `StemControlCard`, `BinauralHRTFEngine`, `StemTrack`, `StemCacheManager`, `AudioDSPState`, `AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral`, `BinauralHRTFEngine`, `DirectFrameBridge`, `SpatialTimelineManager`, `StemTrack`, `SpatialPlacement`, `test_lock_free_dsp_and_timeline_crossfade_audio_callback`, `7. Histórico de Versões e Decisões Críticas Recentes`?**
  _High betweenness centrality (0.208) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 25 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0547680412371134 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `main_window.py`, `7. Histórico de Versões e Decisões Críticas Recentes`, `test_atmossplit.py`, `MainWindow`, `AudioDSPState`, `StemTrack`, `SpatialPlacement`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `file_source.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._