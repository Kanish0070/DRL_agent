/**
 * state.h — Shared node diagnostic state (T8.5, T8.6).
 *
 * Central place for all mutable node-level state that multiple tasks
 * need to read/write. Tasks must NOT read fields they don't own without
 * considering race conditions; most fields here are written by exactly
 * one task, so simple volatile access is sufficient.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    /* T8.5 diagnostics */
    volatile bool     sensor_fault;       /* set by sensor_task on read failure */
    volatile uint32_t tx_success_count;   /* set by network_task */
    volatile uint32_t tx_fail_count;      /* set by network_task */

    /* T8.6 reconnection state */
    volatile bool     post_reboot;        /* set on init/reconnect; cleared after HB delivery */
    char              gateway_ip[32];     /* set by network_task on first GRANT receive */
} node_state_t;

/* Single global instance defined in state.c */
extern node_state_t g_node_state;
