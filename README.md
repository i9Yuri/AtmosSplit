# AtmosSplit — Montador Espacial Dolby Atmos 7.1.4

Aplicação desktop nativa para Linux (Python 3.11 + PySide6), 100% gratuita, offline-first e de custo zero (R$ 0,00), que decompõe faixas musicais em múltiplas camadas individuais (voz principal, coro, bumbo, caixa, pratos/chocalhos, sub-grave, baixo harmônico, guitarras, teclados e ambiência aérea de teto) e oferece uma interface visual intuitiva para montagem e audição espacial em um sistema **Dolby Atmos 7.1.4 canais**.

---

## 🎧 Hardware e Ecossistema Alvo

- **Workstation Principal:** Nobara Linux (KDE Plasma Wayland), CPU Intel Xeon E5-2667 v2 (8c/16t, AVX), GPU AMD Radeon RX 580 2048SP (8 GB VRAM, arquitetura Polaris 20) e 32 GB RAM DDR3.
- **Sistema de Som 7.1.4:** Soundbar **JBL Bar 1000 / 1000MK2** (7.1.4 canais com subwoofer sem fio de 10" e satélites surround destacáveis) conectada via HDMI eARC à TV Samsung Tizen.
- **Pré-escuta no PC:** Headsets **Havit H2002D** / **QCY N70** com simulação binaural HRTF integrada em tempo real.
- **Transmissão Sem Fio (Wi-Fi):** Servidor UPnP/DLNA **Rygel** (`Yuri PC`), aplicativo **BubbleUPnP / Symfonium** no smartphone Galaxy S20 FE e player da **TV Samsung** com automação de tela apagada (`KEY_PICTURE_OFF`).

---

## ✨ Recursos Principais

### 1. Ingestão & Busca Flexível
- **Drag & Drop:** Arraste qualquer arquivo local nos formatos FLAC, WAV, ALAC, MP3, M4A, Opus ou OGG.
- **Abertura por Duplo Clique:** Associação direta de arquivos via linha de comando ou gerenciador de arquivos (Dolphin).
- **Busca de Alta Fidelidade Integrada:** Digite "Artista - Nome da Música" para buscar versões lossless em catálogo Hi-Res (Soulseek / Monochrome) com fallback automático via `yt-dlp`.

### 2. Destrinchador Multi-Estágio com IA & DSP Cirúrgico
- **Modo Rápido (~4 camadas):** Vocais, Bateria, Baixo e Outros.
- **Modo Cirúrgico (8–12 camadas):**
  - Bumbo (Kick) centrado e enviado ao LFE.
  - Caixa (Snare) com impacto frontal.
  - Pratos / Chocalhos / Chimbal (Cymbals & Shakers) com elevação de teto.
  - Sub-Grave puro (< 80 Hz via filtro Linkwitz-Riley de 4ª ordem) dedicado ao Subwoofer.
  - Baixo Harmônico (80–400 Hz).
  - Voz Principal (Lead Vocal) ancorada no canal de diálogo frontal central.
  - Coro / Backing Vocals com dispersão estéreo surround.
  - Ambiência Aérea (> 6000 Hz) mapeada para os 4 drivers de teto.
- **Process Shield & Blindagem de Hardware:** Execução em prioridade `nice -n 19`, `ionice idle` e afinidade nos núcleos de CPU 2 a 15 (deixando núcleos 0 e 1 livres para o KWin Wayland e PipeWire), com isolamento total em subprocesso (`QProcess`).
- **Cache Instantâneo por Hash SHA-256:** Carrega músicas já analisadas em menos de 0.5s sem reprocessamento.

### 3. Planta Interativa 2D / 3D da Sala 7.1.4
- **Perspectiva Pseudo-3D com Escala Visual de Raio:** A altura sonora $Z$ é comunicada visualmente pelo tamanho da esfera (de 11 px no chão até 33 px no teto — 3x maior), com sombra no piso e haste vertical.
- **Controle Fino de Altura por Scroll:** Clique na bolinha e role a roda do mouse para subir ou descer o som no espaço tridimensional.
- **Espelhamento Estéreo Simétrico (L / R):** Elimina o desbalanceamento unilateral agressivo nos pratos e sintetizadores. Duas esferas gêmeas unidas por uma ponte estéreo se movem simetricamente ($X \to -X$).
- **Medidores VU Reativos:** Cada nó pulsa visualmente em tempo real acompanhando a energia musical do seu instrumento.
- **Instâncias independentes:** `Ctrl+C` copia o posicionamento selecionado; `Ctrl+V` cria outra instância do mesmo áudio com controles espaciais próprios. `Delete` remove cópias.

### 4. Automação Espacial Dinâmica por Trechos (Timeline)
- **Divisão com 1 Clique (`✂️ Dividir no Tempo Atual`):** Fatie a música em seções independentes (Intro, Verso, Refrão, Solo, Ponte, Final).
- **Mixagem Exclusiva por Trecho:** Defina a voz na frente no verso e no fundo com elevação de teto durante o refrão.
- **Transição Hermite Smoothstep ($3\alpha^2 - 2\alpha^3$):** Movimentação contínua e cinematográfica de instrumentos entre seções sem saltos ou cliques acústicos.
- **Zoom temporal:** Use `Ctrl+roda`, os botões `+` / `−` / `100%` e a barra horizontal. A régua detalha até milissegundos; os splits preservam resolução de 0,001 s.

### 5. Dolby Atmos Real com Joint Object Coding (E-AC-3 JOC via `ac3forge`)
- **Fim do Falso Atmos 5.1:** Utiliza o encoder nativo `ac3forge` para gerar bitstream autêntico **Dolby Digital Plus with Dolby Atmos (E-AC-3 JOC)** com metadados espaciais OAMD, complexidade 13 e 12 objetos 3D discretos.
- **Acionamento Real dos 4 Canais de Teto:** Reconhecido como `Dolby Digital Plus + Dolby Atmos` pelo `ffprobe`, `mediainfo` e auditor do `AtmosHunter`, ativando os drivers overhead na JBL Bar 1000MK2.
- **Exportação Wi-Fi em 1 Clique:** Salva diretamente em `~/Music/DolbyAtmos/` com capa embutida e `-movflags +faststart`.

---

## ⌨️ Tabela de Atalhos de Teclado & Controles

| Controle / Tecla | Ação |
| :--- | :--- |
| `Espaço` | Tocar / Pausar pré-escuta binaural HRTF |
| `Scroll do Mouse` | Subir / Descer a altura Z do instrumento (ajusta o raio visual 3D) |
| `Duplo Clique` ou `D` | Alternar **Espelhamento Estéreo Simétrico (L / R)** no instrumento ativo |
| `0` (Zero) | Centralizar o instrumento selecionado no meio do palco acústico |
| `M` / `S` | Alternar Mudo (Mute) ou Solo no instrumento selecionado |
| `Setas Cima / Baixo` | Ajustar altura Z em passos de 5% |
| `Setas Esquerda / Direita` | Retroceder / Avançar 5 segundos na reprodução |
| `1` a `5` | Alternar Presets: 1 (Equilibrado), 2 (360°), 3 (Show), 4 (Voz), 5 (Clube) |
| `✂️ Dividir` | Criar nova seção musical na barra de tempo para automação espacial |

---

## 🚀 Como Executar

```bash
# 1. Iniciar a aplicação diretamente
./iniciar.sh

# 2. Executar a suíte completa de testes automatizados
.venv/bin/pytest tests/test_atmossplit.py -v

# 3. Instalar o lançador no menu de aplicativos do KDE Plasma / desktop
./scripts/install_desktop_entry.sh
```

---

## 📦 Formatos de Exportação Suportados

1. **`MP4 Dolby Digital Plus + Dolby Atmos 7.1.4 (E-AC-3 JOC)` [Recomendado Wi-Fi / TV]:**
   - Áudio com 12 objetos 3D espaciais, taxa de 768 kbps, vídeo de capa leve (1 fps 1280x720) e streaming instantâneo.
2. **`MKV LPCM 7.1.4 12ch`:**
   - 12 canais PCM 24-bit 48 kHz discretos sem perdas para cabo HDMI eARC passthrough via DirectFrame.
3. **`MKV Dolby Atmos 7.1.4`:**
   - Contêiner MKV com fluxo E-AC-3 JOC.
4. **`WAV 7.1.4 12ch`:**
   - Arquivo master de áudio descompactado multi-track para estúdio.
5. **`EC3 Dolby Atmos 7.1.4`:**
   - Bitstream bruto `.ec3` E-AC-3 JOC.

---

## 🛡️ Licença & Arquitetura
Projeto 100% livre, construído sob as diretrizes do **Spec-First Architect** e padrões de engenharia de alta fidelidade sonora.
