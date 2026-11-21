/* PortAudio output callback. One producer and one consumer per ring. */
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(ATOMIC_LONG_LOCK_FREE == 2 && ATOMIC_POINTER_LOCK_FREE == 2,
               "AtmosSplit requires lock-free native counters and pointers");

enum { SLOT_COUNT = 3, CHANNELS = 2 };

typedef struct {
    size_t block, total, length[SLOT_COUNT], offset;
    _Atomic unsigned long read_slot, write_slot, consumed, underruns;
    float samples[];
} MonitorRing;

typedef struct {
    _Atomic(MonitorRing *) target;
    _Atomic(MonitorRing *) acknowledged;
} MonitorPort;

MonitorRing *monitor_ring_new(size_t block, size_t total) {
    if (!block || block > (SIZE_MAX - sizeof(MonitorRing)) /
                          (SLOT_COUNT * CHANNELS * sizeof(float))) return NULL;
    MonitorRing *ring = calloc(1, sizeof(*ring) + block * SLOT_COUNT * CHANNELS * sizeof(float));
    if (ring) {
        ring->block = block;
        ring->total = total;
        atomic_init(&ring->read_slot, 0);
        atomic_init(&ring->write_slot, 0);
        atomic_init(&ring->consumed, 0);
        atomic_init(&ring->underruns, 0);
    }
    return ring;
}

void monitor_ring_free(MonitorRing *r) { free(r); }

int monitor_has_space(const MonitorRing *r) {
    return atomic_load_explicit(&r->write_slot, memory_order_relaxed)
         - atomic_load_explicit(&r->read_slot, memory_order_acquire) < SLOT_COUNT;
}

int monitor_push(MonitorRing *r, const float *stereo, size_t frames) {
    if (!frames || frames > r->block || !monitor_has_space(r)) return 0;
    unsigned long seq = atomic_load_explicit(&r->write_slot, memory_order_relaxed);
    size_t slot = seq % SLOT_COUNT;
    memcpy(r->samples + slot * r->block * CHANNELS, stereo, frames * CHANNELS * sizeof(float));
    r->length[slot] = frames;
    atomic_store_explicit(&r->write_slot, seq + 1, memory_order_release);
    return 1;
}

unsigned long monitor_consumed(const MonitorRing *r) { return atomic_load(&r->consumed); }
unsigned long monitor_underruns(const MonitorRing *r) { return atomic_load(&r->underruns); }

MonitorPort *monitor_port_new(void) {
    MonitorPort *port = malloc(sizeof(*port));
    if (port) {
        atomic_init(&port->target, NULL);
        atomic_init(&port->acknowledged, NULL);
    }
    return port;
}

void monitor_port_free(MonitorPort *port) { free(port); }
void monitor_publish(MonitorPort *port, MonitorRing *ring) { atomic_store(&port->target, ring); }
MonitorRing *monitor_acknowledged(const MonitorPort *port) { return atomic_load(&port->acknowledged); }

struct PaStreamCallbackTimeInfo;
int monitor_callback(const void *input, void *output, unsigned long frames,
                     const struct PaStreamCallbackTimeInfo *time, unsigned long flags, void *context) {
    (void)input; (void)time;
    MonitorPort *port = context;
    MonitorRing *r = atomic_load_explicit(&port->target, memory_order_acquire);
    float *dst = output;
    size_t written = 0;
    if (r) {
        unsigned long seq = atomic_load_explicit(&r->read_slot, memory_order_relaxed);
        /* Limit work to the blocks already published at callback entry. */
        unsigned long end = atomic_load_explicit(&r->write_slot, memory_order_acquire);
        while (seq != end && written < frames) {
            size_t slot = seq % SLOT_COUNT;
            size_t count = r->length[slot] - r->offset;
            if (count > frames - written) count = frames - written;
            memcpy(dst + written * CHANNELS, r->samples + (slot * r->block + r->offset) * CHANNELS,
                   count * CHANNELS * sizeof(float));
            r->offset += count;
            written += count;
            if (r->offset == r->length[slot]) {
                r->offset = 0;
                atomic_store_explicit(&r->read_slot, ++seq, memory_order_release);
            }
        }
        unsigned long cursor = atomic_load_explicit(&r->consumed, memory_order_relaxed) + written;
        atomic_store_explicit(&r->consumed, cursor, memory_order_release);
        /* paOutputUnderflow = 0x4. Priming a buffer is not an underrun. */
        if (cursor < r->total && (written < frames || (flags & 4)))
            atomic_store_explicit(&r->underruns, atomic_load_explicit(&r->underruns, memory_order_relaxed) + 1,
                                  memory_order_relaxed); /* sole writer */
    }
    if (written < frames)
        memset(dst + written * CHANNELS, 0, (frames - written) * CHANNELS * sizeof(float));
    atomic_store_explicit(&port->acknowledged, r, memory_order_release);
    return 0; /* paContinue; the producer drains/stops the device at EOF */
}
