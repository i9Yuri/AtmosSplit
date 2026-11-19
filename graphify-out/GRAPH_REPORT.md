# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 39 files · ~37,632 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 561 nodes · 1380 edges · 29 communities (13 shown, 16 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 202 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4ba9b6b4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_atmossplit.py
- auto_director.py
- SpatialPlacement
- RoomView714
- SearchSourceEngine
- MasterRenderer714
- BinauralHRTFEngine
- MainWindow
- TimelineWidget
- file_source.py
- StemControlCard
- LiveSpatialPlayer
- test_atmossplit.py
- test_cache_statistics_and_cleanup
- AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral
- ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4
- AtmosSplit — Montador Espacial Dolby Atmos 7.1.4
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh
- SamsungDLNABridge
- .__init__
- test_room_view_stereo_pucks_and_toggle

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 73 edges
2. `SpatialPlacement` - 39 edges
3. `RoomView714` - 38 edges
4. `SpatialTimelineManager` - 34 edges
5. `LiveSpatialPlayer` - 33 edges
6. `StemControlCard` - 32 edges
7. `StemTrack` - 28 edges
8. `MasterRenderer714` - 23 edges
9. `StemCacheManager` - 20 edges
10. `TimelineWidget` - 19 edges

## Surprising Connections (you probably didn't know these)
- `4. Restrições Críticas de Hardware, SO e Ambiente` --references--> `MainWindow`  [INFERRED]
  PROJECT_CONTEXT.md → src/ui/main_window.py
- `Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura)` --references--> `SamsungDLNABridge`  [INFERRED]
  CHANGELOG.md → src/playback/samsung_dlna_bridge.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `AutoAtmosDirector`  [INFERRED]
  CHANGELOG.md → src/spatial/auto_director.py
- `7. Histórico de Versões e Decisões Críticas Recentes` --references--> `BinauralHRTFEngine`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/binaural_hrtf.py
- `7. Histórico de Versões e Decisões Críticas Recentes` --references--> `LiveSpatialPlayer`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/live_player.py

## Import Cycles
- None detected.

## Communities (29 total, 16 thin omitted)

### Community 0 - "test_atmossplit.py"
Cohesion: 0.06
Nodes (16): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), CachedStemMetadata, StemCacheManager, apply_cpu_affinity(), apply_process_shield() (+8 more)

### Community 1 - "auto_director.py"
Cohesion: 0.18
Nodes (7): AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, test_acoustic_analyzer_and_auto_director(), test_immersion_360_lead_vocal_anchored(), test_stereo_mirroring_placement_and_render()

### Community 2 - "SpatialPlacement"
Cohesion: 0.13
Nodes (6): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), SpatialPlacement, SpatialSection, SpatialTimelineManager, test_master_renderer_dynamic_timeline(), test_spatial_timeline_manager_split_and_interpolation()

### Community 5 - "MasterRenderer714"
Cohesion: 0.12
Nodes (3): MasterRenderer714, RenderConfig, test_k_weighted_lufs_loudness_and_true_peak()

### Community 8 - "TimelineWidget"
Cohesion: 0.07
Nodes (4): [1.3.0] - 2026-11-19, Adicionado & Otimizado, TimelineTrackCanvas, TimelineWidget

### Community 10 - "file_source.py"
Cohesion: 0.05
Nodes (26): [1.2.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, [1.5.0] - 2026-11-19, [1.6.0] - 2026-11-19, Adicionado & Otimizado, CHANGELOG — AtmosSplit (+18 more)

### Community 11 - "StemControlCard"
Cohesion: 0.07
Nodes (5): Adicionado & Corrigido (Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos), 7. Histórico de Versões e Decisões Críticas Recentes, _install_crash_shield(), StemControlCard, test_stem_card_pan_and_quick_position_snaps()

### Community 12 - "LiveSpatialPlayer"
Cohesion: 0.20
Nodes (4): StemTrack, LiveSpatialPlayer, test_live_player_crash_proof_and_zero_lock_contention(), test_live_spatial_player()

### Community 13 - "test_atmossplit.py"
Cohesion: 0.17
Nodes (5): SpeakerPosition714, VBAP714Engine, test_master_renderer_anti_clipping(), test_room_view_radius_and_selection(), test_vbap_714_constant_power()

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

## Knowledge Gaps
- **2 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 223 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `test_atmossplit.py`, `auto_director.py`, `SpatialPlacement`, `RoomView714`, `SearchSourceEngine`, `MasterRenderer714`, `BinauralHRTFEngine`, `TimelineWidget`, `.seek`, `file_source.py`, `StemControlCard`, `LiveSpatialPlayer`, `test_cache_statistics_and_cleanup`, `.get_active_edit_section`, `._load_and_process_audio_path`, `AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral`, `SamsungDLNABridge`, `._init_theme_and_ui`, `.dragEnterEvent`, `.__init__`?**
  _High betweenness centrality (0.233) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_atmossplit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.056669339748730285 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `test_atmossplit.py`, `SpatialPlacement`, `MainWindow`, `TimelineWidget`, `StemControlCard`, `LiveSpatialPlayer`, `test_atmossplit.py`, `._init_theme_and_ui`, `test_room_view_stereo_pucks_and_toggle`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `SpatialPlacement` be split into smaller, more focused modules?**
  _Cohesion score 0.1349206349206349 - nodes in this community are weakly interconnected._