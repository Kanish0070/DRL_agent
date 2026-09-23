#pragma once
#include "freertos/FreeRTOS.h"

void network_task(void *pvParameters);
void network_task_set_gateway_ip(const char *ip);
