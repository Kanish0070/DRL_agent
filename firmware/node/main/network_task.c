/**
 * network_task.c — T8.2: Grant-reply network task (FreeRTOS).
 *
 * Implements the exact grant-reply protocol validated by ns3-sim's IoTSensorApp:
 *   1. Bind a UDP socket on UDP_PORT_GRANT.
 *   2. On receipt of a GrantPacket, validate magic, version, CRC, and node_id
 *      (0 foreign-grant replies — literal acceptance criterion T8.2).
 *   3. If the LCFS buffer has data, build a DataPacket and send to gateway
 *      on UDP_PORT_UPLINK.
 *   4. If alarm was latched, set FLAG_ALARM_ACK in the response and call
 *      lcfs_clear_alarm().
 *
 * D1.3 MANDATORY: esp_wifi_set_ps(WIFI_PS_NONE) BEFORE wifi_start()
 * — enforced in main.c, referenced here for auditability.
 */
#include "network_task.h"
#include "node_config.h"
#include "packet.h"
#include "lcfs_buffer.h"
#include "state.h"

#include <string.h>
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "esp_log.h"
#include "esp_wifi.h"

static const char *TAG = "net_task";

/* Shared LCFS buffer — defined in main.c, extern'd here */
extern lcfs_buf_t g_lcfs;
/* Shared node state — defined in state.c */
extern node_state_t g_node_state;

static int          s_udp_sock  = -1;
static char         s_gateway_ip[32] = {0};   /* set after DHCP / hello exchange */
static uint32_t     s_slot_counter = 0;

void network_task_set_gateway_ip(const char *ip) {
    strncpy(s_gateway_ip, ip, sizeof(s_gateway_ip) - 1);
}

static int create_udp_socket(uint16_t port) {
    int sock = lwip_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        ESP_LOGE(TAG, "socket() failed: %d", sock);
        return -1;
    }
    struct sockaddr_in addr = {
        .sin_family      = AF_INET,
        .sin_port        = htons(port),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (lwip_bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "bind() on port %u failed", port);
        lwip_close(sock);
        return -1;
    }
    return sock;
}

static void send_data_packet(uint32_t age_us, bool alarm_was_latched) {
    if (s_gateway_ip[0] == '\0') return;   /* no gateway known yet */

    uint8_t flags = 0;
    if (alarm_was_latched) flags |= FLAG_ALARM_ACK;

    pkt_data_t pkt;
    pkt_build_data(&pkt, THIS_NODE_ID, flags, s_slot_counter, age_us);

    struct sockaddr_in dest = {
        .sin_family      = AF_INET,
        .sin_port        = htons(UDP_PORT_UPLINK),
    };
    lwip_inet_pton(AF_INET, s_gateway_ip, &dest.sin_addr);

    int tx_sock = lwip_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (tx_sock >= 0) {
        lwip_sendto(tx_sock, &pkt, sizeof(pkt), 0,
                    (struct sockaddr *)&dest, sizeof(dest));
        lwip_close(tx_sock);
        g_node_state.tx_success_count++;
    } else {
        g_node_state.tx_fail_count++;
    }
}

void network_task(void *pvParameters) {
    s_udp_sock = create_udp_socket(UDP_PORT_GRANT);
    if (s_udp_sock < 0) {
        ESP_LOGE(TAG, "Failed to create grant socket — task exiting");
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGI(TAG, "Listening for GRANT packets on UDP port %u (node_id=%u)",
             UDP_PORT_GRANT, THIS_NODE_ID);

    pkt_grant_t grant_pkt;
    struct sockaddr_in sender;
    socklen_t sender_len = sizeof(sender);

    while (1) {
        int n = lwip_recvfrom(s_udp_sock, &grant_pkt, sizeof(grant_pkt), 0,
                              (struct sockaddr *)&sender, &sender_len);
        if (n < 0) {
            ESP_LOGW(TAG, "recvfrom error %d", n);
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }
        if (n != (int)sizeof(grant_pkt)) continue;

        /* ── Foreign-grant guard (0 foreign-grant replies in 10k slots) ── */
        if (!pkt_validate_grant(&grant_pkt, THIS_NODE_ID)) {
            /* Log but do NOT reply — satisfies acceptance criterion. */
            ESP_LOGD(TAG, "Ignoring GRANT for node %u (we are %u)",
                     grant_pkt.hdr.node_id, THIS_NODE_ID);
            continue;
        }

        s_slot_counter = grant_pkt.slot_id;

        /* Record gateway IP for outbound traffic */
        char gw_ip[32];
        lwip_inet_ntop(AF_INET, &sender.sin_addr, gw_ip, sizeof(gw_ip));
        if (strcmp(gw_ip, s_gateway_ip) != 0) {
            network_task_set_gateway_ip(gw_ip);
        }

        /* ── LCFS buffer critical section ── */
        if (xSemaphoreTake(g_lcfs.lock, pdMS_TO_TICKS(5)) == pdTRUE) {
            if (g_lcfs.has_data) {
                uint32_t age_us        = lcfs_pop(&g_lcfs);
                bool     alarm_latched = g_lcfs.alarm_latched;
                if (alarm_latched) {
                    lcfs_clear_alarm(&g_lcfs);
                }
                xSemaphoreGive(g_lcfs.lock);
                send_data_packet(age_us, alarm_latched);
            } else {
                xSemaphoreGive(g_lcfs.lock);
                /* Empty grant — do not reply (gateway tracks wasted slot). */
            }
        }
    }
}
