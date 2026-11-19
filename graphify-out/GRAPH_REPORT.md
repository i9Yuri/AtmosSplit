# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 39 files · ~42,217 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 610 nodes · 1532 edges · 29 communities (11 shown, 18 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 260 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a8bf4ebd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main_window.py
- 7. Histórico de Versões e Decisões Críticas Recentes
- SpatialTimelineManager
- RoomView714
- SearchSourceEngine
- .get_total_cache_size_bytes
- MainWindow
- .stop
- test_atmossplit.py
- StemControlCard
- LiveSpatialPlayer
- SpatialPlacement
- AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral
- ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4
- AtmosSplit — Montador Espacial Dolby Atmos 7.1.4
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh
- ._audio_callback
- BinauralHRTFEngine
- DirectFrameBridge

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 75 edges
2. `SpatialPlacement` - 42 edges
3. `RoomView714` - 41 edges
4. `SpatialTimelineManager` - 38 edges
5. `LiveSpatialPlayer` - 37 edges
6. `StemControlCard` - 34 edges
7. `StemTrack` - 31 edges
8. `MasterRenderer714` - 26 edges
9. `TimelineWidget` - 26 edges
10. `7. Histórico de Versões e Decisões Críticas Recentes` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` --references--> `start_stream()`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py
- `Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)` --references--> `close_stream()`  [INFERRED]
  CHANGELOG.md → src/spatial/live_player.py
- `4. Restrições Críticas de Hardware, SO e Ambiente` --references--> `MainWindow`  [INFERRED]
  PROJECT_CONTEXT.md → src/ui/main_window.py
- `Corrigido & Aprimorado (Dolby Atmos Real com Joint Object Coding / E-AC-3 JOC & 12 Objetos Espaciais 7.1.4)` --references--> `AudioProbeResult`  [INFERRED]
  CHANGELOG.md → src/acquisition/probe_verifier.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `AutoAtmosDirector`  [INFERRED]
  CHANGELOG.md → src/spatial/auto_director.py

## Import Cycles
- None detected.

## Communities (29 total, 18 thin omitted)

### Community 0 - "main_window.py"
Cohesion: 0.05
Nodes (20): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), CachedStemMetadata, StemCacheManager, apply_cpu_affinity(), apply_process_shield() (+12 more)

### Community 2 - "SpatialTimelineManager"
Cohesion: 0.05
Nodes (6): SpatialSection, SpatialTimelineManager, TimelineTrackCanvas, TimelineWidget, test_spatial_timeline_manager_split_and_interpolation(), test_timeline_millisecond_zoom_and_ruler()

### Community 3 - "RoomView714"
Cohesion: 0.07
Nodes (4): Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio), _immunize_cpython_none_refcount(), RoomView714, test_cpython_none_refcount_shield_and_zero_paint_leak()

### Community 10 - "test_atmossplit.py"
Cohesion: 0.05
Nodes (23): [1.5.0] - 2026-11-19, Corrigido & Aprimorado (Mixagem Profissional Dolby Atmos & Correção de Mapeamento ETSI TS 103 420), AudioMetadata, AudioSource, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), AudioProbeResult (+15 more)

### Community 12 - "LiveSpatialPlayer"
Cohesion: 0.13
Nodes (6): Corrigido & Otimizado (Arquitetura DSP 100% Lock-Free e Eliminação de Congelamentos no Sistema), AudioDSPState, LiveSpatialPlayer, test_live_player_crash_proof_and_zero_lock_contention(), test_live_spatial_player(), test_lock_free_dsp_and_timeline_crossfade_audio_callback()

### Community 13 - "SpatialPlacement"
Cohesion: 0.09
Nodes (13): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), StemTrack, DirectorPreset, SpatialPlacement, MasterRenderer714, RenderConfig, test_k_weighted_lufs_loudness_and_true_peak(), test_master_renderer_anti_clipping() (+5 more)

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
Cohesion: 0.06
Nodes (18): [1.2.0] - 2026-11-19, [1.3.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, [1.6.0] - 2026-11-19, [1.6.1] - 2026-11-19, [1.6.2] - 2026-11-19 (+10 more)

## Knowledge Gaps
- **2 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 239 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `main_window.py`, `7. Histórico de Versões e Decisões Críticas Recentes`, `SpatialTimelineManager`, `RoomView714`, `SearchSourceEngine`, `.get_total_cache_size_bytes`, `.__init__`, `.stop`, `.set_active_placements`, `test_atmossplit.py`, `StemControlCard`, `LiveSpatialPlayer`, `SpatialPlacement`, `._init_theme_and_ui`, `AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral`, `._cancel_separation_task`, `BinauralHRTFEngine`, `.seek`, `DirectFrameBridge`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05025568682771998 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `main_window.py`, `7. Histórico de Versões e Decisões Críticas Recentes`, `MainWindow`, `test_atmossplit.py`, `SpatialPlacement`, `._init_theme_and_ui`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `SpatialTimelineManager` be split into smaller, more focused modules?**
  _Cohesion score 0.05223880597014925 - nodes in this community are weakly interconnected._