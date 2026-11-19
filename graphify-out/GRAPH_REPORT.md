# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 39 files · ~40,493 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 592 nodes · 1468 edges · 28 communities (14 shown, 14 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 237 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4998c574`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main_window.py
- main_window.py
- SpatialPlacement
- RoomView714
- SearchSourceEngine
- .get_total_cache_size_bytes
- MainWindow
- TimelineWidget
- file_source.py
- StemControlCard
- LiveSpatialPlayer
- test_atmossplit.py
- StemCacheManager
- test_cache_statistics_and_cleanup
- AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral
- ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4
- AtmosSplit — Montador Espacial Dolby Atmos 7.1.4
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh
- SamsungDLNABridge
- test_stem_card_pan_and_quick_position_snaps
- CHANGELOG — AtmosSplit
- DirectFrameBridge

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 73 edges
2. `RoomView714` - 41 edges
3. `SpatialPlacement` - 40 edges
4. `SpatialTimelineManager` - 37 edges
5. `LiveSpatialPlayer` - 36 edges
6. `StemControlCard` - 34 edges
7. `StemTrack` - 30 edges
8. `MasterRenderer714` - 23 edges
9. `7. Histórico de Versões e Decisões Críticas Recentes` - 21 edges
10. `StemCacheManager` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` --references--> `start_stream()`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py
- `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` --references--> `close_stream()`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py
- `4. Restrições Críticas de Hardware, SO e Ambiente` --references--> `MainWindow`  [INFERRED]
  PROJECT_CONTEXT.md → src/ui/main_window.py
- `Corrigido & Aprimorado (Dolby Atmos Real com Joint Object Coding / E-AC-3 JOC & 12 Objetos Espaciais 7.1.4)` --references--> `AudioProbeResult`  [INFERRED]
  CHANGELOG.md → src/acquisition/probe_verifier.py
- `Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura)` --references--> `SamsungDLNABridge`  [INFERRED]
  CHANGELOG.md → src/playback/samsung_dlna_bridge.py

## Import Cycles
- None detected.

## Communities (28 total, 14 thin omitted)

### Community 0 - "main_window.py"
Cohesion: 0.07
Nodes (17): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), AudioSource, AudioProbeResult, verify_audio_file(), ExportFormat (+9 more)

### Community 1 - "main_window.py"
Cohesion: 0.07
Nodes (11): AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, BinauralHRTFEngine, AudioDSPState, SpeakerPosition714, VBAP714Engine (+3 more)

### Community 2 - "SpatialPlacement"
Cohesion: 0.07
Nodes (9): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), SpatialPlacement, MasterRenderer714, SpatialSection, SpatialTimelineManager, test_k_weighted_lufs_loudness_and_true_peak(), test_lock_free_dsp_and_timeline_crossfade_audio_callback(), test_master_renderer_dynamic_timeline() (+1 more)

### Community 3 - "RoomView714"
Cohesion: 0.07
Nodes (4): Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio), _immunize_cpython_none_refcount(), RoomView714, test_cpython_none_refcount_shield_and_zero_paint_leak()

### Community 10 - "file_source.py"
Cohesion: 0.11
Nodes (7): AudioMetadata, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), AudioExporter714, RenderConfig, test_exporter_multichannel_mkv_and_wav()

### Community 12 - "LiveSpatialPlayer"
Cohesion: 0.06
Nodes (5): 7. Histórico de Versões e Decisões Críticas Recentes, LiveSpatialPlayer, close_stream(), start_stream(), _install_crash_shield()

### Community 13 - "test_atmossplit.py"
Cohesion: 0.17
Nodes (8): StemTrack, test_binaural_hrtf_engine(), test_exporter_etsi_ts_103_420_coordinates(), test_live_spatial_player(), test_master_renderer_anti_clipping(), test_room_view_radius_and_selection(), test_room_view_stereo_pucks_and_toggle(), test_vbap_714_constant_power()

### Community 16 - "test_cache_statistics_and_cleanup"
Cohesion: 0.12
Nodes (7): Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura), sample_stereo_wav(), test_cache_statistics_and_cleanup(), test_exporter_anti_truncation_full_duration(), test_file_source_and_sha256(), test_probe_verifier(), test_stem_cache_manager()

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

### Community 24 - "test_stem_card_pan_and_quick_position_snaps"
Cohesion: 0.18
Nodes (3): Adicionado & Corrigido (Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos), test_live_player_crash_proof_and_zero_lock_contention(), test_stem_card_pan_and_quick_position_snaps()

### Community 25 - "CHANGELOG — AtmosSplit"
Cohesion: 0.11
Nodes (15): [1.2.0] - 2026-11-19, [1.3.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, [1.5.0] - 2026-11-19, [1.6.0] - 2026-11-19, [1.6.1] - 2026-11-19 (+7 more)

## Knowledge Gaps
- **2 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 238 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `main_window.py`, `main_window.py`, `SpatialPlacement`, `RoomView714`, `SearchSourceEngine`, `.get_total_cache_size_bytes`, `._load_and_process_audio_path`, `TimelineWidget`, `.seek`, `file_source.py`, `StemControlCard`, `LiveSpatialPlayer`, `test_atmossplit.py`, `StemCacheManager`, `._init_theme_and_ui`, `AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral`, `SamsungDLNABridge`, `DirectFrameBridge`?**
  _High betweenness centrality (0.218) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06924882629107981 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `main_window.py`, `main_window.py`, `SpatialPlacement`, `MainWindow`, `LiveSpatialPlayer`, `test_atmossplit.py`, `._init_theme_and_ui`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `RoomView714` (e.g. with `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` and `7. Histórico de Versões e Decisões Críticas Recentes`) actually correct?**
  _`RoomView714` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06554019457245264 - nodes in this community are weakly interconnected._