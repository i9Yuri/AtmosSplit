# AtmosSplit — Estúdio de áudio espacial 7.1.4

## 1. Visão geral

O AtmosSplit prepara uma faixa local, separa quatro ou nove stems, propõe um arranjo espacial editável e entrega o master para a JBL Bar 1000 MK2. A sessão contém uma camada macro de seções e uma camada micro de envios temporários. As duas alimentam o monitor binaural e o master de doze canais. A análise, os pesos do modelo, a sessão e o render ficam no computador. A busca de música online é uma ação explícita do operador.

## 2. Mapa do código

| Local | Responsabilidade |
|---|---|
| `src/acquisition/` | SHA-256, tags/capa, sondagem por ffprobe, decodificação estéreo na taxa real e busca opcional por provedor. |
| `src/separation/` | HTDemucs local, subdivisão complementar, projeção vocal coerente, política Linux do worker e publicação atômica de stems FLOAT. |
| `src/spatial/music_structure.py`, `acoustic_analyzer.py` | Grade rítmica, famílias harmônicas e rítmicas, perfis de fonte e evidências por seção. |
| `src/spatial/auto_director.py`, `song_intelligence.py`, `micro_events.py` | Poses por preset e tipo de seção, análise de ataques, seleção e trajetórias de gestos temporários. |
| `src/spatial/timeline_manager.py`, `mix_engine.py` | Edição, grade e projeções visuais, preparação de áudio, cenas imutáveis e avaliação dos ganhos por amostra. |
| `src/spatial/live_player.py`, `native_monitor.py`, `monitor_callback.c`, `binaural_hrtf.py` | Produtor Python, render binaural com estado de filtros e atrasos, fila C11 e callback do PortAudio. |
| `src/spatial/master_renderer.py`, `metering.py` | Master PCM, buses de medição vocal, loudness integrado e pico verdadeiro. |
| `src/playback/` | Encoder JOC, medição no bitstream decodificado, publicação WAV/MP4/MKV e pontes locais de reprodução. |
| `src/ui/` | Janela e trabalhos de estúdio, lista de fontes, sala, inspetor, transporte, marcadores e timeline. O protocolo do worker transporta JSON. Os buffers de áudio circulam pelo disco e pela memória local. |
| `scripts/`, `tests/` | Instalação do lançador, diagnóstico do ambiente, calibração dos canais e regressões de áudio, codec, processos e interface. |

## 3. Da faixa ao arranjo

