/**
 * lcfs_buffer.h — LCFS-1 sample buffer with sticky alarm latch.
 *
 * Mirrors sim/queue.py NodeQueue (LCFS mode) semantics exactly:
 *   - A fresh sample always overwrites whatever is waiting.
 *   - The alarm_latched flag, once set, survives overwrite by a
 *     non-alarm sample.  It is cleared ONLY by explicit ack via
 *     lcfs_clear_alarm() — mirrors NodeQueue.clear_alarm().
 *
 * Thread-safe: caller must hold lcfs_buf_t.lock (FreeRTOS mutex)
 * before calling any function that touches the buffer.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

typedef struct {
    bool     has_data;
    uint32_t age_us;       /* age of the buffered sample in microseconds */
    bool     alarm_latched;
    SemaphoreHandle_t lock;
} lcfs_buf_t;

static inline void lcfs_init(lcfs_buf_t *buf) {
    buf->has_data      = false;
    buf->age_us        = 0;
    buf->alarm_latched = false;
    buf->lock          = xSemaphoreCreateMutex();
}

/**
 * lcfs_push — overwrite with a fresh sample (age=0).
 * If is_alarm is true, the latch is set (and stays set until cleared).
 * Must be called with buf->lock held.
 */
static inline void lcfs_push(lcfs_buf_t *buf, bool is_alarm) {
    buf->has_data = true;
    buf->age_us   = 0;
    if (is_alarm) {
        buf->alarm_latched = true;
    }
}

/**
 * lcfs_pop — consume the buffered sample, returns its age in microseconds.
 * Sets has_data = false.  alarm_latched is NOT cleared here.
 * Must be called with buf->lock held.
 */
static inline uint32_t lcfs_pop(lcfs_buf_t *buf) {
    buf->has_data = false;
    return buf->age_us;
}

/**
 * lcfs_age — advance age by delta_us; called every sensor period.
 * Must be called with buf->lock held.
 */
static inline void lcfs_age(lcfs_buf_t *buf, uint32_t delta_us) {
    if (buf->has_data) {
        buf->age_us += delta_us;
    }
}

/**
 * lcfs_clear_alarm — explicit alarm acknowledgement.
 * Must be called with buf->lock held.
 */
static inline void lcfs_clear_alarm(lcfs_buf_t *buf) {
    buf->alarm_latched = false;
}
