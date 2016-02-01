import paho.mqtt.client as mqtt
# Message types
from broker.factory import MQTTMessageFactory
from broker.util import MQTTUtils

CONNECT = 0x10
CONNACK = 0x20
PUBLISH = 0x30
PUBACK = 0x40
PUBREC = 0x50
PUBREL = 0x60
PUBCOMP = 0x70
SUBSCRIBE = 0x80
SUBACK = 0x90
UNSUBSCRIBE = 0xA0
UNSUBACK = 0xB0
PINGREQ = 0xC0
PINGRESP = 0xD0
DISCONNECT = 0xE0

# Log levels
MQTT_LOG_INFO = 0x01
MQTT_LOG_NOTICE = 0x02
MQTT_LOG_WARNING = 0x04
MQTT_LOG_ERR = 0x08
MQTT_LOG_DEBUG = 0x10

# Error values
MQTT_ERR_SUCCESS = 0
MQTT_ERR_PROTOCOL = 2

import sys

class Extended_Client(mqtt.Client):
    def __init__(self, partner_pair, client_id="", clean_session=True, userdata=None):#, protocol=MQTTv31):
        super().__init__(client_id, clean_session, userdata)#, protocol)
        self.local_interface = partner_pair


    def get_uid(self):
        return self._client_id

    def enqueue_packet(self, binary_packet : bytes):
        print("enqueueing binary packet")
        print(binary_packet)
        # decode
        # FIXME import Errors with Message Factory

        try:
            print(type(binary_packet))
            obj = MQTTMessageFactory.make(binary_packet)
        except:
            e = sys.exc_info()[0]
            print(e)

        print("foo")
        print("enqueueing from %s . try forward" % obj.__class__)
        cmd = obj.type << 4
        mid = obj.id
        qos = obj.qos
        """
        cmd = None
        mid = None
        qos = None
        """

        # put on wire
        self._packet_queue(cmd, binary_packet, mid, qos)
        pass

    # _packet_handle function überschreiben
    def _packet_handle(self):
        cmd = self._in_packet['command']&0xF0
        if cmd == PINGREQ:
            return self._handle_pingreq()
        elif cmd == PINGRESP:
            return self._handle_pingresp()
        elif cmd == PUBACK:
            return self._handle_pubackcomp("PUBACK")
        elif cmd == PUBCOMP:
            return self._handle_pubackcomp("PUBCOMP")
        elif cmd == PUBLISH:
            # send puback and so on
            self._handle_publish()
            # forward
            return self._forward_to_partner()
        elif cmd == PUBREC:
            return self._handle_pubrec()
        elif cmd == PUBREL:
            return self._handle_pubrel()
        elif cmd == CONNACK:
            return self._handle_connack()
        elif cmd == SUBACK:
            return self._handle_suback()
        elif cmd == UNSUBACK:
            return self._handle_unsuback()
        elif cmd == SUBSCRIBE:
            return self._handle_subscribe()
        elif cmd == UNSUBSCRIBE:
            return self._handle_unsubscribe()
        else:
            # If we don't recognise the command, return an error straight away.
            self._easy_log(MQTT_LOG_ERR, "Error: Unrecognised command "+str(cmd))
            return MQTT_ERR_PROTOCOL

    def _handle_subscribe(self):
        # TODO decode packet and send SUBACK
        return self._forward_to_partner()

    def _handle_unsubscribe(self):
        # TODO decode packet and send UNSUBACK
        return self._forward_to_partner()

    def _forward_to_partner(self):
        print("ppp: forwarding packet to partner")
        # paho has cut of some bytes. We are missing 'command' and 'remaining_length':
        # TODO append and concatenate it again.
        b_command = self._in_packet['command_byte'] #b''#MQTTUtils.encode_value(self._in_packet['command'])
        b_length = MQTTUtils.encode_length(self._in_packet['remaining_length'])
        b_rest_of_packet = self._in_packet["packet"]

        b_concat = b_command + b_length + b_rest_of_packet
        print("forwarded content is of type: %s" % (b_concat.__class__))
        print("forwarded content is: %s" % (b_concat))

        self.local_interface.pass_packet_to_partner(b_concat, self._client_id)
        return MQTT_ERR_SUCCESS