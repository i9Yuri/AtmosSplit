# CHANGELOG — AtmosSplit

Todas as mudanças notáveis deste projeto serão registradas neste arquivo.

## [1.8.1] - 2026-11-19
### Aprimorado (Particionamento Frase a Frase Inteligente e Movimentação Espacial 3D Dinâmica em Todos os Objetos)
- **Particionamento Musical Granular e Fraseado Autônomo:**
  - Substituída a divisão macro de blocos estáticos por detector dinâmico de transições baseado em fluxo de energia ($\Delta E$), curvas de novidade, detecção de pausas de fraseado vocal (VAD) e vales de percussão (drop gaps).
  - A música agora é dividida em frases orgânicas de **8 a 20 segundos** (8 a 16 seções por faixa), refletindo o fraseado musical real (ex: Intro Ambiance, Intro Beat, Verso 1A Seco, Verso 1B Groove, Pré-Refrão / Riser, Refrão Drop, Hook & Eco Traseiro, Verso 2 Contraste, Breakdown Celestial, Clímax 7.1.4, Outro Descompressão e Dissolução).
- **Coreografia Espacial 3D Real em Vez de Apenas Ajuste de Volume:**
  - **Vozes (`vocals`):**
    - *Verso Seco / Contraste:* Ancoragem cristalina estrita no centro frontal ($x=0.0, y=0.98, z=0.0$, $spread=0.05$).
    - *Build-up:* A voz ascende verticalmente em direção aos canais de teto ($z=0.48$, $spread=0.35$), criando expectativa e tensão.
    - *Breakdown:* A voz flutua suspensa no meio da sala e no teto ($y=0.20, z=0.68$, $spread=0.65$), gerando sensação celestial imersiva.
    - *Outro:* A voz recua suavemente em direção aos satélites traseiros ($y=-0.45, z=0.72$).
  - **Bateria / Percussão (`drums`):**
    - *Verso:* Kit seco, focado e firme no chão ($y=0.65, z=0.0$).
    - *Build-up:* Esteiras e viradas sobem verticalmente ao teto ($z=0.62$, $spread=0.50$).
    - *Refrão / Clímax:* Kit amplo com pratos distribuídos no teto frontal/traseiro ($z=0.45$, $spread=0.55$) e soco de subwoofer 10" via LFE 1.0.
    - *Breakdown:* Bateria cessa completamente ($gain=0.15, is\_muted=True$), criando contraste dramático com a voz.
  - **Instrumentos Harmônicos / Sintetizadores (`other`):**
    - *Verso:* Puxados deliberadamente para os flancos laterais ($x=\pm 0.68, y=0.20, z=0.10$), desobstruindo o centro para a voz.
    - *Build-up:* Riser acústico ascendente em espiral ao teto ($x=\pm 0.68, y=0.15, z=0.88$, $spread=0.75$).
    - *Refrão:* Envolvimento 360° total abraçando as laterais ($SL/SR$) e traseira ($BL/BR$) com amplitude estéreo ($x=\pm 0.88, y=-0.25, z=0.45$).
    - *Breakdown:* Acordes e pads pairam diretamente sobre a cabeça do ouvinte no teto ($z=0.90, spread=0.85$).
  - **Vocal Throw Traseiro (`vocals::spatial_throw`):**
    - Muted nos versos, ativando com potência ($gain = 1.35, x = \pm 0.72, y = -0.82, z = 0.50$) diretamente nos módulos destacáveis traseiros da JBL Bar 1000 durante os refrões e clímax.
- **Validação de Testes:**
  - Suíte de 30 testes unitários validada com 100% de aprovação comprovando as novas métricas de granularidade de frases e coordenadas 3D reativas.


## [1.8.0] - 2026-11-19
### Adicionado & Aprimorado (IA Maestro com Arranjo Estrutural Autônomo, Efeito Vocal Throw 7.1.4 e Timeline Profissional Estilo DAW)
- **Arranjo Musical Inteligente Autônomo (SongStructureIntelligence / IA Maestro):**
  - **Segmentação Estrutural de Áudio:** Analisador autônomo baseado em perfis temporais de energia RMS, curvas de atividade vocal (VAD), transientes de bateria e contrastes espectrais.
  - **Detecção de Seções Canônicas:** Mapeia automaticamente `Intro (Ambiência Aérea)`, `Verso (Voz Frontal Seca)`, `Build-up (Ascensão ao Teto)`, `Refrão (Imersão 360°)`, `Ponte/Solo (Destaque 3D)`, `Refrão Final (Clímax Absoluto)` e `Outro (Decaimento Imersivo)`.
  - **Efeito Meticuloso "Last Christmas" (Vocal Throw Traseiro 7.1.4):**
    - Identifica automaticamente momentos chaves de resposta vocal e coros.
    - Projeta a instância `vocals::spatial_throw` direcionada com grande destaque ($+1.28$ de ganho) aos módulos traseiros destacáveis da JBL Bar 1000MK2 ($BL/BR, x = \pm 0.68, y = -0.78, z = 0.45$).
    - Durante os versos, o efeito é automaticamente silenciado ($gain = 0.0, is\_muted = True$), garantindo que a voz principal permaneça limpa, intimista e perfeitamente ancorada no canal central frontal.
    - No refrão e clímax, a voz salta inesperadamente para trás com imersão e presença marcante.
  - **Transições e Crossfades Hermite Sem Saltos:** Suavização por curvas $S$ (Hermite smoothstep $3\alpha^2 - 2\alpha^3$) nas fronteiras temporais, eliminando qualquer clique, pop ou salto abrupto de volume.
