"""
AtmosSplit — Process Shield (Blindagem Térmica e de Hardware)
Garante isolamento térmico, controle estrito de afinidade e prioridade de CPU:
- nice -n 19 (prioridade mais baixa para não travar o desktop KDE Plasma Wayland)
- ionice -c 2 -n 7 (evita disputa por I/O no disco)
- Afinidade de CPU estrita: reserva núcleos 0 e 1 para SO, KWin Wayland e PipeWire,
  alocando os núcleos restantes (2 a 15) para os cálculos de IA.
- Blindagem anti-crash GPU: bloqueia chamadas ROCm/CUDA instáveis na RX 580 Polaris.
"""

from __future__ import annotations

import os
import psutil
import logging
from typing import List, Optional

log = logging.getLogger(__name__)


def apply_cpu_affinity(reserve_cores: int = 2) -> List[int]:
    """
    Reserva os primeiros `reserve_cores` (ex: 0 e 1) exclusivamente para o
    KWin Wayland, interface gráfica e PipeWire, garantindo que o mouse e a
    área de trabalho nunca engasguem durante a separação de IA.
    """
    total = psutil.cpu_count(logical=True) or 8
    if total > 4:
        allowed = list(range(reserve_cores, total))
    else:
        allowed = list(range(total))

    try:
        p = psutil.Process()
        p.cpu_affinity(allowed)
        log.info("Afinidade de CPU ajustada: núcleos %s ativos (núcleos 0-%d reservados para SO).", allowed, reserve_cores - 1)
    except Exception as e:
        log.debug("Aviso ao definir afinidade de CPU: %s", e)
        allowed = list(range(total))

    return allowed


def get_shielded_thread_count(max_ratio: float = 0.70) -> int:
    """
    Retorna uma contagem de threads segura para CPU Xeon E5-2667 v2 (16 threads).
    Ex.: 16 * 0.70 = 10 a 11 threads.
    """
    total_threads = psutil.cpu_count(logical=True) or 8
    safe_threads = max(2, int(total_threads * max_ratio))
    return min(safe_threads, 10)


def apply_process_shield(reserve_cores: int = 2):
    """Aplica nice, ionice, afinidade de CPU e variáveis de ambiente seguras."""
    # 1. Blindagem de GPU (Polaris RX 580 não deve ser sondada por PyTorch ROCm/CUDA)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HIP_VISIBLE_DEVICES"] = ""

    # 2. Ajustar nice para +19 (menor prioridade de CPU)
    try:
        os.nice(19)
        log.info("Process nice ajustado para 19.")
    except Exception as e:
        log.debug("Aviso ao ajustar nice: %s", e)

    # 3. Ajustar ionice para Best Effort classe 7 (menor prioridade de disco)
    try:
        p = psutil.Process()
        if hasattr(psutil, "IOPRIO_CLASS_BE"):
            p.ionice(psutil.IOPRIO_CLASS_BE, value=7)
    except Exception as e:
        log.debug("Aviso ao ajustar ionice: %s", e)

    # 4. Afinidade de CPU (reserva núcleos 0 e 1 para desktop)
    allowed_cores = apply_cpu_affinity(reserve_cores=reserve_cores)

    # 5. Limitar threads no PyTorch e bibliotecas BLAS/OpenMP
    threads = min(len(allowed_cores), get_shielded_thread_count())
    try:
        import torch
        torch.set_num_threads(threads)
    except Exception:
        pass

    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ["MKL_NUM_THREADS"] = str(threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(threads)
    log.info("Process shield ativo: %d threads de computação.", threads)
