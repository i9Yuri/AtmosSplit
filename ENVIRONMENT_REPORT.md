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
| **CPU Intel Xeon E5-2667 v2** | 8 núcleos físicos, 16 threads lógicas, frequência de 3.30 GHz (Turbo até 4.0 GHz), suporte a instruções AVX. Execução do modelo `htdemucs` em CPU com 8 threads separou 30s de áudio em **21,0 segundos** (1,43× a velocidade de reprodução). | **Motor primário de inferência.** Execução com `nice -n 19`, `ionice -c 3` e teto de threads para reservar capacidade ao desktop. |
| **Sub-divisão Cirúrgica DSP** | No benchmark original, filtros Butterworth aplicados nos dois sentidos, decomposição Mid/Side e extração de agudos processaram 30 s em **0,167 segundos** (RAM delta: 138 MB). | Pipeline híbrido: Estágio 1 (Macro-camadas via Demucs) + Estágio 2 (Sub-divisão instantânea via DSP/Scipy). |

---

## 3. Verificação de saída no estúdio 2.0

Os arquivos do primeiro benchmark e o respectivo JSON são históricos. O ffprobe identificou seis canais nos antigos ensaios TrueHD e E-AC-3, inclusive nos arquivos cujo nome continha `71`. Na versão 2.0 a entrega para a TV é E-AC-3 JOC a 768 kbit/s. A decodificação verifica o bed 5.1 e onze objetos espaciais com LFE discreto. Nos testes de calibração foram confirmados MP4 com perfil Dolby Digital Plus + Dolby Atmos, WAVEX PCM 24 bits com máscara 7.1.4 e MKV com doze canais PCM.

| Medição local | Resultado |
|---|---|
| Janela nativa | Wayland, 1920×1000 em tela 1920×1080 a 79,982 Hz, processo em nice 0 |
| Transporte | Um segundo de silêncio reproduzido integralmente pelo dispositivo PortAudio padrão, zero underruns |
| Worker de separação | Modelo local, nice 19, classe de I/O idle e afinidade lógica 2–15 observados durante inferência |
| Faixa de 156,6535 s | 9 stems, 14 seções, 130,4 BPM, métrica de quatro tempos e 50 eventos candidatos selecionados |
| Master PCM | Em ambos os perfis, −18,00 LUFS. Relação voz/instrumental em 1–4,5 kHz de +2,58 dB no Estúdio e +4,07 dB no JBL |
| MP4 completo | JOC a 48 kHz com 156,672 s. Pico decodificado de −3,16 dBTP e ajuste do codec de 0,00 dB |

O player DirectFrame/mpv depende dos layouts oferecidos pelo sink HDMI. Na máquina de desenvolvimento, o mpv aceitou a lista explícita das doze posições e abriu o master em doze canais com saída de teste. A identificação física na JBL e a resposta da sala requerem escuta no ponto de audição.

## 4. Reproduzir a calibração

```bash
.venv/bin/python scripts/probe_714_playback.py
```

O programa usa o exportador de produção e grava em `tests/multichannel_diagnostics/`. O MP4 padrão contém pulsos de dois segundos por canal, incluindo o centro a partir de 4 s e o LFE a partir de 6 s. A duração acompanha a opção `--step-seconds`. As durações, a afinação e o nível dos tons estão no script.
