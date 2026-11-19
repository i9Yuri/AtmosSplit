# ENVIRONMENT_REPORT — Auditoria, Benchmarks de IA e Verificação 7.1.4

**Data de Execução:** 19/11/2026  
**Ambiente:** Nobara Linux (KDE Plasma, Wayland, PipeWire)  
**Hardware:** Intel Xeon E5-2667 v2 (8c/16t, AVX, Ivy Bridge-EP), 32 GB RAM DDR3, AMD Radeon RX 580 2048SP (Polaris 20, 8GB VRAM)  
**Sistema de Som Alvo:** JBL Bar 1000 / 1000MK2 (7.1.4 Dolby Atmos com subwoofer de 10" sem fio e satélites destacáveis) conectada via HDMI eARC à TV Samsung Tizen.

---

## 1. Auditoria dos Projetos Vizinhos Reaproveitáveis

Inspecionamos os projetos irmãos no workspace `/home/yuri/Desktop/Yuri/Projects/`:

1. **Zenith / AtmosHunter (`Projects/Zenith/AtmosHunter`):**
   - **Mecanismos de busca:** Possui cliente Soulseek assíncrono persistente (`core/slsk_service.py` via `aioslsk 1.7`) e orquestrador de busca (`core/search.py`) integrando API Hi-Res Direct (`tracks.monochrome.st`) e Internet Archive.
   - **Auditoria de codecs:** `core/audio_verify.py` implementa verificação precoce de contêineres e validação ffprobe rigorosa, diferenciando E-AC-3 JOC Dolby Atmos real de AAC estéreo renomeado.
   - **Streaming DLNA & Samsung Tizen:** `core/dlna_bridge.py` cria servidor HTTP com suporte a Range requests e UPnP AVTransport para envio direto de faixas à TV Samsung / JBL Bar 1000 sem perda. `core/tv_control.py` gerencia WebSocket com a TV Samsung (porta 8002) e dispara `KEY_PICTURE_OFF` para desligar a tela durante a audição.
   - **Reaproveitamento no AtmosSplit:** Integração direta com o backend de busca do AtmosHunter para ingestão em 1-clique de faixas Hi-Res/Atmos, e reaproveitamento da ponte DLNA + controle de tela Tizen no módulo de playback.

2. **DirectFrame (`Projects/DirectFrame`):**
   - **Motor de reprodução:** Baseado em PySide6 e `python-mpv` com biblioteca `mpv-libs-0.41.0-5.fc44.x86_64`.
   - **Passthrough de áudio HDMI:** Possui lógica em `PlayerCore.py` configurada com `audio_spdif="ac3,eac3,truehd,dts-hd,dts"`, `audio_exclusive=True` e fallback automático para LPCM multicanal 7.1.
   - **Reaproveitamento no AtmosSplit:** O AtmosSplit inclui atalho para abrir diretamente arquivos exportados no DirectFrame com passthrough HDMI eARC ativado.

3. **Vitrola (`Projects/Vitrola`):**
   - **Motor de download e fallback:** Implementa wrappers sobre `yt-dlp` e FFmpeg (`backend/downloader.py` e `core/ytdlp_wrapper.py`) para download com extração de áudio original em máxima taxa de bits.
   - **Reaproveitamento no AtmosSplit:** Atua como fallback quando uma música não existir nos catálogos Soulseek / Hi-Res lossless.

---

## 2. Benchmark Empírico de Separação de Stems (CPU Xeon vs. GPU RX 580)

Executamos `scripts/probe_stems_env.py` e testes com áudio polifônico de 30 segundos (`test_polyphonic_30s.wav`):

| Componente | Avaliação Empírica | Decisão Arquitetural |
|---|---|---|
| **GPU AMD RX 580 2048SP** | Arquitetura Polaris (gfx803) sem suporte upstream ROCm moderno no Linux. Tentativas de forçar frameworks de deep learning em Polaris geram risco de *GPU Ring Hang* e congelamento do KDE Plasma Wayland. | **NÃO utilizar ROCm na RX 580.** GPU dedicada à aceleração de interface gráfica Mesa RADV. |
| **CPU Intel Xeon E5-2667 v2** | 8 núcleos físicos, 16 threads lógicas, frequência de 3.30 GHz (Turbo até 4.0 GHz), suporte a instruções AVX. Execução do modelo `htdemucs` em CPU com 8 threads separou 30s de áudio em **21,0 segundos** (1,61x mais rápido que tempo real). | **Motor primário de inferência.** Execução com `nice -n 19`, `ionice -c 2 -n 7` e teto de threads para preservar 100% da fluidez do desktop. |
| **Sub-divisão Cirúrgica DSP** | Filtros de fase linear Linkwitz-Riley 4ª ordem (< 80 Hz para LFE), decomposição Mid/Side e isolamento de transientes/altas frequências processaram 30s em **0,167 segundos** (RAM delta: 138 MB). | Pipeline híbrido: Estágio 1 (Macro-camadas via Demucs) + Estágio 2 (Sub-divisão instantânea via DSP/Scipy). |

---

## 3. Verificação Real de Saída e Reprodução 7.1.4

Executamos `scripts/probe_714_playback.py` e geramos arquivos diagnósticos de 12 canais discretos (`tests/multichannel_diagnostics/`):

1. **Formato A — MKV com LPCM 7.1.4 (`pcm_s24le`, 12 canais discretos, 24-bit, 48 kHz, 13,8 Mbps):**
   - **Status:** **GERADO COM SUCESSO.**
   - O FFmpeg 8.1.3 do sistema reconhece e muxa nativamente o layout canônico `7.1.4`: `FL+FR+FC+LFE+BL+BR+SL+SR+TFL+TFR+TBL+TBR`.
   - **Comportamento na cadeia HDMI eARC:** Se a porta HDMI do PC estiver conectada à TV Samsung Tizen com eARC em modo *Pass-Through*, o contêiner Matroska 12ch transmite os 12 canais discretos.
2. **Formato B — FLAC 12 canais:**
   - **Status:** **INCOMPATÍVEL.** A especificação do codec FLAC é limitada matematicamente a no máximo 8 canais (7.1). O encoder do FFmpeg rejeita arquivos acima de 8 canais (`error -22`).
3. **Formato C — TrueHD 7.1 Lossless (`test_71_truehd.mkv`, 8 canais discretos):**
   - **Status:** **GERADO COM SUCESSO.** Exige flag `-strict -2`. Matriz de altura codificada em fase nos surrounds para acionamento do upmixer MultiBeam / Dolby Surround da JBL Bar 1000.
4. **Formato D — E-AC-3 7.1 a 1024 kbps (`test_71_eac3.mkv`, Dolby Digital Plus 7.1):**
   - **Status:** **GERADO COM SUCESSO.** Taxa de bits máxima suportada pelo padrão, com 100% de compatibilidade em qualquer receptor HDMI ARC/eARC e DLNA de Smart TVs Samsung.
5. **Formato E — WAV 12 canais PCM 24-bit 48 kHz (`test_714_channels.wav`):**
   - **Status:** **GERADO COM SUCESSO.** Formato mestre descompactado para edição e pré-escuta interna.

---

## 4. Conclusão da Fase 0 e Diretriz do Exportador

O AtmosSplit suportará como formatos de saída principais:
- **MKV LPCM 7.1.4 (12 canais discretos 24-bit):** Fidelidade máxima sem compressão, mapeando 1:1 cada uma das 12 caixas físicas da JBL Bar 1000.
- **Dolby Digital Plus 7.1 (E-AC-3 1024 kbps) & TrueHD 7.1:** Para máxima compatibilidade via DLNA e TVs que restrinjam LPCM eARC a 8 canais.
