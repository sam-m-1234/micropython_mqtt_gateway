
import time
import machine
import gc

import state
import secrets
import utils
from mqtt import publish, poll_mqtt
from net import set_time
from mrequests.mrequests import get

import logging as log


ACK_STR = "OK"
NACK_STR = "ERROR"
BUSY_STR = "BUSY"

MAX_NUM_ACTIVE_SESSIONS = 1
NRF_UART_RX_LOOP_WAIT_SEC = 0.1
NRF_UART_RX_LOOP_TIMEOUT_SEC = 60
MAX_MQTT_SUB_MSG_WAIT_SEC = 30


class Header:
    def __init__(self):
        self.gateway_ts = ""
        self.sensor_ts = ""
        self.topic = ""
        self.body_len = 0
        self.sensor_id = ""
        self.schema_ver_str = ""
        self.headers_len_str = ""
        self.fw_ver_str = ""
        self.params_ver_str = ""
        self.tenant_id_str = ""


class GatewayContext:
    dev = None
    num_active_sessions = 0
    active_session_id = 0
    data = b''
    datalen = 0
    session_len = 0
    payload_len = 0
    session_start_time = 0
    session_finish_time = 0
    header = Header()
    body = b''


def read_bytestream(ctx, expected_len):
    dev = ctx.dev
    all_bytes = b''
    len_recv = 0
    seconds_rem = NRF_UART_RX_LOOP_TIMEOUT_SEC
    while(len_recv < expected_len and seconds_rem > 0):
        if dev.any():
            data = dev.read()
            all_bytes += data
            len_recv  += len(data)
        else:
            time.sleep(NRF_UART_RX_LOOP_WAIT_SEC)
            seconds_rem -= NRF_UART_RX_LOOP_WAIT_SEC
    ctx.payload_len += len_recv
    ctx.session_len += len_recv
    return all_bytes


def parse_body(ctx):
    dev = ctx.dev
    expected_len = ctx.header.body_len
    bytes_read = b''
    try:
        bytes_read = read_bytestream(ctx, expected_len)
    except:
        log.err("parse body failed")
        ctx.dev.write(NACK_STR)
        return -1
    ctx.body += bytes_read
    return 0


def parse_header(ctx):
    dev = ctx.dev
    data = ctx.data

    if (state.net_connected):
        if (not state.time_set):
            set_time() # TODO periodically trigger time re-sync in net.py
        dt = machine.RTC().datetime()
        dt = utils.datetime_to_compressed_str(dt)
    else:
        dt = "USE_SERVER_TIME"

    try:
        data = data.decode("utf-8")
        data = data.split(',')
        ctx.header.gateway_ts = dt
        
        ctx.header.topic = data[0]
        ctx.header.body_len = int(data[1])
        ctx.header.sensor_id = data[2]
        ctx.header.sensor_ts = data[3]
        ctx.header.headers_len_str = data[4]
        ctx.header.schema_ver_str = data[5]
        ctx.header.fw_ver_str = data[6]
        ctx.header.params_ver_str = data[7]
        ctx.header.tenant_id_str = data[8]
        if (ctx.header.tenant_id_str != secrets.TENANT_NAME):
            log.err("wrong tenant: " + ctx.header.tenant_id_str)
            ctx.dev.write(NACK_STR)
            return -1
        ctx.dev.write(ACK_STR)
        return 0
    except:
       log.err("parse header failed: " + str(data))
       ctx.dev.write(NACK_STR)
       return -1


def reset_session(ctx):
    ctx.active_session_id = 0
    ctx.data = b''
    ctx.session_len = 0
    ctx.payload_len = 0
    ctx.header = Header()
    ctx.body = b''
    ctx.num_active_sessions -= 1
    gc.collect()
    gc.mem_free()


