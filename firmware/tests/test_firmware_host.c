/**
 * test_firmware_host.c — T8.7: Host-side Unity unit tests for firmware logic.
 *
 * Tests purely logical firmware code (no real hardware needed):
 *   1. CRC16-CCITT correctness
 *   2. Packet golden bytes (matching Python's test_packets.py)
 *   3. Foreign-grant rejection (pkt_validate_grant node_id check)
 *   4. LCFS overwrite + alarm-latch-survives-overwrite (mirrors test_sim_queue.py)
 *   5. Node role derivation from CONFIG_NODE_ID
 *
 * Build and run on host:
 *   gcc -DCONFIG_NODE_ID=0 -DHOST_TEST \
 *       -I../main \
 *       test_firmware_host.c unity/unity.c \
 *       -o test_firmware_host && ./test_firmware_host
 *
 * On ESP-IDF with native/host component:
 *   idf.py -T host test
 */
#include "unity.h"

/* ── Host-test stubs for FreeRTOS primitives ─────────────────
 * On host, we replace FreeRTOS mutex with a no-op so lcfs_buffer.h compiles. */
#ifdef HOST_TEST
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
typedef void* SemaphoreHandle_t;
#define xSemaphoreCreateMutex()      ((void*)1)
#define xSemaphoreTake(s, t)         pdTRUE
#define xSemaphoreGive(s)            do {} while(0)
#define pdMS_TO_TICKS(x)             (x)
#define pdTRUE                       1
#endif

#include "../main/packet.h"
#include "../main/lcfs_buffer.h"
#include "../main/node_config.h"


/* ══ CRC16 ══════════════════════════════════════════════════ */
void test_crc16_standard_check_value(void) {
    /* CRC-16/CCITT-FALSE reference: "123456789" -> 0x29B1 */
    const uint8_t msg[] = "123456789";
    TEST_ASSERT_EQUAL_HEX16(0x29B1, crc16_ccitt(msg, 9));
}

/* ══ Packet golden bytes (match Python test_packets.py) ═════ */
void test_grant_packet_golden_bytes(void) {
    pkt_grant_t p;
    pkt_fill_header(&p.hdr, MSG_GRANT, 2, 0);
    p.slot_id     = 42;
    p.deadline_us = 100000;
    pkt_finalise((uint8_t*)&p, sizeof(p));

    const char *expected_hex = "1da0010102002a000000a0860100e525";
    uint8_t expected[16];
    for (int i = 0; i < 16; i++) {
        char byte_str[3] = { expected_hex[i*2], expected_hex[i*2+1], '\0' };
        expected[i] = (uint8_t)strtol(byte_str, NULL, 16);
    }
    TEST_ASSERT_EQUAL_MEMORY(expected, &p, 16);
}

void test_data_packet_size(void) {
    pkt_data_t p;
    pkt_build_data(&p, 1, 0, 1, 100000);
    TEST_ASSERT_EQUAL(16, sizeof(p));  /* 6 + 4 + 4 + 2 */
    /* Verify CRC over header+payload */
    uint16_t expected_crc = crc16_ccitt((uint8_t*)&p, sizeof(p) - 2);
    uint16_t stored_crc   = p.crc;
    TEST_ASSERT_EQUAL_HEX16(expected_crc, stored_crc);
}

void test_heartbeat_packet_size(void) {
    pkt_heartbeat_t p;
    pkt_build_heartbeat(&p, 0, 0, -65);
    TEST_ASSERT_EQUAL(12, sizeof(p));  /* 6 + 4 + 2 */
    uint16_t expected_crc = crc16_ccitt((uint8_t*)&p, sizeof(p) - 2);
    TEST_ASSERT_EQUAL_HEX16(expected_crc, p.crc);
}

void test_hello_packet_size(void) {
    pkt_hello_t p;
    pkt_build_hello(&p, 1, FLAG_POST_REBOOT);
    TEST_ASSERT_EQUAL(8, sizeof(p));   /* 6 + 2 */
    uint16_t expected_crc = crc16_ccitt((uint8_t*)&p, sizeof(p) - 2);
    TEST_ASSERT_EQUAL_HEX16(expected_crc, p.crc);
}

/* ══ Foreign-grant guard ════════════════════════════════════ */
void test_validate_grant_accepts_correct_node(void) {
    pkt_grant_t p;
    pkt_fill_header(&p.hdr, MSG_GRANT, THIS_NODE_ID, 0);
    p.slot_id     = 1;
    p.deadline_us = 1;
    pkt_finalise((uint8_t*)&p, sizeof(p));
    TEST_ASSERT_TRUE(pkt_validate_grant(&p, THIS_NODE_ID));
}