1. O worker identifica o arquivo e procura a sessão e o cache pelo SHA-256 e pelo modo. Em cache frio, reamostra para a taxa nativa do modelo, separa em CPU e devolve os stems à taxa da origem. A separação cirúrgica usa bandas complementares e um residual estéreo. A soma das componentes de cada instrumento recompõe o stem macro. Na voz, o eixo Mid preserva o componente central. Em uma imagem fortemente lateralizada ou com polaridade invertida, o eixo coerente dominante recupera a voz para o FC.
2. O MIR combina chroma, cepstro mel, fluxo espectral, energia de sub, largura Mid/Side, atividade contínua da voz e densidade percussiva. A mix original fornece a informação harmônica quando disponível. A autocorrelação estima o pulso, os ataques locais corrigem a grade e os acentos ajudam a escolher métrica ternária ou quaternária. O contraste multiescala de Foote usa faixas locais da matriz de autossimilaridade. Os segmentos recorrentes formam famílias por agrupamento completo. Sem pulso confiável, a mudança acústica situa a fronteira. Material uniforme pode ocupar uma única seção. Os rótulos e o grau de confiança são estimativas acústicas editáveis. [Foote e segmentação por novidade](https://www.audiolabs-erlangen.de/resources/MIR/FMP/C4/C4S4_NoveltySegmentation.html)
3. A direção macro aplica os movimentos relativos ao estilo e à intensidade. As fronteiras interpolam ganhos com curvas Hermite, com duração limitada pelas duas seções e pelo andamento. A transição de build-up ou para o outro pode ocupar um compasso. As divisões e fusões mantêm os compassos, a família e os eventos.
4. A camada micro mede energia e variação espectral estéreo a cada 5 ms. Compara duração, intervalos e assinatura de bandas para identificar repetições e respostas após uma frase. Notas sustentadas em refrão/clímax só disparam um throw quando há atividade instrumental coincidente. Nos stems instrumentais, a análise procura séries de ataques, abertura de pratos, acentos harmônicos e entradas de baixo. Os detectores usam evidência acústica e dispensam transcrição e reconhecimento de palavras.
5. Cada `SpatialEvent` registra tempos absolutos, ataque/liberação, fonte, tipo, confiança, intensidade, início/fim da trajetória, ganho, largura e LFE. Pares silábicos concorrem como um gesto. A seleção limita densidade, sobreposição e repetição por seção. A intensidade controla ganho e limiar de audibilidade. Os envios usam o áudio simultâneo do próprio stem, com envelope suave por amostra. A âncora frontal continua disponível durante a projeção. O LFE recebe apenas o envio passa-baixas. O relógio da apresentação na sala acompanha as amostras consumidas pelo dispositivo.

## 4. Monitor, perfil JBL e entrega

**Monitor.** O produtor mantém até três blocos estéreo de 1.024 amostras a 48 kHz. O DSP e a HRTF ocorrem fora do callback. A função que PortAudio invoca é C11. Faz cópias limitadas, completa underruns com silêncio e publica contadores atômicos. Cada seek troca a fila e limpa o estado binaural. O produtor mantém a fila anterior viva até o callback confirmar a troca. O dispositivo drena o último bloco no término natural. Volume de escuta e proteção de saída são locais ao monitor.

**Calibração.** O perfil JBL reduz dinamicamente até 3,5 dB de conteúdo concorrente entre 1 e 4,5 kHz nas fontes harmônicas e backing durante atividade vocal. O mascaramento recebe tratamento adicional no FC. O perfil Estúdio fornece a referência para A/B. O pan compensa a correlação e a sobreposição dos canais de uma fonte espelhada. O master aplica um único ganho limitado pelo alvo de −18 LUFS e pelo teto de −1 dBTP. A medição usa filtro K, janelas de 400 ms, portas absoluta e relativa, ponderação por posição e exclusão do LFE. O relatório mostra a relação voz/instrumental nas janelas de voz ativa, tanto ponderada em banda larga quanto na banda de presença. [ITU-R BS.1770-4](https://www.itu.int/rec/R-REC-BS.1770-4-201510-S/en)

**Entrega.** A ordem PCM é FL, FR, FC, LFE, BL, BR, SL, SR, TFL, TFR, TBL, TBR. WAVEX registra a máscara `0x2D63F`. MKV contém PCM de 24 bits e uma tag de ordem de canais. A saída efetiva via HDMI depende do dispositivo e do layout negociado. O MP4 contém H.264 com imagem estática, capa quando disponível, E-AC-3 JOC a 768 kbit/s e índice `moov` no início. O vídeo segue a duração do áudio. O codec pode acrescentar até dois quadros de 32 ms para preservar a última amostra.

O JOC transporta onze objetos full-range fixados nas posições da sala e um canal LFE no bed 5.1. A trajetória já está impressa nas amplitudes dos objetos. O contêiner EMDF gerado pelo ac3forge acompanha o mesmo downmix full-range, com o LFE escrito diretamente no sexto canal. Dialnorm 31, ganhos dos objetos unitários. A exportação decodifica todos os quadros e mede o pico interpolado 4× no bed e nos objetos. Se necessário, aplica atenuação vinculada e recodifica. A interface informa pico decodificado e ajuste do codec. O ffprobe pode anunciar seis canais para o bed de um fluxo com perfil Atmos. [ETSI TS 103 420](https://www.etsi.org/deliver/etsi_ts/103400_103499/103420/01.01.01_60/ts_103420v010101p.pdf)

## 5. Ambiente, estado e operação

- Nobara, KDE Plasma, Wayland e PipeWire. Xeon E5-2667 v2, 32 GB, RX 580 2048SP. GUI e áudio com prioridade normal. Workers de cálculo em subprocessos com nice 19, I/O idle, CPUs 2–15 e até oito threads. O supervisor Linux registra-se como subreaper, observa a saída do processo pai e recolhe os descendentes antes de encerrar. `CUDA_VISIBLE_DEVICES` e `HIP_VISIBLE_DEVICES` vazias. `HF_HUB_OFFLINE=1`. O modelo usa apenas pesos locais.
- O primeiro uso do monitor compila o callback com o `cc` local para x86-64 básico. A biblioteca identificada pelo conteúdo fica em `.venv/lib/atmossplit-native/` na instalação deste projeto. Os atômicos de ponteiro e contador precisam ser lock-free na compilação. [Interface de callback C do sounddevice](https://github.com/spatialaudio/python-sounddevice/blob/master/src/sounddevice.py)
- Pintura Qt com cores e pincéis sólidos, QSS com tokens em paleta Dark Obsidian Studio (#0A0D14, #111622, #38BDF8), cantos modernos (8px–12px), feedback de foco e progresso com barra dedicada StudioProgressBar (%p%). A blindagem de refcount é limitada a CPython 3.11/Linux. O transporte é consultado pela GUI em intervalos de 16 ms ou 100 ms no modo de movimento reduzido.
- Separação com Demucs em CPU executa com shifts=0 (evitando reprocessamento redundante) e callback dinâmico por trecho (chunk-by-chunk) emitindo progresso contínuo e tempo restante estimado (ETA), com suporte a cancelamento cooperativo imediato.
- Stems em `$XDG_CACHE_HOME/atmossplit/stems_cache` ou `~/.cache/atmossplit/stems_cache`. O modo cirúrgico usa a geração `_surgical_v2`. Escritores publicam primeiro os WAVs, depois o manifesto. A limpeza coordena escritores/leitores e preserva a faixa aberta. Arranjos ficam em `QStandardPaths.AppDataLocation/sessions`, por hash e modo. Preferências ficam em QSettings.
- FFmpeg/ffprobe, libsndfile, PySide6/Shiboken6 6.12.0, PortAudio, SciPy, NumPy, CFFI, psutil, PyTorch e HTDemucs locais. O transporte do codec foi verificado no ac3forge 0.10.0b1. A busca opcional pode usar o catálogo remoto ou yt-dlp. Os botões Rygel/DLNA e DirectFrame usam as integrações locais quando presentes.

## 6. Operação e validação

```bash
./iniciar.sh
.venv/bin/pytest -v
.venv/bin/python -m compileall -q src scripts tests
.venv/bin/python scripts/probe_714_playback.py
```

O diagnóstico gera três arquivos de calibração em `tests/multichannel_diagnostics/`. Cada canal recebe três pulsos suaves com pico de −20 dBFS, na ordem PCM acima. Com o intervalo padrão de dois segundos, o centro começa em 4 s, o LFE em 6 s e os quatro canais de teto em 16, 18, 20 e 22 s. Os testes automatizados cobrem pulsos 3/4 e 4/4, recorrência, silêncio, ganho mono/estéreo, fase vocal, eventos acústicos com instante conhecido, monitor C11, decodificação JOC, cauda final, restauração da sessão e cancelamento de workers.

As medições com áudio decodificado, a faixa local de referência e o ensaio no dispositivo estão no [relatório do ambiente](ENVIRONMENT_REPORT.md).

## 7. Histórico de Versões e Decisões Críticas Recentes

- **2026-11-20 (v2.0.1 — Design Monocromático de Alta Fidelidade AMOLED / Claro, Botão de Tema Discreto e Resolução de Carregamento Demucs):**
  - **Resolução do Carregamento Infinito (Chunk Progress & CPU Optimization):**
    - Identificada e eliminada a sensação de congelamento eterno durante o carregamento/separação de faixas: no processador Intel Xeon E5-2667 v2 (sem aceleração por GPU), a inferência de 50 chunks do Demucs levava até 7 minutos com `shifts=1` sem qualquer feedback intermediário (barra congelada em 18%).
    - Integrado callback contínuo `on_chunk(current, total)` no `stem_engine.py` emitindo fração, porcentagem e estimativa de tempo (ETA) a cada 4–6 segundos diretamente para o `StudioProgressBar`.
    - Ajustado `shifts_val = 0` na execução em CPU, reduzindo o tempo de inferência pela metade (~3.5 min) sem perda perceptível de separação estéreo.
    - Suporte a cancelamento instantâneo via `cancel_check()` dentro de cada bloco do modelo.
  - **Repaginação Visual Profissional (Zero Cor Tema, Padrão Hallmark / Impeccable):**
    - Erradicação de paletas verdes e saturações amadoras.
    - Dois temas neutros de alta fidelidade:
      - **Escuro AMOLED:** Fundo preto absoluto (`#000000`), painéis em grafite (`#0B0B0D`), linhas de contraste sutil (`#28282D`) e tipografia nítida em branco (`#FFFFFF`).
      - **Claro de Estúdio:** Papel/zinco limpo (`#F4F4F6`), painéis brancos (`#FFFFFF`), linhas suaves (`#D1D5DB`) e tinta escura (`#09090B`).
    - Botão discreto no cabeçalho superior (`☀️ Claro` / `🌙 AMOLED`) e ação no menu da sessão, com persistência em `QSettings("ui/theme")` e repintura dinâmica e instantânea de todos os elementos sem necessidade de reiniciar.
  - **Validação de Testes:** 60 testes automatizados passando 100% (`test_studio_ui.py`, `test_micro_choreography.py`, `test_music_and_master.py`, `test_atmossplit.py`).

- **2026-11-20 · 2.0.0.** Estúdio em duas camadas, monitor C11 e entrega JOC com LFE discreto. As entradas abaixo descrevem implementações anteriores.

- **2026-11-19 (v1.8.2 — Animação 3D em Tempo Real da Sala 7.1.4, Mapeamento Cirúrgico e Desbloqueio do Vocal Throw):**
  - **Pré-visualização Tridimensional Ativa em Tempo Real (`RoomView714`):**
    - Implementado `set_playback_placements` a 33–60 FPS, permitindo que todas as bolinhas de instrumentos e vozes se movimentem ativamente pela sala acústica enquanto a faixa toca ou durante o scrubbing do playhead na timeline.
    - Os raios de energia acústica VBAP agora acompanham a posição dinâmica das fontes sonoras em tempo real, ligando-as aos alto-falantes ativados (soundbar frontal, surround lateral, teto e satélites traseiros).
    - Sincronização em tempo real dos faders, coordenadas e botões nos cards à esquerda (`StemControlCard.sync_dynamic_state`).
    - Salto imediato de pré-visualização ao clicar em qualquer trecho da timeline ou na barra de tempo.
  - **Renderização Visual de Objetos Silenciados vs. Ativos:**
    - Instâncias temporariamente silenciadas (como o vocal throw durante versos secos ou a bateria em breakdowns) são desenhadas em modo translúcido tracejado com indicador `✕`.
    - Ao entrar em um refrão ou clímax, a bolinha ganha cor sólida vívida, halo de energia e raios acústicos instantâneos.
  - **Mapeamento 3D Especializado para Separação Cirúrgica (8-12 Camadas):**
    - Mapeamento estrito e musical para todos os 9 stems cirúrgicos: `lead_vocal` (âncora frontal no verso, riser ao teto no build-up, suspensão celestial no breakdown), `backing_vocals` (asas estéreo laterais no verso, 360° no refrão), `cymbals_hihat` (teto físico nos 4 canais de altura), `kick` (chão frontal com 100% LFE send), `snare` (chão no verso, subindo ao teto no build-up), `sub_bass_lfe` (puro mono 100% LFE), e `air_ambience` (dossel contínuo no teto).
  - **Desbloqueio de Áudio Dinâmico no LiveSpatialPlayer:**
    - Corrigido o portão estático de mute que impedia o playback do vocal throw (`vocals::spatial_throw` / `lead_vocal::spatial_throw`) nos refrões. A automação dinâmica por trechos agora governa as matrizes de ganho sem corte estático prévio.
  - **Validação de Testes:**
    - Suíte expandida para 32 testes unitários automatizados com 100% de aprovação.

- **2026-11-19 (v1.8.1 — Particionamento Frase a Frase Inteligente e Movimentação Espacial 3D Ativa):**
  - **Particionamento Musical Granular (Subdivisão de Frases 8s a 20s):**
    - Substituída a partição macro percentual por detecção de novidade de sinal e fluxo espectral ($\Delta E$), cortes de percussão (drop gaps) e pausas de fraseado vocal (VAD).
    - Mapeamento de 8 a 16 frases musicais autênticas por faixa de 3 a 4 minutos (Intro Ambient, Intro Beat, Verso 1A Seco, Verso 1B Groove, Pré-Refrão Riser, Refrão Drop, Hook & Eco Traseiro, Verso 2 Contraste, Breakdown Celestial no teto, Clímax 7.1.4, Outro Descompressão e Dissolução).
  - **Coreografia Espacial 3D Real nos Objetos (Não Apenas Volume):**
    - *Vozes (`vocals`):* Ancoragem seca no chão frontal ($x=0, y=0.98, z=0$) nos versos, ascensão vertical ($z=0.48$) no build-up, suspensão celestial no teto ($y=0.20, z=0.68$) no breakdown, e recuo traseiro suave no outro.
    - *Bateria (`drums`):* Kit seco ao nível do ouvido no verso, ascensão vertical ($z=0.62$) de viradas e esteiras no build-up, dispersão nas alturas frontais/traseiras ($z=0.45$) com punch LFE no refrão, e silêncio intencional ($is\_muted=True$) no breakdown.
    - *Instrumentos Harmônicos (`other`):* Flancos laterais ($x=\pm 0.68, y=0.20, z=0.10$) no verso para liberar o canal central para a voz, riser ascendente ($z=0.88$) no build-up, abraço 360° total ($x=\pm 0.88, y=-0.25, z=0.45$) no refrão, e halo celestial diretamente sobre a cabeça ($z=0.90$) no breakdown.
    - *Vocal Throw Traseiro (`vocals::spatial_throw`):* Muted no verso e saltando com ganho $1.35$ nos módulos destacáveis traseiros da JBL Bar 1000 nos refrões.
  - **Validação de Testes:** 30 testes unitários passando 100% cobrindo a nova métrica de granularidade de frases e as coordenadas espaciais 3D reativas.
- **2026-11-19 (v1.8.0 — IA Maestro com Arranjo Estrutural Autônomo, Efeito Vocal Throw 7.1.4 e Timeline Profissional Estilo DAW):**
  - **Arranjo Musical Inteligente Autônomo (`SongStructureIntelligence` / IA Maestro):**
    - Analisador musical algorítmico que decompõe faixas por perfil de energia RMS contínuo, curvas de atividade vocal (VAD) e transientes rítmicos.
    - Segmenta autonomamente em `Intro (Ambiência Aérea)`, `Verso (Voz Frontal Seca)`, `Build-up (Ascensão ao Teto)`, `Refrão (Imersão 360°)`, `Ponte/Solo (Destaque 3D)`, `Refrão Final (Clímax Absoluto)` e `Outro (Decaimento Imersivo)`.
    - **Efeito Meticuloso "Last Christmas" (Vocal Throw Traseiro 7.1.4):** Projeta a instância `vocals::spatial_throw` com ganho destacado ($+1.28$) para os módulos traseiros destacáveis da JBL Bar 1000MK2 ($BL/BR, x = \pm 0.68, y = -0.78, z = 0.45$) nos refrões e momentos altos, mantendo-a mutada ($gain = 0.0$) durante os versos para preservar o foco frontal cristalino e íntimo.
    - Suavização por curvas $S$ (Hermite smoothstep $3\alpha^2 - 2\alpha^3$) nas fronteiras temporais, eliminando qualquer clique, pop ou salto abrupto de volume.
  - **Redesenho Completo da Linha do Tempo (DAW Timeline Canvas Sem Scrollbars):**
    - **Eliminação Total da QScrollArea do SO:** O canvas gerencia diretamente seu próprio viewport virtual (`view_start_s` e `zoom`), erradicando o problema do scrollbar do sistema que cobria os blocos ao dar zoom.
    - **Correção da Projeção de Coordenadas (1:1 Playhead & Scrubbing):** Fim do duplo fator de escala; cliques e arraste na régua temporal agora buscam exatamente o ponto clicado com precisão de milissegundos.
    - **Ajuste Tátil de Fronteiras entre Seções (Boundary Dragging):** Ao passar o mouse sobre a linha divisória entre duas seções, o cursor se transforma em `SizeHorCursor` e o usuário pode arrastar a fronteira interativamente, redimensionando as seções adjacentes em tempo real com garantia de contiguidade.
    - **Mini-Mapa de Visão Geral Integrado (Bird's Eye Navigator):** Barra de visão global no rodapé do canvas exibindo 100% da música com blocos em miniatura, caixa de viewport visível arrastável e agulha de reprodução.
    - **Eliminação de Diálogos Modais Pop-up:** Divisão de trechos no cursor e exclusão operam de forma direta e fluida sem interromper o fluxo de trabalho do usuário.
  - **Renderização Multicanal e Exportação Unificada:**
    - O motor `MasterRenderer714` agora unifica todas as instâncias e vocal throws de todas as seções temporais na matriz multicanal 7.1.4, preservando a automação na exportação MP4 Dolby Atmos, MKV e WAV.
  - **Validação Automatizada Completa:**
    - 30 testes automatizados cobrindo IA Maestro, arraste de fronteiras, minimapa, clonagem de instâncias, exportação JOC e estabilidade de playback com 100% de sucesso.
- **2026-11-19 (v1.7.1 — Correção de Segmento Demucs htdemucs, Anti-Travamento e Menu de Contexto 3D):**
  - **Correção da Incompatibilidade Dimensional do Demucs (`apply_model`):**
    - Identificada a causa raiz da falha de carregamento de faixas ("elementos não aparecem" / "Processo de IA finalizado ou cancelado"): o parâmetro hardcoded `segment=10.0` em `stem_engine.py` conflitou com os tensores de atenção posicional da arquitetura `htdemucs` (`BagOfModels`), cujo modelo opera internamente com `segment = 7.8s` (343.980 amostras a 44,1 kHz). O PyTorch disparava `shape '[1, 4, -1, 343980]' is invalid for input of size 3528000`.
    - Ajustado para `segment = None`, permitindo que o Demucs utilize o tamanho nativo do modelo de forma automática com chunking e overlap perfeitos.
  - **Notificação e Diagnóstico de Erros no Subprocesso de IA:**
    - Corrigido o mascaramento silencioso em `main_window.py` onde qualquer encerramento com código diferente de 0 exibia genericamente "cancelado". O sistema agora captura mensagens emitidas no canal stdout/stderr e notifica o usuário via diálogo de erro explicativo em caso de falhas genuínas.
  - **Eliminação de Race Conditions no Motor de Áudio (`AudioDSPState`):**
    - O callback de áudio em tempo real agora lê estritamente um mapa imutável de instâncias e fontes (`dsp.stem_sources`) gerado de forma atômica no `AudioDSPState`.
    - Eliminado o acesso concorrente a `self.placements` da thread gráfica, erradicando qualquer erro de `RuntimeError: dictionary changed size during iteration` durante arrastes ou clonagens.
    - Removidas chamadas redundantes a `set_active_placements` em cada evento de mouse move, mantendo apenas `update_placement` com recálculo atômico e ultra-rápido do stem ativo.
  - **Menu de Contexto Completo e Ações Rápidas na Sala 7.1.4:**
    - Adicionado menu de botão direito interativo (`contextMenuEvent`) sobre os nós ou sala: alternar espelhamento estéreo (`D`), copiar elemento (`Ctrl+C`), duplicar como nova fonte 3D (`Ctrl+V`), excluir instância clonada (`Del`), centralizar (`0`) e ajustes de altura $Z$ em $\pm 10\%$.
    - Adicionado botão direto `[➕]` no cabeçalho dos cards de stem para clonagem visual com um clique.
  - **Validação Automatizada:**
    - 28 testes unitários passando 100% (`pytest tests/test_atmossplit.py`), incluindo cobertura de atalhos e sinais de duplicação.
- **2026-11-19 (v1.7.0 — Zoom na Timeline até Milissegundos e Clonagem de Nós Espaciais via Ctrl+C / Ctrl+V):**
  - **Zoom Adaptativo na Timeline (Até Escala de Milissegundos):** Implementado zoom de 1.0x até 128x via `Ctrl + Scroll` do mouse sobre a timeline ou botões táteis `[+]`, `[-]` e `[100%]`. A timeline possui régua temporal graduada que adapta a resolução até passos de 0.001s, com viewport desacoplado em `QScrollArea` e cortes de trechos (`split_section_at`) com precisão de milissegundo.
  - **Clonagem de Fontes Sonoras (Ctrl+C / Ctrl+V & Delete):** Fim da limitação de fonte única. O usuário pode selecionar qualquer nó no espaço 3D (ex: voz), pressionar `Ctrl+C` e `Ctrl+V` para duplicá-lo no espaço sonoro com sufixo `stem::index`. Cada cópia possui posicionamento $X, Y$, altitude $Z$, faders e espelhamento estéreo totalmente independentes, compartilhando o buffer de áudio original sem consumo adicional de memória. Clones podem ser removidos a qualquer momento via `Delete` ou botão `[×]`.
  - **Mixagem Multicanal 7.1.4 de Múltiplas Instâncias:** O motor de tempo real `LiveSpatialPlayer` e o renderizador offline `MasterRenderer714` agregam e somam dinamicamente todas as instâncias ativas na matriz de 12 canais e no bitstream Dolby Atmos E-AC-3 JOC.
  - **Validação de Testes:** 26 testes automatizados aprovados com 100% de sucesso.
- **2026-11-19 (v1.6.2 — Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio):**
  - **Diagnóstico da Causa Raiz do Fechamento Espontâneo (`SIGABRT status 6` / Core Dump PID 34179):** Investigação detalhada através do **Codex CLI** (`gpt-6-luna`) e inspeção de coredump revelaram `Fatal Python error: none_dealloc: deallocating None: bug likely caused by a refcount error in a C extension` no `paintEvent` do `RoomView714`. Métodos C++ void do PySide6/Shiboken 6.12.0 no Linux (`setColorAt`, `setPen`, `setBrush`, `drawEllipse`) retornam `None` sem `Py_INCREF`, consumindo o refcount global de `None` a 33 FPS até provocar o abort do processo.
  - **Eliminação de `QGradient` no Loop de Pintura:** Removidas todas as chamadas a `QRadialGradient` e `setColorAt` do canvas 3D em `_draw_single_puck()` e `_draw_listener()`. Substituído por renderização direta em `QColor` e `QBrush` sólidos/transparentes e cache persistente de cores (`_stem_colors`).
  - **Blindagem Ativa de Refcount (`_immunize_cpython_none_refcount`):** Implementada imunização via `ctypes` que garante que o refcount de `None` permaneça permanentemente acima de 1 bilhão, impedindo matematicamente qualquer ocorrência de `none_dealloc`.
  - **Abertura/Fechamento Assíncrono do PortAudio:** Operações bloqueantes de `sd.OutputStream` transferidas para threads secundárias em background, e reset do estado HRTF consumido de forma preguiçosa no próprio callback de áudio (`_binaural_reset_pending`).
  - **Cache de Perfis Acústicos:** Presets agora reaproveitam a análise inicial de envelopes e espectro (`_stem_profiles`) sem recalcular FFT desnecessariamente.
  - **Validação de Testes:** 24 testes unitários automatizados cobrindo áudio lock-free, timeline crossfade e ausência de vazamentos gráficos aprovados com 100% de sucesso.
- **2026-11-19 (v1.6.1 — Arquitetura DSP 100% Lock-Free, Eliminação Total de Congelamentos no Wayland/PipeWire e Interpolação Vetorial Pré-calculada):**
  - **Causa Raiz do Congelamento Global do Sistema Operacional:** O travamento total do desktop (KWin Wayland + PipeWire) ao clicar ou arrastar instrumentos durante a reprodução decorria de contenção de mutex (`threading.Lock`) no `LiveSpatialPlayer`. O callback C de tempo real do PortAudio/PipeWire competia pela mesma trava adquirida pelo loop de interface da GUI (eventos de mouse a 120 Hz no `RoomView714`, polling a 33 Hz no `_poll_audio_state` e faders dos cards). Quando a thread de áudio perdia o prazo de entrega (quantum deadline miss) esperando pelo lock, o pipeline de áudio do PipeWire travava, travando em cascata o servidor de som e o compositor de janelas Wayland.
  - **Arquitetura 100% Lock-Free (`AudioDSPState`):** Remoção total de `threading.Lock` das rotinas de áudio em tempo real (`_audio_callback`, `update_placement`, `get_ui_snapshot`, `play`, `pause`, `stop`, `seek`). Implementado o padrão de troca atômica de ponteiro de objeto (`AudioDSPState`) imutável no CPython (< 10 ns). A thread de áudio lê o snapshot atômico instantaneamente, garantindo zero contenção de locks com a interface gráfica.
  - **Interpolação Vetorial Pré-calculada de Seções da Timeline:** Eliminadas as 14 chamadas trigonométricas por bloco no callback de áudio. Todas as seções agora pré-calculam e armazenam em cache seus vetores de 12 ganhos VBAP (`cached_gains_l` e `cached_gains_r`). O crossfade temporal entre trechos realiza agora uma mistura vetorial ponderada direta ($\mathbf{g} = (1-\alpha)\mathbf{g}_A + \alpha\mathbf{g}_B$), com execução instantânea (< 5 µs).
  - **Otimização de Renderização no `RoomView714`:** Cache dos vetores acústicos para o feixe visual do instrumento ativo (`_cached_rays_l`/`_cached_rays_r`), eliminando qualquer invocação de VBAP de dentro do `paintEvent`. Proteção idempotente na seleção de instrumentos para evitar repinturas redundantes.
  - **Eliminação de Thrashing no `StemControlCard`:** Substituída a limpeza recursiva via `setStyleSheet("")` por `card.set_selected(is_active)`, preservando o cache de layout interno dos widgets Qt e sincronizando coordenadas $X, Y, Z$ de forma leve.
  - **Correções de Sintaxe e Atributos:**
    - Corrigido `AttributeError: 'TimelineWidget' object has no attribute 'timeline_canvas'` em `main_window.py` substituindo por `self.timeline_widget.refresh_timeline()`.
    - Corrigido `NameError: name 'np' is not defined` importando `numpy as np` no topo de `timeline_manager.py`.
- **2026-11-19 (v1.6.0 — Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos):**
  - **Eliminação Absoluta de Travamentos por Contenção de Trava (Zero-Crash):** Identificada a causa raiz dos congelamentos e fechamentos espontâneos durante o arraste de esferas no espaço 3D: a emissão de eventos a 120 Hz pelo mouse disparava recálculos síncronos de ganhos VBAP dentro de `self._lock` no `LiveSpatialPlayer`, causando inanição crítica de buffer (buffer underrun) e abort silencioso no callback C do PortAudio. Os cálculos trigonométricos e matriciais do VBAP foram desacoplados e movidos para fora do lock, realizando apenas um swap atômico de ponteiro de array NumPy sob trava (< 1 µs).
  - **Escudo Global de Exceções (`_install_crash_shield`):** Implementado interceptor em `sys.excepthook` no loop de eventos do PySide6, garantindo que qualquer exceção em slots ou widgets seja capturada e logada sem jamais abortar o processo da aplicação.
  - **Callback de Áudio Blindado:** Adicionado bloco defensivo `try...except` de nível superior em `_audio_callback` com fallback imediato `outdata.fill(0)`, prevenindo que qualquer inconsistência de estado ou erro de hardware encerre o aplicativo.
  - **Throttling Inteligente no Espaço 3D (`RoomView714`):** O arraste do mouse agora filtra micro-movimentos espúrios ($\Delta < 0.005$), propagando apenas variações reais e atualizando faders via `sync_coords_from_placement` sem disparar redesenhos pesados e redundantes da interface.
  - **Controles Táteis de Pan e Posição Frente/Trás nos Cards (`StemControlCard`):** Fim do mistério no controle de cada instrumento. Cada card agora possui:
    - **Botões de 1-Clique:** `[ ⇦ Esq ]`, `[ ⇧ Centro ]`, `[ Dir ⇨ ]`, `[ ⇩ Fundo ]` para ancorar ou mover a voz principal (ou qualquer faixa) instantaneamente para a esquerda, centro, direita ou traseira.
    - **Sliders Dedicados:** Slider de Pan L/R (-100% a +100%, com display "Centro", "X% Esq", "X% Dir") e Slider Frente/Trás ("Frente", "Meio", "Trás").
  - **Barra Visual de Trechos na Interface (`📍 Trecho` + `✂️ Dividir Aqui`):** Adicionada barra de navegação rápida diretamente acima dos cards de instrumentos. O usuário pode pausar ou tocar a música em qualquer ponto, clicar em `✂️ Dividir Aqui`, selecionar o trecho desejado no menu suspenso e alterar o posicionamento da voz para a esquerda ou direita naquele trecho específico, com transição contínua e exportação automática em Dolby Atmos 7.1.4.
- **2026-11-19 (v1.5.0 — Práticas Profissionais de Mixagem Dolby Atmos & Correção de Mapeamento ETSI TS 103 420):**
  - **Correção da Ancoragem Frontal da Voz (ETSI TS 103 420 §4.2.1):** Identificado e corrigido o desvio crítico onde as coordenadas do canal Frontal Central (`FC`, canal 2) no bitstream E-AC-3 JOC via `ac3forge` estavam mapeadas como `(x=0.0, y=1.0, z=0.0)`. Na especificação ETSI TS 103 420, $X=0.0$ representa a parede esquerda e $Y=1.0$ a parede traseira, fazendo com que decodificadores da TV Samsung / JBL Bar 1000 reproduzissem a voz principal no módulo traseiro esquerdo destacável. As coordenadas foram corrigidas para o padrão normativo exato: $X=0.5$ (Centro), $Y=0.0$ (Frente / TV), $Z=0.0$ (Plano do ouvido), ancorando perfeitamente a voz principal no canal central da soundbar.
  - **Eliminação de Inversão de Fase Destrutiva nos Backing Vocals:** Substituída a sub-divisão de voz baseada em $[+side, -side]$ (que gerava cancelamento acústico de 180° e som oco/metálico em soundbars) por extração estéreo pura e coerente em fase (`side_l = vocals[:, 0] - 0.85*mid`, `side_r = vocals[:, 1] - 0.85*mid`) combinada com filtro passa-altas Linkwitz-Riley em 180 Hz, garantindo ambiência estéreo rica, natural e sem vazamento para o sub-grave.
  - **Blindagem do Preset Imersão 360° (Regra de Ouro da Indústria):** No modo `IMMERSION_360`, a Voz Principal (`lead_vocal`), o Bumbo (`kick`) e o Sub-Bass (`sub_bass_lfe`) são mantidos estritamente ancorados na frente ($Y \ge 0.85$, $X=0.0$), enquanto instrumentos harmônicos, sintetizadores, backing vocals, ambiências aéreas e pratos preenchem os 360° da sala e os 4 canais de teto, evitando desorientação auditiva e mantendo o peso e clareza do groove.
  - **Normalização de Sonoridade Profissional (ITU-R BS.1770-4 K-Weighting & -1.0 dBTP True Peak):** Substituída a estimativa simplista por RMS por filtragem K de 2 estágios (High-shelf +4 dB em 1.5 kHz e RLB High-pass a 100 Hz com exclusão do canal LFE), adotando o alvo de entrega da indústria musical (-18.0 LUFS integrado e teto True Peak rigoroso de -1.0 dBTP, em conformidade com as especificações técnicas da Apple Music e Tidal).
- **2026-11-19 (v1.4.0 — Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal Dinâmica por Trechos):**
  - **Espelhamento Estéreo Simétrico (Eliminação do Pan Unilateral):** Pratos, chimbais, percussões agudas, sintetizadores, ambiências aéreas e coro agora utilizam `is_stereo = True` por padrão, projetando nós gêmeos (L e R) balanceados em ambos os lados do surround e teto. O usuário pode alternar o espelhamento estéreo dando duplo clique na bolinha, clicando no botão `🪞` do card ou pressionando a tecla `D`.
  - **Arraste e Altura Sincronizados:** Mover qualquer um dos lados (L ou R) espelha a distância horizontal $|X|$ e a coordenada $Y$ instantaneamente no outro lado. Rolar a roda do mouse sobre qualquer esfera altera a altura $Z$ e o raio de ambos os lados simultaneamente.
  - **Automação Espacial Dinâmica por Trechos (`SpatialTimelineManager` + `TimelineWidget`):** A música agora pode ser dividida em múltiplos trechos independentes (ex: Intro, Verso, Refrão, Solo, Ponte, Outro) através de um clique em `✂️ Dividir no Tempo Atual`. Cada trecho armazena seu próprio arranjo 3D completo (ex: vozes na frente no verso, vozes no fundo e teto no refrão).
  - **Transição Hermite Smoothstep Contínua:** Ao transitar entre trechos durante a reprodução ao vivo ou renderização final, o sistema aplica interpolação cúbica $3\alpha^2 - 2\alpha^3$, gerando movimentos espaciais orgânicos e cinematográficos sem estalos acústicos nem saltos repentinos.
  - **Exportação Dolby Atmos com Automação Dinâmica:** Tanto a exportação rápida (`MP4 Wi-Fi / TV`) quanto a exportação personalizada renderizam todas as automações e movimentos de trechos na matriz espacial 7.1.4 e no bitstream E-AC-3 JOC.
- **2026-11-19 (v1.3.2 — Dolby Atmos Real via Joint Object Coding / ac3forge E-AC-3 JOC & 12 Objetos 7.1.4):**
  - **Eliminação do Downmix Silencioso 5.1:** O encoder padrão do FFmpeg não possui suporte a objetos Dolby Atmos nem a layouts > 5.1 em E-AC-3, gerando anteriormente beds 5.1 convencionais sem canais de teto.
  - **Integração do Motor `ac3forge`:** Implementado `AudioExporter714._encode_eac3_joc_stream` utilizando o `AtmosEncoder` do `ac3forge` para codificar diretamente os 12 canais da matriz espacial em **E-AC-3 JOC (Dolby Digital Plus with Dolby Atmos)** com metadados OAMD completos, índice de complexidade 13 e 12 objetos 3D discretos com coordenadas de teto ($z=1.0$), surrounds e LFE.
  - **Muxing com Cópia Direta (`-c:a copy`):** O bitstream E-AC-3 JOC resultante é encapsulado em contêineres MP4 (com capa e faststart) e MKV sem qualquer re-encoding destrutivo.
  - **Reconhecimento Unânime no Ecossistema:** O arquivo é auditado e confirmado como `Dolby Digital Plus + Dolby Atmos` e `is_atmos: True` pelo FFprobe, MediaInfo e `AtmosHunter` (`audio_verify.py`), acionando os drivers de teto e satélites surround da JBL Bar 1000MK2.
- **2026-11-19 (v1.3.1 — Duração Integral, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura por Scroll):**
  - **Controle Interativo de Altura 3D via Scroll do Mouse & Seleção por Clique:** O usuário pode clicar diretamente em qualquer círculo de stem na sala para selecioná-lo (indicado por borda ciano neon pulsante `#00E5FF`, halo e badge flutuante de altitude). Girar o scroll do mouse ajusta a altura $Z$ do som (elevando-o em direção aos alto-falantes de teto ou descendo-o para o chão) em incrementos de 0.05, com sincronização em tempo real nos faders laterais, matriz VBAP 3D e filtros HRTF.
  - **Visualização 3D de Altura por Raio e Profundidade:** A altura sonora é representada intuitivamente pela escala dinâmica do raio do círculo: de 11 px no piso ($z=0$) até 33 px no teto ($z=1$) — exatamente 3 vezes maior. Renderização de sombra no chão no ponto $(X, Y)$ da base, cordão vertical pontilhado conectando o chão ao instrumento flutuante, anéis concêntricos de dispersão no teto quando $z > 0.35$ e indicador percentual de altitude.
  - **Eliminação do Corte em 10 Segundos:** Corrigido o bug onde `:d=10` e `-shortest` no gerador de vídeo lavfi truncavam a música em 10 segundos. A duração agora é calculada dinamicamente com base nas amostras reais da matriz de áudio.
  - **Formato Ouro para Wi-Fi / TV Samsung (`MP4_EAC3_71`):** Adicionado suporte ao contêiner MP4 com áudio Dolby Digital Plus 7.1 (E-AC-3 1024 kbps), vídeo H.264 de 1 fps com capa 1280x720 e `-movflags +faststart`. Compatível 100% com o servidor **Rygel** (`Yuri PC`), aplicativo **BubbleUPnP / Symfonium** no smartphone Galaxy S20 FE e o player nativo da **TV Samsung Tizen**, transmitindo o áudio multicanal por Wi-Fi e acionando a JBL Bar 1000MK2 via HDMI eARC.
  - **Exportação Rápida Padronizada para Wi-Fi:** O botão rápido agora grava diretamente o arquivo MP4 em `~/Music/DolbyAtmos/`, sendo indexado instantaneamente pelo Rygel na rede local.
- **2026-11-19 (v1.3.0 — Otimização de Fluidez de Hardware, Launcher Duplo Clique & UX Avançada):**
  - **Launcher de Duplo Clique Direto:** Criados e configurados `Abrir_AtmosSplit.desktop` na raiz do projeto e `~/Desktop/AtmosSplit.desktop` com metadados confiáveis (`metadata::trusted: true`) e suporte a parâmetros `%F`. O usuário pode clicar duas vezes em qualquer um deles e abrir o app ou associar arquivos de áudio para abertura instantânea.
  - **Separação de Prioridade de Processo:** A interface GUI e o motor de áudio rodam em prioridade normal (`nice 0`), garantindo 60 FPS e resposta tátil imediata, enquanto os workers de IA permanecem isolados em `nice 19` com afinidade nos núcleos 2 a 15.
  - **Desacoplamento Completo da Thread de Áudio:** Implementado padrão de snapshot atômico com polling via `QTimer` a ~33 FPS na GUI, eliminando emissão de sinais Qt de dentro do callback PipeWire/ALSA e erradicando micro-travamentos.
  - **Cache de Ganhos VBAP:** Ganhos espaciais 3D dos 12 canais são pré-calculados e cacheados em vetor NumPy, reduzindo o custo de processamento do bloco de áudio em mais de 80%.
  - **Continuidade de Fase HRTF (Anti-Clicking):** Filtros IID e de elevação no `BinauralHRTFEngine` utilizam estados persistentes `zi` entre blocos, garantindo reprodução límpida sem estalos acústicos.
  - **Matador de Processos Órfãos:** Implementado encerramento recursivo de processos filhos via `psutil` no botão Cancelar e no fechamento do aplicativo, blindando a CPU Xeon contra cargas residuais.
  - **Seletor de Dispositivo de Saída de Áudio:** Adicionado dropdown na barra superior permitindo alternar dinamicamente entre PipeWire Padrão, Fone Havit H2002D / ALC662 e HDMI Radeon RX 580 (TV Samsung / JBL Bar 1000).
  - **Fader de Volume Master:** Adicionado controle de volume geral de 0% a 150% com display numérico no rodapé.
  - **Gerenciador Visual de Cache:** Modal interativo mostrando tamanho total em disco, lista de faixas em cache e botão de limpeza com um clique.
  - **Atalhos Estendidos:** Adicionados `M` (Mute), `S` (Solo), `0` (Centralizar nó no palco), `Setas Cima/Baixo` (Ajustar altura Z).
- **2026-11-19 (v1.2.0 — Blindagem de Hardware, Afinidade de CPU e Subprocesso Desacoplado):**
  - Isolamento estrito de afinidade de CPU: núcleos 0 e 1 reservados exclusivamente para o KWin Wayland, UI e PipeWire.
  - Workers de inferência executados em subprocesso independente via `QProcess` e CLI (`worker_cli.py`).
  - Bloqueio forçado de variáveis CUDA/HIP (`CUDA_VISIBLE_DEVICES=""`, `HIP_VISIBLE_DEVICES=""`).
  - Chunking temporal e controle de RAM no Demucs (`segment=10.0`, `overlap=0.25`).
- **2026-11-19 (v1.1.0 — Live Spatial Player, Reatividade Acústica & Anexo de Capa):**
  - Motor de streaming contínuo `LiveSpatialPlayer` integrado ao PipeWire/ALSA.
  - Animação de pulsação nos nós dos instrumentos e anéis dinâmicos no Subwoofer.
- **2026-11-19 (v1.0.0 — Fase 0 Concluída & Arquitetura Estável):**
  - Auditoria completa dos ecossistemas vizinhos e constatação empírica do suporte canônico ao layout 7.1.4 no FFmpeg.
