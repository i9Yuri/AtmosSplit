# AtmosSplit

Estúdio Linux para transformar uma faixa estéreo em mixagem espacial 7.1.4. O HTDemucs separa a faixa em CPU. A direção espacial organiza o arranjo em seções e distribui eventos pontuais pela sala. A edição e a exportação funcionam localmente.

## Abrir o estúdio

```bash
./iniciar.sh
```

1. Abra ou arraste uma faixa. O modo rápido prepara quatro stems e o cirúrgico prepara nove. A reabertura recupera o arranjo e os stems do cache.
2. Escolha uma seção na timeline. A família, o andamento, o compasso e a confiança explicam a proposta de direção. Ative **Compasso** para alinhar as divisões à grade.
3. Selecione uma fonte e ajuste posição, altura, largura, ganho e envio ao subwoofer no inspetor. Compare a microcoreografia ligada e desligada. O slider de intensidade dosa a direção. Os envios vocais aparecem em pontos específicos e a voz principal mantém a referência frontal.
4. Escolha o dispositivo de pré-escuta binaural. Use os perfis Estúdio e JBL Bar 1000 MK2 para comparar a presença da voz mantendo o volume de escuta.
5. Exporte MP4 E-AC-3 JOC para a Samsung Q60C por DLNA, MKV LPCM para DirectFrame ou WAV de 12 canais. O estúdio informa loudness, pico e relação voz/instrumental. A entrega JOC informa também o pico após decodificação.

## Atalhos

| Comando | Ação |
|---|---|
| Ctrl+O, Espaço, ← / → | Abrir, tocar/pausar, mover cinco segundos |
| ↑ / ↓, roda sobre uma fonte | Ajustar altura |
| M, S, D, 0 | Mudo, solo, espelhar, centralizar |
| 1–5 | Aplicar um estilo de direção |
| Ctrl+C / Ctrl+V, Delete | Copiar e colar uma fonte, remover a cópia |
| Ctrl+roda na timeline | Zoom em torno do ponteiro |

## Verificação

```bash
.venv/bin/pytest -v
.venv/bin/python scripts/probe_714_playback.py
```

A calibração produz MP4, MKV e WAV com identificação individual dos doze canais. No MP4 padrão, ouça o centro em 4 s, o sub em 6 s e as quatro posições de teto a partir de 16 s. O teste acústico depende da configuração da TV, do eARC, da soundbar e da sala.

A instalação local usa Python 3.11, pesos HTDemucs já presentes, PySide6, PortAudio, um compilador C11 e FFmpeg/ffprobe. Os detalhes de hardware, cache, processo, MIR, DSP e codec estão no [documento de arquitetura](PROJECT_CONTEXT.md).
