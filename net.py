import network
import ntptime
import utime
import urequests
import time

import state

import logging as log

NET_LOOP_POLL_INTERVAL_SEC = 8

USE_WIFI = True
USE_LTE = False


class NetworkContext:
    wifi_if = None
    lte_if = None
    wifi_ssid = ""
    wifi_password = ""
    timeout_sec = 0


# Function to connect to a specific wifi network, with timeout
def connect_to_wifi(ctx):
    iface = ctx.wifi_if
    ssid = ctx.wifi_ssid
    password = ctx.wifi_password
    timeout_msec = ctx.timeout_sec * 1000
    if not iface.isconnected():
        iface.connect(ssid, password)
        # Wait until connected
        t = time.ticks_ms()
        while not iface.isconnected():
            if time.ticks_diff(time.ticks_ms(), t) > timeout_msec:
                iface.disconnect()
                log.err("wifi connect timeout")
                return False
        return True
    else:
        return True


def set_time(): # TODO set timer in net.py to trigger re-sync time
    try:
        ntptime.settime()
        state.time_set = True
        log.inf("time set")
    except:
        state.time_set = False
        log.err("set time failed")


def connect_to_network(ctx):         
    # Wifi
    try:
        iface = ctx.wifi_if
        ssid_visible = False
        iface.active(True)
        # Check if the supplied ssid is visible
        ssid_list = iface.scan()
        for x in ssid_list:
            if ctx.wifi_ssid in str(x):
                ssid_visible = True
                break
        if (ssid_visible):
            if (connect_to_wifi(ctx)):
                log.inf("wifi connected")
                set_time() # TODO set timer in net.py to trigger re-sync time
                return 0
            else:
                log.err("connect to wifi ssid failed")
        else:
            log.err("find wifi ssid failed")
    except:
        log.err("connect wifi failed")
    # TODO LTE


def net_loop(ctx):
    while(True):
        if (not ctx.wifi_if.isconnected() or not state.net_connected): # and not ctx.lte_if.isconnected()):
            if (connect_to_network(ctx) == 0):
                state.net_connected = True
            else:
                state.net_connected = False
        time.sleep(NET_LOOP_POLL_INTERVAL_SEC)