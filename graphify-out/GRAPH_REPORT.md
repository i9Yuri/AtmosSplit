# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 39 files · ~39,314 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 580 nodes · 1432 edges · 29 communities (17 shown, 12 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 221 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d024466e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- stem_engine.py
- main_window.py
- SpatialPlacement
- RoomView714
- search_source.py
- MasterRenderer714
- 7. Histórico de Versões e Decisões Críticas Recentes
- MainWindow
- TimelineWidget
- file_source.py
- StemControlCard
- LiveSpatialPlayer
- test_atmossplit.py
- StemCacheManager
- exporter.py
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
- .separate_track

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 73 edges
2. `SpatialPlacement` - 39 edges
3. `RoomView714` - 39 edges
4. `SpatialTimelineManager` - 37 edges
5. `LiveSpatialPlayer` - 34 edges
6. `StemControlCard` - 34 edges
7. `StemTrack` - 30 edges
8. `MasterRenderer714` - 23 edges
9. `StemCacheManager` - 20 edges
10. `TimelineWidget` - 19 edges

## Surprising Connections (you probably didn't know these)
- `4. Restrições Críticas de Hardware, SO e Ambiente` --references--> `MainWindow`  [INFERRED]
  PROJECT_CONTEXT.md → src/ui/main_window.py
- `Corrigido & Aprimorado (Dolby Atmos Real com Joint Object Coding / E-AC-3 JOC & 12 Objetos Espaciais 7.1.4)` --references--> `AudioProbeResult`  [INFERRED]
  CHANGELOG.md → src/acquisition/probe_verifier.py
- `Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura)` --references--> `SamsungDLNABridge`  [INFERRED]
  CHANGELOG.md → src/playback/samsung_dlna_bridge.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `AutoAtmosDirector`  [INFERRED]
  CHANGELOG.md → src/spatial/auto_director.py
- `7. Histórico de Versões e Decisões Críticas Recentes` --references--> `AudioDSPState`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/live_player.py

## Import Cycles
- None detected.

## Communities (29 total, 12 thin omitted)

### Community 0 - "stem_engine.py"
Cohesion: 0.12
Nodes (7): apply_cpu_affinity(), apply_process_shield(), get_shielded_thread_count(), emit_json(), main(), progress_cb(), test_process_shield_and_cpu_affinity()

### Community 1 - "main_window.py"
Cohesion: 0.09
Nodes (8): AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, SpeakerPosition714, VBAP714Engine, run_app(), test_acoustic_analyzer_and_auto_director()

### Community 2 - "SpatialPlacement"
Cohesion: 0.09
Nodes (5): SpatialPlacement, SpatialSection, SpatialTimelineManager, test_lock_free_dsp_and_timeline_crossfade_audio_callback(), test_spatial_timeline_manager_split_and_interpolation()

### Community 4 - "search_source.py"
Cohesion: 0.09
Nodes (8): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), AudioProbeResult, verify_audio_file(), SearchResultItem, SearchSourceEngine

### Community 5 - "MasterRenderer714"
Cohesion: 0.12
Nodes (9): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), StemTrack, MasterRenderer714, RenderConfig, test_k_weighted_lufs_loudness_and_true_peak(), test_master_renderer_anti_clipping(), test_master_renderer_dynamic_timeline(), test_room_view_stereo_pucks_and_toggle() (+1 more)

### Community 6 - "7. Histórico de Versões e Decisões Críticas Recentes"
Cohesion: 0.17
Nodes (4): [1.3.0] - 2026-11-19, Adicionado & Otimizado, 7. Histórico de Versões e Decisões Críticas Recentes, BinauralHRTFEngine

### Community 10 - "file_source.py"
Cohesion: 0.13
Nodes (6): AudioSource, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), sample_stereo_wav(), test_file_source_and_sha256()

### Community 12 - "LiveSpatialPlayer"
Cohesion: 0.13
Nodes (6): [1.6.1] - 2026-11-19, Corrigido & Otimizado (Arquitetura DSP 100% Lock-Free e Eliminação de Congelamentos no Sistema), AudioDSPState, LiveSpatialPlayer, test_live_player_crash_proof_and_zero_lock_contention(), test_live_spatial_player()

### Community 13 - "test_atmossplit.py"
Cohesion: 0.17
Nodes (8): Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura), Corrigido & Aprimorado (Mixagem Profissional Dolby Atmos & Correção de Mapeamento ETSI TS 103 420), test_binaural_hrtf_engine(), test_exporter_etsi_ts_103_420_coordinates(), test_immersion_360_lead_vocal_anchored(), test_probe_verifier(), test_room_view_radius_and_selection(), test_vbap_714_constant_power()

### Community 14 - "StemCacheManager"
Cohesion: 0.11
Nodes (5): CachedStemMetadata, StemCacheManager, DeepStemEngine, test_cache_statistics_and_cleanup(), test_stem_cache_manager()

### Community 16 - "exporter.py"
Cohesion: 0.17
Nodes (5): AudioMetadata, AudioExporter714, ExportFormat, test_exporter_anti_truncation_full_duration(), test_exporter_multichannel_mkv_and_wav()

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
Cohesion: 0.17
Nodes (3): Adicionado & Corrigido (Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos), _install_crash_shield(), test_stem_card_pan_and_quick_position_snaps()

### Community 25 - "CHANGELOG — AtmosSplit"
Cohesion: 0.20
Nodes (9): [1.2.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, [1.5.0] - 2026-11-19, [1.6.0] - 2026-11-19, Adicionado & Otimizado, CHANGELOG — AtmosSplit (+1 more)

## Knowledge Gaps
- **2 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 235 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `main_window.py`, `SpatialPlacement`, `RoomView714`, `search_source.py`, `MasterRenderer714`, `7. Histórico de Versões e Decisões Críticas Recentes`, `TimelineWidget`, `.play`, `file_source.py`, `StemControlCard`, `LiveSpatialPlayer`, `StemCacheManager`, `exporter.py`, `AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral`, `SamsungDLNABridge`, `DirectFrameBridge`, `.separate_track`?**
  _High betweenness centrality (0.224) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `stem_engine.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12258064516129032 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `main_window.py`, `SpatialPlacement`, `MasterRenderer714`, `7. Histórico de Versões e Decisões Críticas Recentes`, `MainWindow`, `test_atmossplit.py`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09143686502177069 - nodes in this community are weakly interconnected._