import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest


@pytest.fixture
def native_output():
    """Fornece buffers a um PaStreamCallback nativo usando a ABI do PortAudio."""
    from src.spatial.native_monitor import NativePort, ffi

    def attach(player):
        port = NativePort()
        port.publish(player._transport.prepare(player.block_size, player._dsp_state.plan.frames))

        def read(output):
            return port.lib.monitor_callback(ffi.NULL, ffi.from_buffer("float[]", output),
                                             len(output), ffi.NULL, 0, port.ptr)
        return read
    return attach
