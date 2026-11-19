# Graph Report - AtmosSplit  (2026-11-19)

## Corpus Check
- 39 files · ~35,607 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .desktop 2, (none) 1)

## Summary
- 534 nodes · 1304 edges · 24 communities (10 shown, 14 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 180 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ac883bc9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_atmossplit.py
- main_window.py
- SpatialPlacement
- RoomView714
- SearchSourceEngine
- .__init__
- SamsungDLNABridge
- MainWindow
- TimelineWidget
- LiveSpatialPlayer
- file_source.py
- StemControlCard
- StemCacheManager
- ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4
- AtmosSplit — Montador Espacial Dolby Atmos 7.1.4
- iniciar.sh
- Abrir_AtmosSplit.sh
- install_desktop_entry.sh
- SamsungDLNABridge

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 70 edges
2. `SpatialPlacement` - 37 edges
3. `RoomView714` - 37 edges
4. `SpatialTimelineManager` - 34 edges
5. `LiveSpatialPlayer` - 32 edges
6. `StemTrack` - 26 edges
7. `MasterRenderer714` - 23 edges
8. `StemCacheManager` - 20 edges
9. `StemControlCard` - 20 edges
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
- `7. Histórico de Versões e Decisões Críticas Recentes` --references--> `BinauralHRTFEngine`  [INFERRED]
  PROJECT_CONTEXT.md → src/spatial/binaural_hrtf.py

## Import Cycles
- None detected.

## Communities (24 total, 14 thin omitted)

### Community 0 - "test_atmossplit.py"
Cohesion: 0.06
Nodes (17): generate_714_channel_check(), audit_system_environment(), generate_synthetic_polyphonic_test_audio(), run_benchmark(), AudioProbeResult, verify_audio_file(), ExportFormat, CachedStemMetadata (+9 more)

### Community 1 - "main_window.py"
Cohesion: 0.07
Nodes (18): Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura), Corrigido & Aprimorado (Mixagem Profissional Dolby Atmos & Correção de Mapeamento ETSI TS 103 420), AcousticAnalyzer, StemAcousticProfile, AutoAtmosDirector, DirectorPreset, BinauralHRTFEngine, SpeakerPosition714 (+10 more)

### Community 2 - "SpatialPlacement"
Cohesion: 0.07
Nodes (13): Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos), StemTrack, SpatialPlacement, MasterRenderer714, RenderConfig, SpatialSection, SpatialTimelineManager, test_k_weighted_lufs_loudness_and_true_peak() (+5 more)

### Community 6 - "SamsungDLNABridge"
Cohesion: 0.11
Nodes (10): [1.2.0] - 2026-11-19, [1.3.0] - 2026-11-19, [1.3.1] - 2026-11-19, [1.3.2] - 2026-11-19, [1.4.0] - 2026-11-19, [1.5.0] - 2026-11-19, Adicionado & Otimizado, Adicionado & Otimizado (+2 more)

### Community 8 - "TimelineWidget"
Cohesion: 0.07
Nodes (12): 1. Visão Geral e Objetivo do Sistema, 2. Mapa Estrutural do Repositório, 3. Pipeline Passo a Passo, 4. Restrições Críticas de Hardware, SO e Ambiente, 5. Configurações Globais e Dependências, 6. Instruções Críticas para IAs que Modificarem Este Código, 7. Histórico de Versões e Decisões Críticas Recentes, AtmosSplit — Documento Mestre de Arquitetura e Contexto Integral (+4 more)

### Community 10 - "file_source.py"
Cohesion: 0.11
Nodes (8): AudioMetadata, AudioSource, calculate_file_sha256(), extract_metadata_from_file(), load_audio_file(), AudioExporter714, test_exporter_multichannel_mkv_and_wav(), test_file_source_and_sha256()

### Community 14 - "StemCacheManager"
Cohesion: 0.10
Nodes (5): StemCacheManager, _do_clear(), test_cache_statistics_and_cleanup(), test_probe_verifier(), test_stem_cache_manager()

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
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 214 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `test_atmossplit.py`, `main_window.py`, `SpatialPlacement`, `RoomView714`, `SearchSourceEngine`, `.__init__`, `SamsungDLNABridge`, `TimelineWidget`, `LiveSpatialPlayer`, `file_source.py`, `StemControlCard`, `.seek`, `StemCacheManager`, `.get_active_edit_section`, `._load_and_process_audio_path`, `._on_stems_ready`, `SamsungDLNABridge`?**
  _High betweenness centrality (0.240) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `MainWindow` (e.g. with `4. Restrições Críticas de Hardware, SO e Ambiente` and `AudioSource`) actually correct?**
  _`MainWindow` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `QT_QPA_PLATFORM`, `QT_ENABLE_HIGHDPI_SCALING` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_atmossplit.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06234177215189873 - nodes in this community are weakly interconnected._
- **Why does `RoomView714` connect `RoomView714` to `test_atmossplit.py`, `main_window.py`, `SpatialPlacement`, `SamsungDLNABridge`, `MainWindow`, `StemControlCard`, `.get_active_edit_section`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SpatialPlacement` (e.g. with `LiveSpatialPlayer` and `MasterRenderer714`) actually correct?**
  _`SpatialPlacement` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `main_window.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07067307692307692 - nodes in this community are weakly interconnected._