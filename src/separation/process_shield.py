"""Política Linux para subprocessos de cálculo do AtmosSplit."""

import logging
import os

import psutil

log = logging.getLogger(__name__)


def apply_cpu_affinity(reserve_cores: int = 2) -> list[int]:
    process = psutil.Process()
    available = process.cpu_affinity()
    allowed = [core for core in available if core >= reserve_cores] or available
    process.cpu_affinity(allowed)
    return allowed


def get_shielded_thread_count(max_ratio: float = 0.70) -> int:
    available = len(psutil.Process().cpu_affinity())
    return max(1, min(8, available, int(available * max_ratio)))


def apply_process_shield(reserve_cores: int = 2) -> None:
    """Aplicar uma vez na entrada do worker, antes de importar Torch e BLAS."""
    os.environ.update(CUDA_VISIBLE_DEVICES="", HIP_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1")
    process = psutil.Process()
    process.nice(19)
    process.ionice(psutil.IOPRIO_CLASS_IDLE)
    cores = apply_cpu_affinity(reserve_cores)
    threads = str(get_shielded_thread_count())
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[key] = threads
    log.info("Worker CPU %s, nice 19, I/O idle, %s threads", cores, threads)
