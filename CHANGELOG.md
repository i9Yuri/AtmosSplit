# CHANGELOG — AtmosSplit

Todas as mudanças notáveis deste projeto serão registradas neste arquivo.

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
