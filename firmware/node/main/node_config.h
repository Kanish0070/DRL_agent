/**
 * node_config.h — Compile-time per-node configuration.
 *
 * Build with -DCONFIG_NODE_ID=0..3 to produce any of the 4 node images
 * from this single source tree (literal acceptance criterion T8.1).
 *
 * Constants mirror config/system.yaml and ns3-sim/aoi-scheduler-sim.cc lines 50-56.
 * DO NOT invent new constants here — match the Python source of truth exactly.
 */
#pragma once
#include <stdint.h>

/* ── Node class table ─────────────────────────────────────────
 * node_classes: ["urgent", "urgent", "important", "routine"]
 * weights:      urgent=10, important=3, routine=1
 * thresholds_ms: urgent=200, important=500, routine=1000
 * shield_ceilings_s: urgent=2.0, important=6.0, routine=20.0
 * ─────────────────────────────────────────────────────────── */
typedef struct {
    const char *class_name;
    float       weight;
    float       threshold_s;
    float       shield_ceiling_s;
} node_role_t;

static const node_role_t NODE_ROLES[4] = {
    /* node 0 */ { "urgent",    10.0f, 0.200f,  2.0f },
    /* node 1 */ { "urgent",    10.0f, 0.200f,  2.0f },
    /* node 2 */ { "important",  3.0f, 0.500f,  6.0f },
    /* node 3 */ { "routine",    1.0f, 1.000f, 20.0f },
};

#ifndef CONFIG_NODE_ID
#error "CONFIG_NODE_ID must be defined at build time (0-3). Use -DCONFIG_NODE_ID=<n>"
#endif

#if CONFIG_NODE_ID < 0 || CONFIG_NODE_ID > 3
#error "CONFIG_NODE_ID must be 0, 1, 2, or 3"
#endif

#define THIS_NODE_ID        ((uint8_t)(CONFIG_NODE_ID))
#define THIS_NODE_CLASS     (NODE_ROLES[CONFIG_NODE_ID].class_name)
#define THIS_NODE_WEIGHT    (NODE_ROLES[CONFIG_NODE_ID].weight)
#define THIS_THRESHOLD_S    (NODE_ROLES[CONFIG_NODE_ID].threshold_s)
#define THIS_SHIELD_CEIL_S  (NODE_ROLES[CONFIG_NODE_ID].shield_ceiling_s)

/* ── Network config (mirrors config/system.yaml network: section) ── */
#define UDP_PORT_GRANT   5006u
#define UDP_PORT_UPLINK  5005u

/* ── Timing config (mirrors measured_params.yaml timing: section) ── */
#define HEARTBEAT_PERIOD_MS   2000u   /* 2.0s nominal */
#define HEARTBEAT_JITTER_MS    200u   /* ±0.2s, matches ns3-sim SendHeartbeat */
#define SENSOR_PERIOD_MS       100u   /* 10 Hz = 100ms */
