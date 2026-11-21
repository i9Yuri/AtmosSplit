"""Liga o produtor Python ao callback C11 do PortAudio no Linux x86-64."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from cffi import FFI
import numpy as np

ffi = FFI()
ffi.cdef("""
    typedef struct MonitorRing MonitorRing;
    typedef struct MonitorPort MonitorPort;
    MonitorRing *monitor_ring_new(size_t, size_t);
    void monitor_ring_free(MonitorRing *);
    int monitor_has_space(const MonitorRing *);
    int monitor_push(MonitorRing *, const float *, size_t);
    unsigned long monitor_consumed(const MonitorRing *);
    unsigned long monitor_underruns(const MonitorRing *);
    MonitorPort *monitor_port_new(void);
    void monitor_port_free(MonitorPort *);
    void monitor_publish(MonitorPort *, MonitorRing *);
    MonitorRing *monitor_acknowledged(const MonitorPort *);
    struct PaStreamCallbackTimeInfo;
    int monitor_callback(const void *, void *, unsigned long, const struct PaStreamCallbackTimeInfo *,
                         unsigned long, void *);
""")


@lru_cache(maxsize=1)
def _library():
    source = Path(__file__).with_name("monitor_callback.c")
    digest = sha256(source.read_bytes()).hexdigest()[:20]
    prefix = Path(sys.prefix) / "lib"
    if sys.prefix == sys.base_prefix or not os.access(prefix, os.W_OK):
        prefix = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache = prefix / "atmossplit-native"
    cache.mkdir(parents=True, exist_ok=True)
    library = cache / f"monitor-{digest}.so"
    if not library.exists():
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            stage = Path(tmp) / "monitor.so"
            cmd = ["cc", "-std=c11", "-O2", "-shared", "-fPIC", "-march=x86-64", "-mno-avx",
                   "-mno-avx2", "-mno-fma", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(stage)]
            try:
                build = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                       env={**os.environ, "CCACHE_DISABLE": "1"})
            except FileNotFoundError as exc:
                raise RuntimeError("O primeiro uso do monitor requer um compilador C11 (cc).") from exc
            if build.returncode:
                raise RuntimeError(f"Falha ao compilar o monitor de áudio: {build.stderr[-600:]}")
            stage.replace(library)
    return ffi.dlopen(str(library))


class NativeRing:
    def __init__(self, block: int, frames: int):
        self.lib = _library()
        ptr = self.lib.monitor_ring_new(block, frames)
        if ptr == ffi.NULL:
            raise MemoryError("Falha ao reservar os blocos de áudio.")
        self.ptr = ffi.gc(ptr, self.lib.monitor_ring_free)

    def push(self, stereo: np.ndarray) -> bool:
        if stereo.dtype != np.float32 or stereo.ndim != 2 or stereo.shape[1] != 2 or not stereo.flags.c_contiguous:
            raise ValueError("O bloco do monitor precisa ser estéreo float32 contíguo.")
        return bool(self.lib.monitor_push(self.ptr, ffi.from_buffer("const float[]", stereo), len(stereo)))

    @property
    def available(self) -> bool:
        return bool(self.lib.monitor_has_space(self.ptr))

    @property
    def consumed(self) -> int:
        return self.lib.monitor_consumed(self.ptr)

    @property
    def underruns(self) -> int:
        return self.lib.monitor_underruns(self.ptr)


class NativePort:
    """O callback confirma cada troca antes da liberação das filas anteriores."""
    def __init__(self):
        self.lib = _library()
        ptr = self.lib.monitor_port_new()
        if ptr == ffi.NULL:
            raise MemoryError("Falha ao reservar o transporte de áudio.")
        self.ptr = ffi.gc(ptr, self.lib.monitor_port_free)
        self.current: NativeRing | None = None
        self.retired: list[NativeRing] = []

    def publish(self, ring: NativeRing) -> None:
        if self.current is not None:
            self.retired.append(self.current)
        self.current = ring
        self.lib.monitor_publish(self.ptr, ring.ptr)

    def collect(self) -> None:
        if self.retired and self.lib.monitor_acknowledged(self.ptr) == self.current.ptr:
            self.retired.clear()

    def open_stream(self, sd, rate: int, block: int, device: int | None):
        # Interface CData/userdata oferecida pelo sounddevice a autores de bibliotecas.
        return sd._StreamBase(kind="output", samplerate=rate, channels=2, blocksize=block,
                              dtype="float32", device=device, callback=self.lib.monitor_callback,
                              userdata=ffi.cast("void *", self.ptr))