def handle_post(ctx):
    dev = ctx.dev
    ctx.session_start_time = time.ticks_ms()
    if (ctx.num_active_sessions <= MAX_NUM_ACTIVE_SESSIONS):
        ctx.num_active_sessions += 1
        ctx.session_start_time = time.ticks_ms()
        log.inf("bt post start")
    else:
        ctx.dev.write(BUSY_STR)
        return -1

    if (parse_header(ctx) == 0):
        ctx.body += str.encode(ctx.header.schema_ver_str) + b','
        ctx.body += str.encode(ctx.header.gateway_ts) + b','
        ctx.body += str.encode(ctx.header.sensor_ts) + b','
        ctx.body += str.encode(ctx.header.headers_len_str)
        if (ctx.header.fw_ver_str == ""):
            ctx.body += b';'
        else:
            log.inf("sub requested")
            ctx.body += b','
            ctx.body += str.encode(ctx.header.fw_ver_str) + b','
            ctx.body += str.encode(ctx.header.params_ver_str) + b';'
        parse_body(ctx)
    else:
        return -2
    ctx.session_finish_time = time.ticks_ms()
    elapsed_time_ms = ctx.session_finish_time - ctx.session_start_time
    elapsed_time_sec = elapsed_time_ms/1000
    bytes_per_sec_session = ctx.session_len / elapsed_time_sec
    bytes_per_sec_payload = ctx.payload_len / elapsed_time_sec
    log.inf("bt post finshed " + str(ctx.session_len) + ", " \
         + str(ctx.payload_len) + ", " + str(elapsed_time_sec) + ", " \
             + str(bytes_per_sec_session) + ", " + str(bytes_per_sec_payload))
    print(ctx.body[0:128])
    
    # assemble the pub_topic
    #pub_topic = secrets.MQTT_PUB_TOPIC_BASE + f'{ctx.header.topic}/{ctx.header.tenant_id_str}/{state.gateway_id}/{ctx.header.sensor_id}'
    pub_topic = secrets.MQTT_PUB_TOPIC_BASE + f'{secrets.TENANT_NAME}/{secrets.GATEWAY_ID}/{ctx.header.sensor_id}'
    log.inf("pub_topic = " + pub_topic)
    
    publish(pub_topic, ctx.body)
    reset_session(ctx)
    dev.write(ACK_STR)


def handle_get(ctx):
    dev = ctx.dev
    data = ctx.data
    data = data.decode("utf-8")
    data = data.split(',')
    topic = data[0]
    sensor_id = data[1]
    current_ver = data[2]

    msg_len = 0
    msg = b''
    topic_to_check = f'{secrets.TENANT_NAME}/{secrets.GATEWAY_ID}/{sensor_id}/{topic}'

    poll_mqtt()
    if topic_to_check in state.mqtt_recv_topics:
        log.inf(f"got messages waiting on topic: {topic_to_check}")
        idx = state.mqtt_recv_topics.index(topic_to_check)
        msg = state.mqtt_recv_msgs[idx]
        msg_len = len(msg)

        # remove the item from state.mqtt_recv_msgs and state.mqtt_recv_topics
        del state.mqtt_recv_msgs[idx]
        del state.mqtt_recv_topics[idx]

        if (topic == "fw" and msg_len > 0):
            url = msg.decode("utf-8") 
            log.inf(f"got fw url: {url}")
            ## download file from url
            r = get(url, headers={b"accept": b"application/octet-stream"})
            log.inf(f"status code = {r.status_code}")
            # # get length
            chunk = b''
            msg = b'' # msg will now contain the firmware binary data itself
            if (r.status_code == 200):
                while(True):
                    chunk = r.read()
                    msg += chunk
                    print(f"chunk len: {len(chunk)}, msg_len: {len(msg)}")
                    if len(chunk) < 4096:
                        msg_len = len(msg)
                        break
    else:
        msg_len = -1

    # let the client know if there are messages waiting
    ctx.dev.write("OK," + str(msg_len))
    # TODO need to handle timeout here, and clean up memory on failure
    if msg_len > 0: # send the message to the client, chunk by chunk
        # wait for client to request bytes by sending through int value:
        seconds_rem = NRF_UART_RX_LOOP_TIMEOUT_SEC
        start_idx = 0
        end_idx = 0
        while(seconds_rem > 0 and start_idx < msg_len):
            if dev.any():
                data = dev.read()
                print(data)
                #try:
                try:
                    chunk_size = int(data)
                except:
                    return -1
                end_idx = start_idx + chunk_size
                ctx.dev.write(msg[start_idx:end_idx])
                start_idx = end_idx
                seconds_rem = NRF_UART_RX_LOOP_TIMEOUT_SEC
                #except:
                #    ctx.dev.write(NACK_STR)
                #    return -1
            else:
                #time.sleep(NRF_UART_RX_LOOP_WAIT_SEC)
                time.sleep(0.01)
                seconds_rem -= NRF_UART_RX_LOOP_WAIT_SEC
    reset_session(ctx)
    return 0


def is_type(type_bytes, ctx):
    type_bytes_len = len(type_bytes)
    if (ctx.datalen < type_bytes_len):
        return False
    if (ctx.data[:type_bytes_len] == type_bytes):
        ctx.data = ctx.data[type_bytes_len:]
        ctx.datalen -= type_bytes_len
        return True
    return False


def gateway_loop(ctx):
    dev = ctx.dev
    while(True):
        if dev.any():
            ctx.data = dev.read()
            ctx.datalen = len(ctx.data)
            ctx.session_len += ctx.datalen
            print(ctx.data)
            if (is_type(b'POST-', ctx)):
                handle_post(ctx)
            elif (is_type(b'GET-', ctx)):
                handle_get(ctx)
            elif (is_type(b'CANCEL', ctx)):
                reset_session(ctx)
            else: # TODO handle errors + more commands here
                log.wrn("Unsupported command: " + str(ctx.data))
        else:
            time.sleep(NRF_UART_RX_LOOP_WAIT_SEC)