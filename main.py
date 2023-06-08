import time
import network
import esp32
import machine
from machine import Pin
import os
import ubinascii
from machine import unique_id
import _thread
import gc

import state
import gateway
import net
import board
import utils
import mqtt
import secrets
import logging as log

MQTT_CERT_PATH = f"/certs/{secrets.GATEWAY_ID}/certificate.pem.cert"
MQTT_KEY_PATH = f"/certs/{secrets.GATEWAY_ID}/private.pem.key"


if __name__ == "__main__":

    machine.freq(240000000) # default is 160000000, another option is 80000000

    log.inf("starting net loop")
    net_ctx = net.NetworkContext()
    net_ctx.wifi_if = network.WLAN(network.STA_IF)
    #net_ctx.lte_if = network.PPP(board.mdm_uart) # For later :P
    net_ctx.wifi_ssid = secrets.WIFI_SSID
    net_ctx.wifi_password = secrets.WIFI_PASSWORD
    net_ctx.timeout_sec = 30
    _thread.start_new_thread(net.net_loop, [net_ctx])

    log.inf("waiting for net connection")
    while(not state.net_connected):
        time.sleep(1)

    state.pub_qos = 0
    state.sub_qos = 0

    log.inf("starting mqtt loop")
    mqtt_ctx = mqtt.MqttConfig()
    mqtt_ctx.client_id = secrets.GATEWAY_ID
    mqtt_ctx.server = secrets.MQTT_SERVER
    mqtt_ctx.ssl_params = {
                        "cert": utils.load_file(MQTT_CERT_PATH),
                        "key": utils.load_file(MQTT_KEY_PATH),
                        "server_side": False
                    }
    _thread.start_new_thread(mqtt.mqtt_loop, [mqtt_ctx])

    log.inf("starting gateway loop")
    gateway_ctx = gateway.GatewayContext()
    gateway_ctx.dev = board.nrf_uart
    _thread.start_new_thread(gateway.gateway_loop, [gateway_ctx])

    # Periodically run garbage collector
    while(True):
        time.sleep(5)
        gc.collect()
        gc.mem_free()


