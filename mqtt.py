import time
from umqtt.simple import MQTTClient
import mrequests.mrequests as mrequests
import gc
import machine
from machine import Timer

import state
import secrets
import logging as log

MQTT_LOOP_POLL_INTERVAL_SEC = 8
MQTT_CONN_MAX_WAIT_SEC = 30
MQTT_DISCONN_WAIT_MSEC = 60000*5 # Give the MQTT some time to send pending messages back to gateway

mqtt_disconnect_timer = Timer(3)


class MqttConfig:
    client_id = ""
    server = ""
    port = 8883
    keepalive = 0
    ssl = True
    ssl_params = {}     


def mqtt_disconnect_timer_cb(mqtt_disconnect_timer):
    state.mqtt_enabled = False
    

def publish(topic, data):
    state.mqtt_enabled = True
    if (state.net_connected):
        seconds_waited = 0
        while(not state.mqtt_connected and seconds_waited < MQTT_CONN_MAX_WAIT_SEC):
            time.sleep(1)
            seconds_waited += 1
        if (state.mqtt_connected):
            # subscribe if not already
            if (not state.mqtt_subscribed):
                try:
                    # subscribe to sub_topic
                    state.mqtt_client.subscribe(
                        topic=f"{secrets.TENANT_NAME}/{secrets.GATEWAY_ID}/#",
                        qos=state.mqtt_sub_qos
                    )
                    log.inf("mqtt subscribed to topic")
                    state.mqtt_subscribed = True
                except:
                    log.err("mqtt subscribe failed")

            try:
                state.mqtt_client.publish( 
                    topic = topic, 
                    msg = data, 
                    qos = state.mqtt_pub_qos
                )
                log.inf("mqtt publish succeeded, len = " + str(len(data)))
                mqtt_disconnect_timer.init(mode=Timer.ONE_SHOT, period=MQTT_DISCONN_WAIT_MSEC, callback=mqtt_disconnect_timer_cb)
            except:
                #reset_mqtt_state()
                log.err("mqtt publish failed")
        else:
            log.err("mqtt publish failed - mqtt not connected")
    else:
        log.err("mqtt publish failed - wifi not connected")
        # TODO handle this case"
    return


def sub_cb(topic, msg): 
    log.inf("GOT MESSAGE:")
    topic = topic.decode("utf-8") 
    print(topic)
    state.mqtt_recv_topics += [topic]
    state.mqtt_recv_msgs += [msg]
    # NOTE if receiving large payloads, make sure the mqtt_disconnect_timer is handled appropriately


def reset_mqtt_state():
    try:
        state.mqtt_client.disconnect()
    except:
        pass
    state.mqtt_connected = False
    state.mqtt_subscribed = False


def poll_mqtt():    
    # Poll server for messages
    if (state.mqtt_connected):
        try:            
            state.mqtt_client.check_msg()
        except:
            reset_mqtt_state()
            log.err("mqtt poll failed")


def mqtt_loop(ctx):

    state.mqtt_client = MQTTClient(
        client_id=ctx.client_id, 
        server=ctx.server, 
        port=ctx.port, 
        keepalive = ctx.keepalive, 
        ssl=ctx.ssl,
        ssl_params = ctx.ssl_params
    )
    state.mqtt_client.set_callback(sub_cb)

    state.mqtt_connected = False
    state.mqtt_subscribed = False

    # Have to initialize the timer here or it won't work correctly later
    mqtt_disconnect_timer.init(mode=Timer.ONE_SHOT, period=1, \
        callback=lambda t:log.inf("mqtt_disconnect_timer ready"))

    while(True):
        if (state.mqtt_enabled):
            # Connect to MQTT Broker and subscribe to topics
            if (state.net_connected and not state.mqtt_connected):
                try:
                    state.mqtt_client.connect()
                    log.inf("mqtt connected")
                    state.mqtt_connected = True
                except:
                    log.err("mqtt connect failed")
                    reset_mqtt_state()
                    machine.reset() # TODO only call this after certain number of failed attempts
        else:
            if (state.mqtt_connected):
                reset_mqtt_state() # Disconnect MQTT
                log.inf("mqtt disconnected")
        time.sleep(MQTT_LOOP_POLL_INTERVAL_SEC)
        