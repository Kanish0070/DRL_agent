/**
 * main.c — Application entry point (T8.1, T8.2–T8.6 wiring).
 *
 * Build one binary, target node role via CONFIG_NODE_ID:
 *     idf.py build -DCONFIG_NODE_ID=0   # urgent node 0
 *     idf.py build -DCONFIG_NODE_ID=2   # important node 2
 *
 * D1.3 MANDATORY: esp_wifi_set_ps(WIFI_PS_NONE) before esp_wifi_start().
 */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"

#include "node_config.h"
#include "lcfs_buffer.h"
#include "state.h"
#include "network_task.h"
#include "sensor_task.h"
#include "heartbeat_task.h"

static const char *TAG = "main";

/* ── Global shared LCFS buffer ──────────────────────────────── */
lcfs_buf_t g_lcfs;

/* ── WiFi credentials (set via menuconfig / sdkconfig in production) ── */
#ifndef CONFIG_WIFI_SSID
#define CONFIG_WIFI_SSID "AoI_GW"
#endif
#ifndef CONFIG_WIFI_PASSWORD
#define CONFIG_WIFI_PASSWORD "changeme"
#endif

static void wifi_init(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    /* D1.3 MANDATORY: disable power-save to keep latency deterministic */
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    wifi_config_t wifi_cfg = {
        .sta = {
            .ssid     = CONFIG_WIFI_SSID,
            .password = CONFIG_WIFI_PASSWORD,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg));

    state_register_wifi_handler();   /* T8.6 reconnection + HelloPacket */

    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
}

void app_main(void) {
    /* NVS required for WiFi */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    /* Initialise shared LCFS buffer */
    lcfs_init(&g_lcfs);

    ESP_LOGI(TAG, "AoI Node booting: node_id=%u class=%s weight=%.0f",
             THIS_NODE_ID, THIS_NODE_CLASS, (double)THIS_NODE_WEIGHT);

    wifi_init();

    /* Spawn FreeRTOS tasks */
    xTaskCreate(sensor_task,    "sensor",    4096, NULL, 5, NULL);
    xTaskCreate(network_task,   "network",   8192, NULL, 6, NULL);
    xTaskCreate(heartbeat_task, "heartbeat", 4096, NULL, 4, NULL);
}