void test_validate_grant_rejects_foreign_node(void) {
    uint8_t foreign_id = (THIS_NODE_ID + 1) % 4;
    pkt_grant_t p;
    pkt_fill_header(&p.hdr, MSG_GRANT, foreign_id, 0);
    p.slot_id     = 1;
    p.deadline_us = 1;
    pkt_finalise((uint8_t*)&p, sizeof(p));
    TEST_ASSERT_FALSE(pkt_validate_grant(&p, THIS_NODE_ID));
}

void test_validate_grant_rejects_bad_magic(void) {
    pkt_grant_t p;
    pkt_fill_header(&p.hdr, MSG_GRANT, THIS_NODE_ID, 0);
    p.hdr.magic   = 0xDEAD;   /* corrupt */
    p.slot_id     = 1;
    p.deadline_us = 1;
    pkt_finalise((uint8_t*)&p, sizeof(p));
    TEST_ASSERT_FALSE(pkt_validate_grant(&p, THIS_NODE_ID));
}

/* ══ LCFS buffer — mirrors test_sim_queue.py semantics ══════ */
void test_lcfs_push_overwrites(void) {
    lcfs_buf_t buf;
    lcfs_init(&buf);

    lcfs_push(&buf, false);
    lcfs_age(&buf, 500000);    /* 0.5s */
    lcfs_push(&buf, false);    /* fresh overwrite, age resets to 0 */
    TEST_ASSERT_EQUAL(0, lcfs_pop(&buf));
}

void test_lcfs_alarm_latch_survives_overwrite(void) {
    lcfs_buf_t buf;
    lcfs_init(&buf);

    lcfs_push(&buf, true);     /* alarm sample */
    lcfs_push(&buf, false);    /* non-alarm overwrites data but NOT the latch */
    TEST_ASSERT_TRUE(buf.alarm_latched);
}

void test_lcfs_alarm_cleared_only_by_explicit_ack(void) {
    lcfs_buf_t buf;
    lcfs_init(&buf);

    lcfs_push(&buf, true);
    lcfs_pop(&buf);            /* pop does NOT clear alarm */
    TEST_ASSERT_TRUE(buf.alarm_latched);
    lcfs_clear_alarm(&buf);    /* explicit ack */
    TEST_ASSERT_FALSE(buf.alarm_latched);
}

void test_lcfs_has_data_after_push(void) {
    lcfs_buf_t buf;
    lcfs_init(&buf);
    TEST_ASSERT_FALSE(buf.has_data);
    lcfs_push(&buf, false);
    TEST_ASSERT_TRUE(buf.has_data);
    lcfs_pop(&buf);
    TEST_ASSERT_FALSE(buf.has_data);
}

/* ══ Node role derivation ═══════════════════════════════════ */
void test_node_role_weight(void) {
    /* node 0 and 1 are urgent (weight=10), node 2 important (3), node 3 routine (1) */
    TEST_ASSERT_EQUAL_FLOAT(10.0f, NODE_ROLES[0].weight);
    TEST_ASSERT_EQUAL_FLOAT(10.0f, NODE_ROLES[1].weight);
    TEST_ASSERT_EQUAL_FLOAT(3.0f,  NODE_ROLES[2].weight);
    TEST_ASSERT_EQUAL_FLOAT(1.0f,  NODE_ROLES[3].weight);
}

void test_this_node_role_matches_config(void) {
    TEST_ASSERT_EQUAL_FLOAT(NODE_ROLES[THIS_NODE_ID].weight, THIS_NODE_WEIGHT);
    TEST_ASSERT_EQUAL_FLOAT(NODE_ROLES[THIS_NODE_ID].shield_ceiling_s, THIS_SHIELD_CEIL_S);
}

/* ══ Unity runner ════════════════════════════════════════════ */
int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_crc16_standard_check_value);
    RUN_TEST(test_grant_packet_golden_bytes);
    RUN_TEST(test_data_packet_size);
    RUN_TEST(test_heartbeat_packet_size);
    RUN_TEST(test_hello_packet_size);
    RUN_TEST(test_validate_grant_accepts_correct_node);
    RUN_TEST(test_validate_grant_rejects_foreign_node);
    RUN_TEST(test_validate_grant_rejects_bad_magic);
    RUN_TEST(test_lcfs_push_overwrites);
    RUN_TEST(test_lcfs_alarm_latch_survives_overwrite);
    RUN_TEST(test_lcfs_alarm_cleared_only_by_explicit_ack);
    RUN_TEST(test_lcfs_has_data_after_push);
    RUN_TEST(test_node_role_weight);
    RUN_TEST(test_this_node_role_matches_config);

    return UNITY_END();
}
