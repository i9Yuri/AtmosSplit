# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 39 files · ~32,799 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: .desktop 2, .mka 2)

## Summary
- 514 nodes · 1259 edges · 23 communities (13 shown, 10 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 170 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6ac14b0c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_atmossplit.py
- main_window.py
- SpatialPlacement
- RoomView714
- search_source.py
- .export
- SamsungDLNABridge
- MainWindow
- TimelineWidget
- LiveSpatialPlayer
- file_source.py
- StemControlCard
- ._audio_callback
- .reset_states
- AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral
- test_live_spatial_player
- ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4
- AtmosSplit — Montador Espacial Dolby Atmos 7.1.4
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 69 edges
2. `SpatialPlacement` - 37 edges
3. `RoomView714` - 37 edges
4. `SpatialTimelineManager` - 34 edges
5. `LiveSpatialPlayer` - 32 edges
6. `StemTrack` - 26 edges
7. `MasterRenderer714` - 21 edges
8. `StemCacheManager` - 20 edges
9. `StemControlCard` - 20 edges
10. `TimelineWidget` - 19 edges

## Surprising Connections (you probably didn't know these)
- `4. Restrições Críticas de Hardware, SO e Ambiente` --references--> `MainWindow`  [INFERRED]
  PROJECT_CONTEXT.md → src/ui/main_window.py
- `Corrigido & Aprimorado (Dolby Atmos Real com Joint Object Coding / E-AC-3 JOC & 12 Objetos Espaciais 7.1.4)` --references--> `AudioProbeResult`  [INFERRED]
  CHANGELOG.md → src/acquisition/probe_verifier.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `AutoAtmosDirector`  [INFERRED]
  CHANGELOG.md → src/spatial/auto_director.py
- `7. Histórico de Versões e Decisões Críticas Recentes` --references--> `SpatialTimelineManager`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/timeline_manager.py
- `Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)` --references--> `TimelineWidget`  [INFERRED]
  CHANGELOG.md → src/ui/timeline_widget.py

## Import Cycles
- None detected.

## Communities (23 total, 10 thin omitted)

### Community 0 - "test_atmossplit.py"
Cohesion: 0.05
Nodes (14): CachedStemMetadata, StemCacheManager, apply_cpu_affinity(), apply_process_shield(), get_shielded_thread_count(), DeepStemEngine, SeparationResult, emit_json() (+6 more)

### Community 1 - "main_window.py"
Cohesion: 0.09
Nodes (7): AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, SpeakerPosition714, VBAP714Engine, test_acoustic_analyzer_and_auto_director()

### Community 2 - "SpatialPlacement"
Cohesion: 0.09
Nodes (11): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), StemTrack, SpatialPlacement, MasterRenderer714, RenderConfig, SpatialSection, SpatialTimelineManager, test_master_renderer_anti_clipping() (+3 more)

### Community 3 - "RoomView714"
Cohesion: 0.08
Nodes (3): RoomView714, test_room_view_radius_and_selection(), test_room_view_stereo_pucks_and_toggle()

### Community 4 - "search_source.py"
Cohesion: 0.09
Nodes (8): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), AudioProbeResult, verify_audio_file(), SearchResultItem, SearchSourceEngine

### Community 5 - ".export"
Cohesion: 0.10
Nodes (8): AudioMetadata, DirectFrameBridge, AudioExporter714, ExportFormat, sample_stereo_wav(), test_exporter_anti_truncation_full_duration(), test_exporter_multichannel_mkv_and_wav(), test_probe_verifier()

### Community 6 - "SamsungDLNABridge"
Cohesion: 0.08
Nodes (12): [1.2.0] - 2026-11-19, [1.3.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, Adicionado & Otimizado, Adicionado & Otimizado, CHANGELOG — AtmosSplit (+4 more)

### Community 9 - "LiveSpatialPlayer"
Cohesion: 0.16
Nodes (3): 7. Histórico de Versões e Decisões Críticas Recentes, BinauralHRTFEngine, LiveSpatialPlayer

### Community 10 - "file_source.py"
Cohesion: 0.16
Nodes (5): AudioSource, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), test_file_source_and_sha256()

### Community 14 - "AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral"
Cohesion: 0.20
Nodes (9): 1. Visão Geral e Objetivo do Sistema, 2. Mapa Estrutural do Repositório, 3. Pipeline Passo a Passo, 4. Restrições Críticas de Hardware, SO e Ambiente, 5. Configurações Globais e Dependências, 6. Instruções Críticas para IAs que Modificarem Este Código, AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral, Comandos de Execução e Testes (+1 more)

### Community 18 - "ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4"
Cohesion: 0.33
Nodes (5): 1. Auditoria dos Projetos Vizinhos Reaproveitáveis, 2. Benchmark Empírico de Separação de Stems (CPU Xeon vs. GPU RX 580), 3. Verificação Real de Saída e Reprodução 7.1.4, 4. Conclusão da Fase 0 e Diretriz do Exportador, ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4

### Community 19 - "AtmosSplit — Montador Espacial Dolby Atmos 7.1.4"
Cohesion: 0.40
Nodes (4): AtmosSplit — Montador Espacial Dolby Atmos 7.1.4, 🚀 Como Executar, 🎧 Hardware e Ecossistema Alvo, ✨ Recursos Principais

### Community 20 - "iniciar.sh"
Cohesion: 0.50
Nodes (3): QT_ENABLE_HIGHDPI_SCALING, QT_QPA_PLATFORM, iniciar.sh script

## Knowledge Gaps
- **2 isolated node(s):** `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 202 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `test_atmossplit.py`, `main_window.py`, `SpatialPlacement`, `RoomView714`, `search_source.py`, `.export`, `SamsungDLNABridge`, `TimelineWidget`, `LiveSpatialPlayer`, `file_source.py`, `StemControlCard`, `.reset_states`, `AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral`, `.update_placement`, `._init_theme_and_ui`, `test_live_spatial_player`?**
  _High betweenness centrality (0.246) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_atmossplit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.054203180785459264 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `test_atmossplit.py`, `main_window.py`, `SpatialPlacement`, `SamsungDLNABridge`, `MainWindow`, `.update_placement`, `._init_theme_and_ui`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._