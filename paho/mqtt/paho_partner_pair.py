import sys

from broker.messages import BaseMQTTMessage

try:
    from paho.mqtt.extended_client import Extended_Client
except ImportError:
    # This part is only required to run the example from within the examples
    # directory when the module itself is not installed.
    #
    # If you have the module installed, just use "import paho.mqtt.client"
    import os
    import inspect

    cmd_subfolder = os.path.realpath(
            os.path.abspath(os.path.join(os.path.split(inspect.getfile(inspect.currentframe()))[0], "../src")))
    if cmd_subfolder not in sys.path:
        sys.path.insert(0, cmd_subfolder)
    from paho.mqtt.extended_client import Extended_Client


# functions for verbosity

def on_connect(mqttc, userdata, flags, rc):
    print("(" + userdata + ") " + "rc: " + str(rc))


def on_message(mqttc, userdata, msg):
    print("(" + userdata + ") " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))


def on_publish(mqttc, userdata, mid):
    print("(" + userdata + ") " + "mid: " + str(mid))


def on_subscribe(mqttc, userdata, mid, granted_qos):
    print("(" + userdata + ") " + "Subscribed: " + str(mid) + " " + str(granted_qos))


def on_log(mqttc, userdata, level, string):
    print("(" + userdata + ") " + string)


class Paho_Partner_Pair():
    def __init__(self):
        print("Paho_Partner_Pair.__init__")

        # internal paho instance (via loop interface to localhost)
        self.internal_client = Extended_Client(partner_pair=self, client_id="uplink", userdata="paho: uplink")
        self.internal_client.on_message = on_message
        self.internal_client.on_connect = on_connect
        self.internal_client.on_publish = on_publish
        self.internal_client.on_subscribe = on_subscribe

        # external instance connecting to another broker.
        # This other broker might assume that this is just another normal client.
        self.external_client = Extended_Client(partner_pair=self, client_id="broker_random4", userdata="paho: facing away")
        self.internal_client.on_message = on_message
        self.internal_client.on_connect = on_connect
        self.internal_client.on_publish = on_publish
        self.internal_client.on_subscribe = on_subscribe

    def connect(self, internal_port, external_address, external_port):
        internal_address = "localhost"
        self.internal_client.connect(internal_address, internal_port)
        self.internal_client.loop_start()  # starts a Thread

        self.external_client.connect(external_address, external_port)
        self.external_client.loop_start()  # starts a Thread

    def pass_packet_to_partner(self, binary_packet: bytes, origin_id):
        if origin_id == self.external_client._client_id:
            self.internal_client.enqueue_packet(binary_packet)
        elif origin_id == self.internal_client._client_id:
            self.external_client.enqueue_packet(binary_packet)

    def get_partner(self, my_id):
        if my_id == self.external_client._client_id:
            return self.internal_client
        elif my_id == self.internal_client._client_id:
            return self.external_client
