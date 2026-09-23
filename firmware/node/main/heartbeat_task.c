/**
 * heartbeat_task.c — T8.4: Periodic HeartbeatPacket (2s ± 0.2s jitter).
 *
 * Matches ns3-sim's SendHeartbeat (lines 238-248):
 *   - Sends HeartbeatPacket every HEARTBEAT_PERIOD_MS ± HEARTBEAT_JITTER_MS.
 *   - Includes current RSSI reading (refreshes gateway's RSSI estimate for
 *     starved nodes — F3.2 in the blueprint).
 *   - Sets FLAG_SENSOR_FAULT in flags byte if g_node_state.sensor_fault.
 *   - Sets FLAG_POST_REBOOT in flags byte if g_node_state.post_reboot
 *     (cleared after first heartbeat that delivers it).
 */
#include "heartbeat_task.h"
#include "node_config.h"
#include "packet.h"
#include "state.h"
#include "network_task.h"

#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "esp_log.h"
#include "esp_wifi.h"

static const char *TAG = "hb_task";

extern node_state_t g_node_state;

static int32_t get_current_rssi(void) {
    wifi_ap_record_t ap_info;
    if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
        return (int32_t)ap_info.rssi;
    }
    return -100;   /* fallback if not associated */
}

static void send_heartbeat(int32_t rssi) {
    const char *gw_ip = g_node_state.gateway_ip;
    if (gw_ip[0] == '\0') return;

    uint8_t flags = 0;
    if (g_node_state.sensor_fault) flags |= FLAG_SENSOR_FAULT;
    if (g_node_state.post_reboot)  flags |= FLAG_POST_REBOOT;

    pkt_heartbeat_t pkt;
    pkt_build_heartbeat(&pkt, THIS_NODE_ID, flags, rssi);

    struct sockaddr_in dest = {
        .sin_family = AF_INET,
        .sin_port   = htons(UDP_PORT_UPLINK),
    };
    lwip_inet_pton(AF_INET, gw_ip, &dest.sin_addr);

    int sock = lwip_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock >= 0) {
        lwip_sendto(sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&dest, sizeof(dest));
        lwip_close(sock);
        /* Clear post_reboot after successful delivery */
        if (g_node_state.post_reboot) {
            g_node_state.post_reboot = false;
        }
    }
}

void heartbeat_task(void *pvParameters) {
    while (1) {
        /* Jitter: uniform ± HEARTBEAT_JITTER_MS */
        int32_t jitter_ms = (int32_t)(rand() % (2 * HEARTBEAT_JITTER_MS + 1))
                            - (int32_t)HEARTBEAT_JITTER_MS;
        uint32_t sleep_ms = (uint32_t)((int32_t)HEARTBEAT_PERIOD_MS + jitter_ms);
        vTaskDelay(pdMS_TO_TICKS(sleep_ms));

        int32_t rssi = get_current_rssi();
        send_heartbeat(rssi);
        ESP_LOGD(TAG, "Heartbeat sent: rssi=%d flags=%s%s",
                 (int)rssi,
                 g_node_state.sensor_fault ? "SENSOR_FAULT " : "",
                 g_node_state.post_reboot  ? "POST_REBOOT"   : "");
    }
}
