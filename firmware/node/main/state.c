/**
 * state.c — Global node state definition and WiFi event handler (T8.6).
 *
 * On WiFi disconnect/reconnect: sends a HelloPacket with FLAG_POST_REBOOT
 * so the gateway knows to treat this node's prior AoI/RSSI state as stale.
 */
#include "state.h"
#include "node_config.h"
#include "packet.h"
#include "network_task.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"

static const char *TAG = "state";

/* ── Global node state ──────────────────────────────────────── */
node_state_t g_node_state = {
    .sensor_fault    = false,
    .tx_success_count = 0,
    .tx_fail_count   = 0,
    .post_reboot     = true,    /* always true at boot */
    .gateway_ip      = {0},
};

/* ── WiFi event handler — T8.6 ─────────────────────────────── */
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data) {
    if (event_base != WIFI_EVENT) return;

    if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi disconnected — reconnecting...");
        esp_wifi_connect();
    } else if (event_id == WIFI_EVENT_STA_CONNECTED) {
        ESP_LOGI(TAG, "WiFi reconnected — marking post_reboot and sending HelloPacket");
        g_node_state.post_reboot = true;

        /* Send HelloPacket with FLAG_POST_REBOOT so gateway invalidates stale state */
        if (g_node_state.gateway_ip[0] != '\0') {
            pkt_hello_t hello;
            pkt_build_hello(&hello, THIS_NODE_ID, FLAG_POST_REBOOT);

            struct sockaddr_in dest = {
                .sin_family = AF_INET,
                .sin_port   = htons(UDP_PORT_UPLINK),
            };
            lwip_inet_pton(AF_INET, g_node_state.gateway_ip, &dest.sin_addr);

            int sock = lwip_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            if (sock >= 0) {
                lwip_sendto(sock, &hello, sizeof(hello), 0,
                            (struct sockaddr *)&dest, sizeof(dest));
                lwip_close(sock);
                ESP_LOGI(TAG, "HelloPacket (FLAG_POST_REBOOT) sent to gateway");
            }
        }
    }
}

void state_register_wifi_handler(void) {
    ESP_ERROR_CHECK(esp_event_handler_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL));
}