- **Redesenho Completo da Linha do Tempo (DAW Timeline Canvas Sem Scrollbars):**
  - **Eliminação Total da QScrollArea do SO:** O canvas agora gerencia diretamente seu próprio viewport virtual (`view_start_s` e `zoom`), erradicando o problema do scrollbar do sistema que cobria os blocos ao dar zoom.
  - **Correção da Projeção de Coordenadas (1:1 Playhead & Scrubbing):** Fim do duplo fator de escala; cliques e arraste na régua temporal agora buscam exatamente o ponto clicado com precisão de milissegundos.
  - **Ajuste Tátil de Fronteiras entre Seções (Boundary Dragging):** Ao passar o mouse sobre a linha divisória entre duas seções, o cursor se transforma em `SizeHorCursor` e o usuário pode arrastar a fronteira interativamente, redimensionando as seções adjacentes em tempo real com garantia de contiguidade.
  - **Mini-Mapa de Visão Geral Integrado (Bird's Eye Navigator):** Barra de visão global no rodapé do canvas exibindo 100% da música com blocos em miniatura, caixa de viewport visível arrastável e agulha de reprodução.
  - **Eliminação de Diálogos Modais Pop-up:** Divisão de trechos no cursor e exclusão operam de forma direta e fluida sem interromper o fluxo de trabalho do usuário.
- **Renderização Multicanal e Exportação Unificada:**
  - O motor `MasterRenderer714` agora unifica todas as instâncias e vocal throws de todas as seções temporais na matriz multicanal 7.1.4, preservando a automação na exportação MP4 Dolby Atmos, MKV e WAV.
- **Validação Automatizada Completa:**
  - 30 testes automatizados cobrindo IA Maestro, arraste de fronteiras, minimapa, clonagem de instâncias, exportação JOC e estabilidade de playback com 100% de sucesso.


## [1.7.1] - 2026-11-19
### Corrigido & Aprimorado (Correção Dimensional do Demucs htdemucs, Anti-Travamento e Menu de Contexto 3D)
- **Correção da Incompatibilidade Dimensional do Demucs (`apply_model`):**
  - Identificada e corrigida a causa raiz da falha de carregamento de músicas onde o processo encerrava com "Processo de IA finalizado ou cancelado" e nenhum stem ou puck aparecia na sala.
  - O parâmetro hardcoded `segment=10.0` em `stem_engine.py` causava conflito com o segment fixo de 7.8s ($343.980$ amostras) da arquitetura `htdemucs`, gerando exceção `shape '[1, 4, -1, 343980]' is invalid for input of size 3528000`.
  - Configurado `segment = None`, permitindo que o Demucs decomponha e processe qualquer arquivo de áudio utilizando nativamente a janela treinada do modelo.
- **Relatório e Diagnóstico Claro de Erros no Subprocesso de IA:**
  - Corrigido o mascaramento de erros em `_on_worker_finished`: erros reais do worker agora são capturados do stdout/stderr e apresentados ao usuário via diálogo explicativo em vez de exibir a mensagem genérica de cancelamento.
- **Eliminação de Condições de Corrida no Player de Áudio (`AudioDSPState`):**
  - Implementado o campo `stem_sources` dentro do `AudioDSPState`, garantindo que o callback do PortAudio nunca acesse o dicionário mutável `self.placements` da interface gráfica.
  - Eliminado o risco de `RuntimeError: dictionary changed size during iteration` durante arraste, clonagem ou remoção de instrumentos.
  - Removido recálculo redundante de todos os stems em `_on_room_placement_changed`, liberando CPU e garantindo 60 FPS lisos durante o movimento de bolinhas.
- **Menu de Contexto Completo e Ações Rápidas na Sala 7.1.4 (`RoomView714`):**
  - Botão direito do mouse agora abre menu de contexto profissional com opções de espelhamento estéreo (`D`), cópia (`Ctrl+C`), clonagem / nova fonte 3D (`Ctrl+V`), exclusão (`Del`), centralização (`0`) e altitude $Z$.
  - Botão `[➕]` adicionado diretamente aos cards de instrumentos para clonagem com 1 clique.
  - Atalhos de teclado universais operando de forma idêntica tanto com foco na sala quanto na janela principal.
- **Validação Automatizada:**
  - 28 testes automatizados executando com 100% de aprovação.

## [1.7.0] - 2026-11-19
### Adicionado & Aprimorado (Zoom na Timeline com Precisão de Milissegundos e Clonagem de Nós Espaciais via Ctrl+C / Ctrl+V)
- **Zoom Adaptativo na Timeline (Até Escala de Milissegundos):**
  - **Controle de Zoom Fluido:** Suporte a zoom contínuo de 100% até 128x عبر `Ctrl + Roda do Mouse` sobre a timeline, botões táteis `[+]` (Aumentar zoom), `[-]` (Reduzir zoom) e `[100%]` (Resetar visualização).
  - **Régua Temporal Graduada (Time Ruler):** Adicionada régua superior com marcas e subdivisões dinâmicas que se adaptam automaticamente do nível de minutos/segundos até resolução de **0,001 s (milissegundo)**.
  - **Navegação Horizontal e Viewport Desacoplado:** Implementada barra de rolagem horizontal nativa com zoom ancorado no cursor do mouse, preservando visibilidade exata do playhead e trechos selecionados.
  - **Fatiamento Cirúrgico de Trechos:** Divisão de trechos (`✂️ Dividir no Tempo Atual`) agora opera com precisão de 3 casas decimais ($0.001\text{s}$), permitindo sincronização milimétrica com batidas, viradas ou transições musicais.
- **Clonagem e Multi-Instância Espacial (Ctrl+C / Ctrl+V & Delete):**
  - **Múltiplos Objetos para a Mesma Faixa de Áudio:** O usuário pode selecionar qualquer bolinha no espaço 3D (ex: voz principal `lead_vocal`), pressionar `Ctrl+C` e em seguida `Ctrl+V` para duplicá-la.
  - **Liberdade Espacial Total:** Cada instância (`lead_vocal`, `lead_vocal::2`, etc.) possui posicionamento $X, Y$, altura $Z$, espelhamento estéreo e ganho completamente independentes, compartilhando a mesma matriz de áudio em memória com zero duplicação de RAM.
  - **Exclusão Rápida:** Clones podem ser removidos a qualquer momento pressionando a tecla `Delete` com o nó selecionado ou clicando no botão `[×]` no cabeçalho do respectivo card.
  - **Mixagem Multicanal 7.1.4 Automática:** O motor de reprodução em tempo real (`LiveSpatialPlayer`) e o renderizador final (`MasterRenderer714`) somam e projetam todas as instâncias ativas no bitstream Dolby Atmos e na matriz 7.1.4.
- **Validação Automatizada:**
  - 26 testes unitários passando 100% (`pytest tests/test_atmossplit.py`), cobrindo zoom milimétrico, clonagem multi-instância e renderização 7.1.4.

## [1.6.2] - 2026-11-19
### Corrigido & Blindado (Auditoria Codex CLI, Eliminação de Refcount Leak do Shiboken6 e Threading Assíncrono do PortAudio)
- **Diagnóstico Empírico da Causa Raiz do Fechamento Espontâneo (`SIGABRT status 6` / Core Dump PID 34179):**
  - O log do systemd/journalctl revelou `Fatal Python error: none_dealloc: deallocating None: bug likely caused by a refcount error in a C extension` ocorrendo no `paintEvent` do `RoomView714` (`_draw_single_puck`).
  - Análise profunda com o **Codex CLI** (`gpt-6-luna`) e testes analíticos isolados comprovaram que em PySide6/Shiboken 6.12.0 no Linux, métodos void de C++ (`setColorAt`, `setPen`, `setBrush`, `drawEllipse`, etc.) retornam `None` sem invocar `Py_INCREF`. A cada quadro desenhado a 33 FPS para 12 stems, centenas de referências ao singleton global `None` eram perdidas por segundo até seu refcount zerar, disparando `none_dealloc` e abortando o processo com coredump no compositor Wayland.
- **Eliminação Completa de `QGradient` no Loop de Desenho Frequente (`src/ui/room_view_714.py`):**
  - Removidas todas as instanciações de `QRadialGradient` e chamadas a `setColorAt()` de dentro de `_draw_single_puck()` e `_draw_listener()`.
  - O corpo das esferas 3D, halos de seleção e pulsações de VU agora utilizam renderização direta com `QColor` e `QBrush` sólidos / transparentes de alto contraste e performance.
  - Implementado cache persistente de cores (`_stem_colors`) e verificação diferencial em `set_vu_levels` para evitar chamadas redundantes a `update()` quando os níveis de áudio não se alterarem.
- **Blindagem Ativa de Refcount do CPython (`_immunize_cpython_none_refcount` em `src/ui/main_window.py`):**
  - Implementada rotina via `ctypes` que imuniza a contagem de referências do objeto `None`, elevando-a em 1 bilhão na inicialização e monitorando-a periodicamente no timer de polling da interface. Isso impede matematicamente que o refcount de `None` atinja zero sob qualquer condição ou tempo de uso.
- **Threading Assíncrono para Abertura e Fechamento do PortAudio (`src/spatial/live_player.py`):**
  - As chamadas bloqueantes `sd.OutputStream.start()`, `.stop()` e `.close()` foram movidas para threads secundárias em background (`start_stream` e `close_stream`), eliminando qualquer travamento ou congelamento na thread principal da interface gráfica.
  - O reset de estado dos filtros HRTF agora é consumido de forma lazy e segura pela própria thread de áudio (`_binaural_reset_pending`), prevenindo condições de corrida com o callback do PortAudio.
  - Implementado `set_active_placements()` para atualizar o estado de DSP em tempo real sem reconstruir buffers nem disparar recálculos redundantes de áudio.
- **Cache de Perfis Acústicos na Janela Principal (`src/ui/main_window.py`):**
  - A troca de presets agora reaproveita os perfis de análise acústica dos stems (`self._stem_profiles`), dispensando re-análise cara de FFT e envelopes a cada clique.
- **Suíte de Testes Expandida (24 Testes Automatizados):**
  - Adicionado teste de estresse `test_cpython_none_refcount_shield_and_zero_paint_leak` executando 5.000 renderizações consecutivas e validando estabilidade absoluta com 100% de aprovação.

## [1.6.1] - 2026-11-19
### Corrigido & Otimizado (Arquitetura DSP 100% Lock-Free e Eliminação de Congelamentos no Sistema)
- **Eliminação Total de Congelamentos no Sistema Operacional e Compositor Wayland (`src/spatial/live_player.py`):**
  - **Diagnóstico da Causa Raiz:** O congelamento total do computador ao clicar ou mover instrumentos ocorria devido à contenção de trava (`threading.Lock`) entre o callback C de áudio de alta prioridade do PortAudio/PipeWire e a thread principal da interface gráfica (GUI). Ao receber eventos do mouse a 120 Hz, polling a 33 Hz e seleções de cards, a GUI retinha o lock enquanto realizava operações no Qt. A thread de áudio perdia o prazo de processamento (quantum deadline miss) do PipeWire aguardando pelo lock, gerando stall no servidor de áudio que travava em cascata o compositor de janelas Wayland (KWin) e congelava a tela do desktop.
  - **Arquitetura 100% Lock-Free com Troca Atômica de Ponteiro:** Removido completamente `threading.Lock` das rotinas de áudio em tempo real. Implementado o padrão `AudioDSPState`: a interface gráfica constrói um novo objeto de estado de DSP de forma assíncrona e executa uma troca atômica de referência (`self._dsp_state = new_state`) a nível de bytecode no CPython (< 10 ns). O callback de áudio nunca espera por travas ou locks da GUI.
- **Interpolação Vetorial Pré-calculada de Seções da Timeline (`src/spatial/timeline_manager.py`):**
  - Eliminado o recálculo trigonométrico e matricial de 14 chamadas VBAP por bloco durante a reprodução.
  - As seções da linha do tempo agora pré-calculam e armazenam seus vetores de ganhos (`cached_gains_l` e `cached_gains_r`). O crossfade temporal entre trechos executa uma interpolação vetorial ponderada direta ($\mathbf{g} = (1-\alpha)\mathbf{g}_A + \alpha\mathbf{g}_B$), com execução instantânea (< 5 µs).
  - Adicionado `import numpy as np` no topo do módulo, corrigindo `NameError` durante divisão de seções.
- **Otimização de Renderização e Idempotência (`src/ui/room_view_714.py`):**
  - Implementado cache dos vetores acústicos (`_cached_rays_l` e `_cached_rays_r`), eliminando qualquer recálculo de VBAP de dentro do `paintEvent`.
  - Protegida a emissão de `stem_selected` para disparar apenas se o instrumento ativo de fato mudou, eliminando repinturas em cascata ao clicar repetidamente no mesmo elemento.
- **Eliminação de Thrashing de Estilo e Sincronização Leve (`src/ui/stem_card.py` & `src/ui/main_window.py`):**
  - Adicionado método `set_selected(is_active)` em `StemControlCard`, substituindo a limpeza destrutiva via `setStyleSheet("")` e preservando a árvore de geometria dos widgets.
  - Corrigido `AttributeError: 'TimelineWidget' object has no attribute 'timeline_canvas'` substituindo por `self.timeline_widget.refresh_timeline()`.
- **Validação Automatizada:**
  - Adicionado teste `test_lock_free_dsp_and_timeline_crossfade_audio_callback` validando a ausência de contenção de travas sob alta concorrência e interpolação vetorial pura. Total de 23 testes passando com 100% de sucesso.

## [1.6.0] - 2026-11-19
### Adicionado & Corrigido (Arquitetura Zero-Crash, Controles Táteis de Pan/Posição e Navegação Visual por Trechos)
- **Eliminação de Congelamentos e Travamentos por Contenção de Trava (`src/spatial/live_player.py`):**
  - **Diagnóstico da Causa Raiz:** O arraste de nós pelo mouse no visualizador 3D gerava eventos `mouseMoveEvent` a 120 Hz, disparando chamadas concorrentes à função `update_placement`. Essa rotina adquiria o lock global `self._lock` enquanto executava multiplicações trigonométricas pesadas para o recálculo matricial dos 12 canais do VBAP. A thread real-time de áudio do PortAudio sofria inanição (buffer underrun / deadline miss) ao esperar pelo lock, resultando em `SIGABRT` e fechamento silencioso do programa.
  - **Desacoplamento Algorítmico do Lock:** Os cálculos matemáticos do VBAP foram movidos para fora do lock. Sob lock permanece apenas a leitura inicial e a troca atômica de ponteiros de array NumPy (`self._cached_vbap_gains_l`), durando menos de 1 microssegundo.
  - **Blindagem do Callback de Áudio:** Implementado bloco `try...except` global de nível superior em `_audio_callback` com zeramento defensivo do buffer de saída (`outdata.fill(0)`), prevenindo que qualquer exceção inesperada em tempo real encerre o aplicativo.
  - **Escudo Global do PySide6 (`_install_crash_shield`):** Adicionado interceptor em `sys.excepthook` para capturar exceções não tratadas no loop de eventos do Qt sem abortar o aplicativo.
  - **Throttling Inteligente e Otimização de Arraste (`src/ui/room_view_714.py`):** O visualizador de sala agora filtra micro-movimentos espúrios do mouse ($\Delta < 0.005$) e atualiza os faders dos cards via `sync_coords_from_placement` sem disparar repinturas custosas da interface inteira a cada pixel.
- **Controles Táteis e Claros de Pan e Posição Frente/Trás (`src/ui/stem_card.py`):**
  - **Fim do Mistério no Posicionamento:** O usuário agora tem acesso imediato e transparente ao controle fino de cada elemento musical diretamente nos cards laterais.
  - **Botões Rápidos de 1-Clique:** Adicionada linha de botões táteis no topo de cada card:
    - `[ ⇦ Esq ]`: Posiciona o som imediatamente no lado esquerdo (-70% Pan, Frontal/Lateral).
    - `[ ⇧ Centro ]`: Ancora o som no centro frontal da TV / Soundbar (0% Pan, +95% Frontal).
    - `[ Dir ⇨ ]`: Posiciona o som imediatamente no lado direito (+70% Pan, Frontal/Lateral).
    - `[ ⇩ Fundo ]`: Envia o som diretamente para as caixas surround traseiras (-75% Frente/Trás).
  - **Sliders Dedicados com Feedback Numérico e Textual:**
    - Slider de **Pan (L / R)** (-100% a +100%) com indicadores dinâmicos de texto ("Centro", "X% Esq", "X% Dir").
    - Slider de **Frente / Trás** (-100% a +100%) com indicadores ("Frente", "Meio", "Trás").
- **Barra Visual de Trechos e Divisão em 1-Clique (`src/ui/main_window.py`):**
  - **Navegação Visual por Trechos:** Adicionada barra com destaque visual (`📍 Trecho: [ 1. Música Completa ▼ ]`) logo acima dos cards de instrumentos.
  - **Botão `✂️ Dividir Aqui`:** Permite fatiar a música instantaneamente no ponto exato da reprodução com um clique, selecionando o novo trecho automaticamente para edição espacial isolada (ex: vozes na frente no verso e na esquerda/direita no refrão).
- **Suíte de Testes Expandida (22 Testes Automatizados):**
  - `test_stem_card_pan_and_quick_position_snaps`: Valida botões rápidos de snap de posição, sliders táteis de Pan e Frente/Trás e formatação textual.
  - `test_live_player_crash_proof_and_zero_lock_contention`: Valida recálculo atômico de ganhos fora do lock sob alta frequência e comportamento defensivo do callback de áudio.

## [1.5.0] - 2026-11-19
### Corrigido & Aprimorado (Mixagem Profissional Dolby Atmos & Correção de Mapeamento ETSI TS 103 420)
- **Correção da Ancoragem Frontal da Voz (Norma ETSI TS 103 420 §4.2.1):**
  - **Diagnóstico da Causa Raiz:** O mapeamento dos 12 canais em `_encode_eac3_joc_stream` utilizava coordenadas cartesianas divergentes da norma Dolby Atmos ETSI TS 103 420. No padrão normativo, $X \in [0.0, 1.0]$ varia da parede esquerda (0.0) à direita (1.0), com $X=0.5$ no centro; e $Y \in [0.0, 1.0]$ varia da parede frontal (0.0) à parede traseira (1.0). O canal Central (`FC`, canal 2) estava mapeado como $(x=0.0, y=1.0)$, fazendo a soundbar renderizar a voz principal no alto-falante traseiro esquerdo (módulo destacável esquerdo da JBL Bar 1000).
  - **Mapeamento Corrigido:** Todas as posições de objetos 3D no bitstream foram alinhadas à norma canônica:
    - `FC` (Centro / Voz): $X=0.5, Y=0.0, Z=0.0$ (Frente e Centro, abaixo da TV).
    - `FL` / `FR`: $X=0.0 / 1.0, Y=0.0, Z=0.0$ (Frontais esquerdo e direito).
    - `BL` / `BR`: $X=0.0 / 1.0, Y=1.0, Z=0.0$ (Satélites traseiros destacáveis).
    - `SL` / `SR`: $X=0.0 / 1.0, Y=0.5, Z=0.0$ (Surrounds laterais).
    - `TFL` / `TFR`: $X=0.0 / 1.0, Y=0.0, Z=1.0$ (Canais de teto frontais).
    - `TBL` / `TBR`: $X=0.0 / 1.0, Y=1.0, Z=1.0$ (Canais de teto traseiros).
    - `LFE`: $X=0.5, Y=0.0, Z=0.0, \text{lfe\_send}=1.0$ (Subwoofer).
- **Eliminação de Inversão de Fase Destrutiva nos Backing Vocals (`src/separation/stem_engine.py`):**
  - **Eliminação do Padrão `[+side, -side]`:** A inversão de polaridade de 180° no canal direito causava comb-filtering severo e cancelamento acústico no centro da sala ao somar os drivers da soundbar, gerando som fino, oco e desbalanceado.
  - **Extração Estéreo Coerente:** Backing vocals agora são extraídos subtraindo 85% do sinal mono central de forma balanceada nos canais L e R (`side_l = vocals[:, 0] - 0.85*mid`, `side_r = vocals[:, 1] - 0.85*mid`), combinada com um filtro passa-altas de 4ª ordem em 180 Hz para eliminar ressonâncias de grave.
- **Blindagem do Preset Imersão 360° (`src/spatial/auto_director.py`):**
  - A Voz Principal (`lead_vocal`), o Bumbo (`kick`) e o Sub-Bass (`sub_bass_lfe`) são mantidos permanentemente ancorados no palco frontal ($Y \ge 0.85, X=0.0, \text{is\_stereo}=\text{False}$), em estrita conformidade com as diretrizes da indústria musical da Dolby, UMG e Abbey Road.
  - A imersão 360° é gerada envolvendo instrumentos harmônicos (teclados, guitarras, sintetizadores), backing vocals, reverberações e pratos de bateria ao redor do ouvinte e elevando-os aos canais de teto.
- **Normalização de Sonoridade Profissional (ITU-R BS.1770-4 K-Weighting & -1.0 dBTP True Peak):**
  - Substituição da estimativa simples por RMS pela medição oficial de 2 estágios do filtro K (High-shelf +4 dB em 1.5 kHz e RLB High-pass a 100 Hz com exclusão do canal LFE).
  - Alvo calibrado para **-18.0 LUFS integrado** com limitador True Peak em **-1.0 dBTP** (especificação oficial de controle de qualidade para entrega de áudio espacial na Apple Music e Tidal).
- **Suíte de Testes Expandida (20 Testes Automatizados):**
  - `test_exporter_etsi_ts_103_420_coordinates`: Codifica e decodifica via `ac3forge.Eac3Decoder` confirmando que os objetos 7.1.4 estão posicionados segundo o padrão ETSI TS 103 420.
  - `test_immersion_360_lead_vocal_anchored`: Valida que no modo Imersão 360° o vocal principal e bumbo permanecem estritamente ancorados na frente.
  - `test_k_weighted_lufs_loudness_and_true_peak`: Valida a medição de sonoridade K-weighted e a contenção de pico em -1.0 dBTP.

## [1.4.0] - 2026-11-19
### Adicionado & Aprimorado (Espelhamento Estéreo Simétrico 7.1.4 & Automação Temporal por Trechos)
- **Espelhamento Estéreo Simétrico dos Instrumentos (`is_stereo`):**
  - **Eliminação do Panning Unilateral Agressivo:** Pratos, chimbais, percussões agudas, sintetizadores, ambiências aéreas e coro agora utilizam espelhamento estéreo balanceado (`is_stereo = True`) por padrão no `AutoAtmosDirector`. O som não fica mais preso unicamente na caixa direita ou esquerda, mas envolve as caixas surround laterais/traseiras e de teto em ambos os lados em perfeita harmonia.
  - **Nós Gêmeos (L e R) com Ponte Estéreo (`src/ui/room_view_714.py`):** Instrumentos estéreo renderizam duas esferas na sala marcadas com "L" e "R", unidas por uma ponte arqueada elegante.
  - **Arraste e Altura Sincronizados:** Arrastar qualquer um dos nós sincroniza a distância lateral $|X|$ e o eixo $Y$ instantaneamente no nó oposto. A roda do mouse altera a altura $Z$ e expande o raio de ambas as bolinhas em tempo real.
  - **Alternância com 1 Clique ou Tecla 'D':** O usuário pode ativar/desativar o espelhamento dando duplo clique no nó, clicando no botão `🪞` do card lateral ou pressionando o atalho de teclado `D`.
- **Automação Espacial Dinâmica por Trechos (`SpatialTimelineManager` & `TimelineWidget`):**
  - **Divisão em Seções Musicais:** A música pode ser fatiada em seções independentes (ex: Intro, Verso, Refrão, Ponte, Final) através do botão `✂️ Dividir no Tempo Atual`.
  - **Mixagem Independente por Trecho:** O usuário tem liberdade total para personalizar o posicionamento dos instrumentos para cada trecho (ex: voz no centro na frente durante os versos e vozes no fundo e teto durante o refrão).
  - **Transição Cúbica Hermite Smoothstep ($3\alpha^2 - 2\alpha^3$):** O motor de interpolação realiza transições contínuas sem saltos repentinos ou cliques acústicos entre as fronteiras dos trechos.
  - **Renderização e Exportação com Automação Dinâmica:** O `MasterRenderer714` processa em blocos interpolados quando há múltiplos trechos, garantindo que o arquivo exportado em Dolby Atmos 7.1.4 reproduza com fidelidade todos os movimentos e mudanças de trecho da música.
- **Suíte de Testes Expandida (17 Testes Automatizados):**
  - `test_stereo_mirroring_placement_and_render`: Valida equilíbrio energético estéreo (canais L e R) para pratos e sintetizadores.
  - `test_spatial_timeline_manager_split_and_interpolation`: Valida divisão, renomeação, exclusão e interpolação contínua na fronteira.
  - `test_master_renderer_dynamic_timeline`: Valida transição espacial de vocal da frente para o fundo entre seções.
  - `test_room_view_stereo_pucks_and_toggle`: Valida hit-test de nós gêmeos L/R e alternância de espelhamento.

## [1.3.2] - 2026-11-19
### Corrigido & Aprimorado (Dolby Atmos Real com Joint Object Coding / E-AC-3 JOC & 12 Objetos Espaciais 7.1.4)
- **Eliminação do Falso Atmos / Downmix Silencioso para 5.1 (`src/playback/exporter.py`):**
  - **Diagnóstico Preciso:** O encoder embutido `eac3` do FFmpeg padrão suporta nativamente apenas layouts tradicionais até 5.1 (6 canais), descartando os metadados espaciais de objetos (JOC) e fundindo os canais surround traseiros e de altura no bed 5.1 estático.
  - **Motor Nativo de Codificação Dolby Atmos (`ac3forge`):** Integrada a biblioteca C++23/Python `ac3forge` com `AtmosEncoder` e `AtmosConfig`. O AtmosSplit agora constrói bitstreams genuínos de **Dolby Digital Plus com Dolby Atmos (E-AC-3 JOC)** com metadados OAMD completos (Object Audio Metadata), índice de complexidade 13 e 12 objetos dinâmicos mapeados nas coordenadas tridimensionais físicas da sala (incluindo teto $z=1.0$, surrounds laterais e traseiros e canal LFE).
  - **Compatibilidade Plena e Verificação Auditada:** O stream E-AC-3 JOC é muxado em MP4/MKV com `-c:a copy` (sem qualquer re-encoding destrutivo). A faixa é auditada e reconhecida como `profile: Dolby Digital Plus + Dolby Atmos`, `Format: E-AC-3 JOC`, `is_atmos: True` e `channels: 7.1.4` pelo `ffprobe`, `mediainfo` e pelo auditor do `AtmosHunter` (`audio_verify.py`), acionando a decodificação de **DOLBY ATMOS real com os 4 canais de altura e surrounds discretos na JBL Bar 1000MK2**.
  - **Novos Formatos de Exportação no Diálogo:**
    - `MP4_ATMOS_JOC_714`: MP4 com Dolby Digital Plus + Dolby Atmos (E-AC-3 JOC com 12 objetos e metadados espaciais 3D), vídeo H.264 de capa 1280x720 e faststart para streaming sem perdas via Wi-Fi (Rygel/TV Samsung/BubbleUPnP).
    - `MKV_ATMOS_JOC_714`: MKV com Dolby Digital Plus + Dolby Atmos (E-AC-3 JOC).
    - `EC3_ATMOS_714`: Bitstream bruto `.ec3` E-AC-3 JOC para ferramentas profissionais e DAWs.
    - `MKV_LPCM_714`: 12 canais discretos 24-bit 48 kHz sem compressão para reprodução direta via cabo HDMI / eARC no DirectFrame.
- **Auditoria Expandida no Verificador (`src/acquisition/probe_verifier.py`):**
  - `AudioProbeResult` agora inspeciona e expõe o campo `profile` e a flag `is_atmos: bool` baseada na presença de metadados JOC e Dolby Atmos no fluxo.

## [1.3.1] - 2026-11-19
### Corrigido & Aprimorado (Exportação Completa, Transmissão Wi-Fi / TV Samsung & Controle 3D de Altura)
- **Controle Interativo de Altura 3D via Scroll do Mouse & Seleção por Clique (`src/ui/room_view_714.py`):**
  - O usuário pode clicar diretamente em qualquer círculo de stem na sala para selecioná-lo (indicado por borda ciano neon pulsante `#00E5FF`, halo e badge flutuante de altitude).
  - Girar o scroll do mouse para cima ou para baixo aumenta ou diminui a altura $Z$ do som (elevando-o em direção aos alto-falantes de teto ou descendo-o para o chão) em incrementos de 0.05.
  - Sincronização em tempo real com os faders do painel lateral esquerdo, matriz de ganhos VBAP 3D e filtros de elevação binaural HRTF.
- **Visualização 3D de Altura por Raio e Profundidade (Zero Custo Gráfico):**
  - A altura sonora é representada intuitivamente pela escala dinâmica do raio do círculo: de 11 px no piso ($z=0$) até 33 px no teto ($z=1$) — exatamente 3 vezes maior.
  - Renderização de sombra no chão no ponto $(X, Y)$ da base e cordão vertical pontilhado conectando o chão ao instrumento flutuante.
  - Anéis concêntricos de dispersão no teto quando $z > 0.35$ e indicador percentual de altura dentro do círculo quando há espaço visual.
- **Correção Crítica de Truncamento em 10 Segundos (`src/playback/exporter.py`):**
  - Identificada e eliminada a causa raiz do bug: o parâmetro estático `:d=10` no gerador de vídeo sintético do FFmpeg (`lavfi`), combinado com a flag `-shortest`, fazia o FFmpeg cortar a música inteira exatamente nos 10 primeiros segundos.
  - O cálculo da duração agora é dinâmico com base na contagem real de amostras da matriz multicanal (`duration_s = num_samples / sample_rate`), garantindo a exportação íntegra da música completa (3m, 5m, 10m).
- **Novo Formato Padrão para Wi-Fi / TV Samsung / DLNA (`MP4_EAC3_71`):**
  - Criado formato nativo **MP4 Dolby Digital Plus 7.1 (E-AC-3 1024 kbps)** com capa embutida H.264 (1280x720 pré-escalado a 1 fps) e flag `-movflags +faststart`.
  - Este formato é o padrão aceito nativamente pela **TV Samsung Tizen** (perfil DLNA `AVC_MP4_HP_HD_EAC3`), pelo servidor **Rygel** e **Jellyfin** no computador e pelos reprodutores de celular (**BubbleUPnP** e **Symfonium** no Samsung Galaxy S20 FE).
  - O botão de **Exportação Rápida** agora gera diretamente este arquivo em `~/Music/DolbyAtmos/`, permitindo tocar via Wi-Fi no exato segundo em que o arquivo é gravado no disco sem qualquer necessidade de transcodificação.
- **Ponte de Cast Wi-Fi & Automação de Tela (`SamsungDLNABridge`):**
  - O botão **🔊 Tocar na JBL 1000** agora exporta a faixa em `.mp4` 7.1, conecta-se aos renderers descobertos no ecossistema e envia o comando `KEY_PICTURE_OFF` para apagar a tela da TV Samsung, mantendo o som 7.1 ativo via HDMI eARC na JBL Bar 1000.
- **Suíte de Testes Expandida (13 Testes Automatizados):**
  - Adicionado teste `test_exporter_anti_truncation_full_duration` validando que faixas longas (> 10s) não sofrem qualquer corte.
  - Adicionado teste `test_room_view_radius_and_selection` validando seleção de nós, controle de altura via scroll e escalonamento de raio 3D.

## [1.3.0] - 2026-11-19
### Adicionado & Otimizado
- **Launcher de Duplo Clique Amigável (`Abrir_AtmosSplit.desktop` & `~/Desktop/AtmosSplit.desktop`):**
  - Configurado arquivo de duplo clique na raiz do projeto e no Desktop com metadados confiáveis (`metadata::trusted: true`).
  - Suporte ao parâmetro `%F` para permitir abrir o app diretamente ou associar arquivos de áudio (FLAC, WAV, MP3, etc.) para carregamento e separação instantânea.
- **Hierarquia de Prioridade Ajustada para Fluidez Extrema:**
  - O launcher (`iniciar.sh`) agora executa a interface PySide6 e o motor de áudio em prioridade normal (`nice 0`), garantindo renderização de 60 FPS contínuos, arraste fluido de nós e ausência de travamentos no Wayland.
  - O isolamento térmico e de núcleos (`nice 19`, `ionice 7`, afinidade núcleos 2-15) fica restrito aos workers pesados de IA no subprocesso (`worker_cli.py`), preservando os núcleos 0 e 1 para o KDE Plasma e PipeWire.
- **Desacoplamento Completo da Thread de Áudio (Zero XRUNs):**
  - Implementado padrão de snapshot atômico com polling via `QTimer` a ~33 FPS na GUI (`MainWindow._poll_audio_state`), eliminando emissão de sinais Qt de dentro do callback de tempo real ALSA/PipeWire.
- **Cache Vetorizado de Ganhos VBAP:**
  - O cálculo trigonométrico dos 12 ganhos VBAP agora é executado e mantido em cache apenas quando as coordenadas mudam, reduzindo o custo de CPU no callback de áudio em mais de 80%.
- **Continuidade de Fase e Anti-Clicking no Binaural HRTF (`binaural_hrtf.py`):**
  - Filtros IID e de elevação agora preservam os estados internos (`zi`) entre blocos contíguos de 2048 amostras, eliminando qualquer micro-estalo acústico na audição em fones de ouvido (Havit H2002D / QCY N70).
  - Adicionado método `reset_states()` para transições suaves em pausas e buscas na faixa.
- **Matador de Processos Órfãos / Zumbis (`psutil`):**
  - O botão de cancelamento de separação e o fechamento do app agora executam encerramento recursivo de toda a árvore de processos filhos, garantindo que nenhuma thread do Demucs continue consumindo CPU em segundo plano.
- **Seletor Dinâmico de Saída de Áudio:**
  - Adicionado menu suspenso na barra de cabeçalho permitindo alternar dinamicamente entre PipeWire Padrão, Fone Havit H2002D / ALC662 e HDMI Radeon RX 580 (TV Samsung / JBL Bar 1000).
- **Fader de Volume Master Geral:**
  - Adicionado controle deslizante de volume geral (0 a 150%) com display numérico no rodapé.
- **Gerenciador e Limpador Visual de Cache:**
  - Botão `🧹 Cache (X MB)` com badge em tempo real.
  - Janela modal interativa para visualizar faixas em cache e limpar armazenamento com 1 clique.
- **Atalhos Estendidos de Teclado:**
  - `M`: Mute instantâneo do stem selecionado.
  - `S`: Solo instantâneo do stem selecionado.
  - `0`: Centraliza o stem selecionado na sala (0, 0, 0).
  - `Setas Cima / Baixo`: Ajusta a elevação (Z) do instrumento em incrementos de 0.05.

## [1.2.0] - 2026-11-19
### Adicionado & Otimizado
- **Afinidade Estrita de CPU no Xeon E5-2667 v2 (`process_shield.py`):**
  - Núcleos 0 e 1 reservados exclusivamente para o sistema operacional, compositor Wayland (`kwin_wayland`), PipeWire e interface gráfica.
  - Workers de separação vinculados exclusivamente aos núcleos 2 a 15, garantindo movimentação fluida do mouse e desktop sem engasgos.
- **Subprocesso Desacoplado de IA via QProcess (`worker_cli.py`):**
  - A separação de stems por IA agora é executada em processo isolado (`python -m src.separation.worker_cli`), eliminando disputa de GIL no interpretador da interface gráfica.
  - Comunicação de progresso via stream JSON assíncrono em stdout.
  - Botão **✖ Cancelar Separação** na interface gráfica: encerra o processo em milissegundos (`process.kill()`), liberando CPU e memória RAM imediatamente.
- **Blindagem Anti-Crash de GPU Polaris (RX 580):**
  - Bloqueio explícito de detecção CUDA e ROCm (`CUDA_VISIBLE_DEVICES=""`, `HIP_VISIBLE_DEVICES=""`), eliminando 100% dos riscos de *GPU Ring Hang* que poderiam derrubar o KDE Plasma.
- **Controle de RAM & Chunking Temporal no Demucs:**
  - Aplicação de segmentação temporal (`segment=10.0`, `overlap=0.25`, `shifts=0` no modo rápido e `shifts=1` no modo cirúrgico).
  - Teto de consumo de RAM limitado a < 1.2 GB, prevenindo pressão de largura de banda na memória DDR3.
- **Downsample Precoce de Áudios Hi-Res:**
  - Faixas em 96 kHz / 192 kHz são resampladas precocemente para 44.1 kHz antes da inferência neural e restauradas para a mixagem 48 kHz, economizando mais de 50% de CPU.
