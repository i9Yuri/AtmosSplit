"""Codificação JOC das onze posições espaciais e do bed LFE independente."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, gcd, radians, sin
from pathlib import Path

import ac3forge as ac3
import numpy as np
from scipy import signal


# Ordem PCM/WAVE 7.1.4. O LFE é transportado diretamente no bed (TS 103 420 §6.3.2.2).
OBJECT_CHANNELS = (0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11)
ROOM_POSITIONS = ((0., 0., 0.), (1., 0., 0.), (.5, 0., 0.),
                  (0., 1., 0.), (1., 1., 0.), (0., .5, 0.), (1., .5, 0.),
                  (0., 0., 1.), (1., 0., 1.), (0., 1., 1.), (1., 1., 1.))


def _carrier_matrix() -> np.ndarray:
    # Mesma lei de azimute de pan_room() no ac3forge 0.10, ordem AC-3 L,C,R,Ls,Rs,LFE.
    angles = (0., 30., 110., 250., 330., 360.)
    channels = (1, 0, 3, 4, 2, 1)
    matrix = np.zeros((12, 6), dtype="f")
    for source, (x, y, _) in zip(OBJECT_CHANNELS, ROOM_POSITIONS):
        az = degrees(atan2(.5-x, .5-y)) % 360
        k = int(np.searchsorted(angles, az, side="right"))-1
        gains = np.array([sin(radians(angles[k+1]-az)), sin(radians(az-angles[k]))])
        matrix[source, [channels[k], channels[k+1]]] = gains/np.linalg.norm(gains)
    matrix[3, 5] = 1.
    return matrix


def _emdf_container(frame: bytes) -> bytes:
    """Recupera o contêiner gerado pelo encoder no campo skipl (A/52, bloco zero).

    skipl tem nove bits e inclui o cabeçalho EMDF de quatro bytes. Ambos os
    comprimentos têm de concordar, mesmo quando a syncword não está alinhada a byte.
    """
    bits = int.from_bytes(frame, "big")
    for shift in range(8):
        aligned = frame if not shift else (bits << shift).to_bytes(len(frame)+1, "big")[1:]
        start = aligned.find(b"\x58\x38", 2)
        while start >= 2:
            size = 4 + int.from_bytes(aligned[start+2:start+4], "big")
            skip = int.from_bytes(aligned[start-2:start], "big") & 511
            if 4 < size == skip and start+size <= len(aligned):
                return aligned[start:start+size]
            start = aligned.find(b"\x58\x38", start+1)
    raise ValueError("O encoder não entregou um contêiner EMDF íntegro.")


@dataclass(frozen=True)
class JocMeasurements:
    trim_db: float
    decoded_true_peak_dbtp: float | None


class _DecodedPeak:
    """Mede bed e objetos em lotes 4× com sobreposição FIR entre lotes."""
    def __init__(self):
        self.decoder = ac3.Eac3Decoder()
        self.blocks: list[np.ndarray] = []
        self.peak = 0.
        self.has_context = False

    def add(self, frame: bytes) -> None:
        unit = self.decoder.decode_access_unit(frame)
        if unit is None or unit.object_metadata is None or len(unit.object_audio) != len(OBJECT_CHANNELS):
            raise ValueError("O quadro JOC não recuperou os onze objetos.")
        self.blocks.append(np.stack([*unit.channels, *unit.object_audio], axis=1))
        if len(self.blocks) == 12:
            self.flush(final=False)

    def flush(self, final: bool = True) -> float:
        if self.blocks:
            matrix = np.concatenate(self.blocks)
            # A interpolação na borda externa recebe contexto real no próximo lote.
            high = signal.resample_poly(matrix, 4, 1, axis=0)
            end = len(high) if final else len(high)-128
            start = 128 if self.has_context else 0
            self.peak = max(self.peak, float(np.max(np.abs(high[start:end]))))
            self.has_context = True
            self.blocks = [] if final else [matrix[-64:]]
        return self.peak


def encode_joc(matrix: np.ndarray, path: Path, sample_rate: int, bitrate: int) -> JocMeasurements:
    if sample_rate != 48000:
        d = gcd(int(sample_rate), 48000)
        matrix = signal.resample_poly(matrix, 48000//d, sample_rate//d, axis=0)
    spf = ac3.SAMPLES_PER_FRAME
    layout = _carrier_matrix()
    placements = [ac3.ObjectPlacement(position=ac3.Position(x=x, y=y, z=z), gain=1., lfe_send=0.)
                  for x, y, z in ROOM_POSITIONS]
    # A API de objetos injeta cada fonte no ring 5.0 inclusive quando lfe_send=1.
    # Geramos a matriz JOC com os 11 sinais full-range e entregamos o mesmo downmix
    # PCM ao encoder de bed, agora com o sexto canal vindo do LFE discreto.
    ceiling = 10**(-1/20)
    peak = 0.
    for i in range(0, len(matrix), 32768):
        bed = matrix[i:i+32768] @ layout
        peak = max(peak, float(np.max(np.abs(bed))))
    gain = min(1., ceiling/max(peak, 1e-12))
    for attempt in range(3):
        cfg = ac3.AtmosConfig(bitrate_kbps=bitrate, dialnorm=31, emit_object_metadata=True)
        objects = ac3.AtmosEncoder(cfg, len(placements))
        bed_cfg = ac3.eac3.FrameConfig(sample_rate=ac3.SampleRate.k48000, bitrate_kbps=bitrate,
                                      acmod=ac3.Acmod.k3_2, lfe=True, dialnorm=31,
                                      oba_complexity_index=len(placements)+1)
        carrier = ac3.eac3.FrameEncoder(bed_cfg)
        qc = _DecodedPeak()
        batch = np.zeros((spf, 12), dtype="f")
        with path.open("wb") as out:
            # O último acesso inclui a cauda MDCT/QMF. Um impulso no fim da
            # música ainda precisa de transform_samples para chegar ao decoder.
            for i in range(0, len(matrix)+objects.latency.transform_samples, spf):
                data = matrix[i:i+spf]
                batch[:len(data)] = data*gain
                batch[len(data):] = 0
                obj = np.ascontiguousarray(batch[:, OBJECT_CHANNELS].T)
                metadata_frame = objects.encode_frame(obj, placements)
                bed = np.ascontiguousarray((batch @ layout).T)
                frame = carrier.encode_frame(bed, aux=_emdf_container(metadata_frame))
                qc.add(frame)
                out.write(frame)
        decoded_peak = qc.flush()
        if decoded_peak <= ceiling + 1e-5:
            return JocMeasurements(float(20*np.log10(gain)), float(20*np.log10(decoded_peak)) if decoded_peak else None)
        # A quantização com perdas pode criar picos intersample. Correção vinculada
        # a todos os canais, seguida de nova codificação e medição.
        gain *= .975*ceiling/decoded_peak
    raise ValueError("O áudio decodificado excedeu o teto de −1 dBTP.")
