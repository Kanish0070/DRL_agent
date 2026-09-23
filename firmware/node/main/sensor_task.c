/**
 * sensor_task.c — T8.3: 10 Hz sensor task with LCFS-1 buffer.
 *
 * Mirrors sim/queue.py NodeQueue (LCFS mode) semantics exactly:
 *   - Fresh sample always overwrites whatever is waiting.
 *   - alarm_latched survives overwrite by a non-alarm sample.
 *   - Cleared ONLY by lcfs_clear_alarm() via explicit ack.
 *
 * T8.5 Diagnostics: sets FLAG_SENSOR_FAULT on read failure or out-of-range.
 */
#include "sensor_task.h"
#include "node_config.h"
#include "lcfs_buffer.h"
#include "state.h"

#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "sensor_task";

/* Shared buffer and state */
extern lcfs_buf_t   g_lcfs;
extern node_state_t g_node_state;

/* ── Simulated sensor read (replace with real driver for hardware bring-up) ── */
static bool sensor_read(float *value_out) {
    /* Stub: returns a valid random-ish value. On real hardware, read from
     * ADC/I2C/SPI sensor driver here. Return false on read failure. */
    static uint32_t counter = 0;
    *value_out = (float)(counter++ % 1000) / 10.0f;   /* 0.0 .. 99.9 */
    return true;   /* always healthy in simulation */
}

static bool is_alarm(float value) {
    /* Stub threshold — replace with real alarm logic per application. */
    return value > 90.0f;
}

void sensor_task(void *pvParameters) {
    TickType_t      last_wake     = xTaskGetTickCount();
    const TickType_t period_ticks = pdMS_TO_TICKS(SENSOR_PERIOD_MS);

    while (1) {
        vTaskDelayUntil(&last_wake, period_ticks);

        float   value;
        bool    ok    = sensor_read(&value);
        bool    fault = !ok;
        bool    alarm = ok && is_alarm(value);

        if (fault) {
            /* T8.5: set sensor-fault flag in shared state. */
            g_node_state.sensor_fault = true;
            ESP_LOGW(TAG, "Sensor read failed");
        } else {
            g_node_state.sensor_fault = false;
        }

        /* Push into LCFS buffer under mutex */
        if (xSemaphoreTake(g_lcfs.lock, pdMS_TO_TICKS(5)) == pdTRUE) {
            lcfs_push(&g_lcfs, alarm);
            xSemaphoreGive(g_lcfs.lock);
        } else {
            ESP_LOGW(TAG, "Could not acquire LCFS lock");
        }
    }
}
