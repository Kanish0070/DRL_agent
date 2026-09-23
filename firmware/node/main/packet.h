/**
 * packet.h — Wire-format packet definitions for the AoI scheduler protocol.
 *
 * All layouts MUST match common/contracts/packets.py exactly:
 *   - Same MAGIC_BYTES (0xA01D), VERSION (1), MSG_* type codes
 *   - Same field order and types
 *   - CRC16-CCITT (poly 0x1021, init 0xFFFF) appended after every packet
 *
 * Golden bytes are validated in firmware/tests/test_packets_host.c.
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define MAGIC_BYTES  0xA01Du
#define VERSION      1u

/* Message type codes — mirror packets.py */
#define MSG_GRANT      0x01u
#define MSG_DATA       0x02u
#define MSG_HEARTBEAT  0x03u
#define MSG_HELLO      0x04u
#define MSG_CONTROL    0x05u

/* Flags — mirror packets.py */
#define FLAG_ALARM_LATCHED  (1u << 0)
#define FLAG_SENSOR_FAULT   (1u << 1)
#define FLAG_POST_REBOOT    (1u << 2)
#define FLAG_ALARM_ACK      (1u << 3)

/* ── CRC16-CCITT ──────────────────────────────────────────── */
static inline uint16_t crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            if (crc & 0x8000u)
                crc = (crc << 1) ^ 0x1021u;
            else
                crc <<= 1;
        }
    }
    return crc;
}

/* ── Packed structures (little-endian) ────────────────────── */
#pragma pack(push, 1)

typedef struct {
    uint16_t magic;
    uint8_t  version;
    uint8_t  msg_type;
    uint8_t  node_id;
    uint8_t  flags;
} pkt_header_t;   /* 6 bytes */

typedef struct {
    pkt_header_t hdr;
    uint32_t     slot_id;
    uint32_t     deadline_us;
    uint16_t     crc;
} pkt_grant_t;    /* 6 + 8 + 2 = 16 bytes */

typedef struct {
    pkt_header_t hdr;
    uint32_t     slot_id;
    uint32_t     age_at_tx_us;
    uint16_t     crc;
} pkt_data_t;     /* 16 bytes */

typedef struct {
    pkt_header_t hdr;
    int32_t      rssi;
    uint16_t     crc;
} pkt_heartbeat_t; /* 6 + 4 + 2 = 12 bytes */

typedef struct {
    pkt_header_t hdr;
    uint16_t     crc;
} pkt_hello_t;    /* 6 + 2 = 8 bytes */

typedef struct {
    pkt_header_t hdr;
    uint8_t      command_code;
    uint16_t     crc;
} pkt_control_t;  /* 6 + 1 + 2 = 9 bytes */

#pragma pack(pop)

/* ── Builder helpers ──────────────────────────────────────── */

static inline void pkt_fill_header(pkt_header_t *h, uint8_t msg_type,
                                    uint8_t node_id, uint8_t flags) {
    h->magic    = MAGIC_BYTES;
    h->version  = VERSION;
    h->msg_type = msg_type;
    h->node_id  = node_id;
    h->flags    = flags;
}

/* Appends CRC over all bytes except the last 2 (CRC field itself). */
static inline void pkt_finalise(uint8_t *buf, size_t total_len) {
    uint16_t crc = crc16_ccitt(buf, total_len - 2);
    buf[total_len - 2] = (uint8_t)(crc & 0xFFu);
    buf[total_len - 1] = (uint8_t)(crc >> 8);
}

static inline void pkt_build_data(pkt_data_t *p, uint8_t node_id, uint8_t flags,
                                   uint32_t slot_id, uint32_t age_at_tx_us) {
    pkt_fill_header(&p->hdr, MSG_DATA, node_id, flags);
    p->slot_id      = slot_id;
    p->age_at_tx_us = age_at_tx_us;
    pkt_finalise((uint8_t *)p, sizeof(*p));
}

static inline void pkt_build_heartbeat(pkt_heartbeat_t *p, uint8_t node_id,
                                        uint8_t flags, int32_t rssi) {
    pkt_fill_header(&p->hdr, MSG_HEARTBEAT, node_id, flags);
    p->rssi = rssi;
    pkt_finalise((uint8_t *)p, sizeof(*p));
}

static inline void pkt_build_hello(pkt_hello_t *p, uint8_t node_id, uint8_t flags) {
    pkt_fill_header(&p->hdr, MSG_HELLO, node_id, flags);
    pkt_finalise((uint8_t *)p, sizeof(*p));
}

/* ── Validator ─────────────────────────────────────────────── */
static inline bool pkt_validate_grant(const pkt_grant_t *p, uint8_t expected_node_id) {
    if (p->hdr.magic   != MAGIC_BYTES) return false;
    if (p->hdr.version != VERSION)     return false;
    if (p->hdr.msg_type != MSG_GRANT)  return false;
    if (p->hdr.node_id != expected_node_id) return false;  /* foreign-grant guard */
    /* Verify CRC over header + payload (all bytes except last 2) */
    uint16_t expected_crc = crc16_ccitt((const uint8_t *)p, sizeof(*p) - 2);
    uint16_t actual_crc   = (uint16_t)((const uint8_t *)p)[sizeof(*p)-2] |
                            ((uint16_t)((const uint8_t *)p)[sizeof(*p)-1] << 8);
    return expected_crc == actual_crc;
}
