from broker import MQTTConstants
from broker.messages import Pingresp, Puback, Suback, Unsuback, Pubrel, Pubrec, Pubcomp


class Action():
    def __init__(self, msg):
        self.msg = msg
        self._client = None
        """:type : broker.client.MQTTClient | None"""

    @property
    def qos(self):
        return self.msg.qos

    @property
    def logger(self):
        if self._client is None:
            return None

        return self._client.logger

    def bind_client(self, client):
        self._client = client

    def write_to_client(self, msg):
        self._client.send_packet(msg)


class IncomingAction(Action):
    def run(self):
        """
        Overwrite to implement packet specific actions.
        Is called after a packet is received
        """
        pass


class IncomingPublish(IncomingAction):
    def run(self):
        print("PUBLISH FROM {}: {} {} {}".format(self._client.uid, self.msg.topic, self.msg.payload, self.msg.qos))
        is_dup = False
        if self.qos is MQTTConstants.EXACTLY_ONCE:
            if self.msg.id in self._client.incoming_packet_ids:
                is_dup = True
            else:
                self._client.incoming_packet_ids.add(self.msg.id)

        if not is_dup:
            self._client.dispatch_to_server(self.msg)

        if self.qos == MQTTConstants.AT_LEAST_ONCE:
            self.write_to_client(Puback.from_publish(self.msg))

        elif self.qos is MQTTConstants.EXACTLY_ONCE:
            self.write_to_client(Pubrec.from_publish(self.msg))

from broker.messages import Subscribe
class IncomingSubscribe(IncomingAction):
    def run(self):
        granted_qos = []
        for topic, qos in self.msg.subscription_intents:
            granted = self._client.subscribe(topic, qos)
            # client.subscribe() returns 0x80 on error
            # but 0x80 is the value to send inside a SUBACK packet to indicate rejection
            granted_qos.append(granted)

        m = Suback.from_subscribe(self.msg, granted_qos)
        self.write_to_client(m)

class IncomingDisconnect(IncomingAction):
    def run(self):
        self._client.disconnect()


class IncomingPingreq(IncomingAction):
    def run(self):
        response = Pingresp.from_pingreq(self.msg)
        self.write_to_client(response)


class IncomingUnsubscribe(IncomingAction):
    def run(self):
        self._client.unsubscribe(self.msg.unsubscribe_list)
        self.write_to_client(Unsuback.from_unsubscribe(self.msg))


class IncomingPuback(IncomingAction):
    def run(self):
        self._client.outgoing_queue.flow_completed(self.msg.id)


class IncomingPubrec(IncomingAction):
    def run(self):
        self._client.outgoing_queue.set_pubconf(self.msg.id)
        self.write_to_client(Pubrel.from_pub(self.msg))


class IncomingPubrel(IncomingAction):
    def run(self):
        if self.msg.id in self._client.incoming_packet_ids:
            self._client.incoming_packet_ids.remove(self.msg.id)

        self.write_to_client(Pubcomp.from_pubrel(self.msg))


class IncomingPubcomp(IncomingAction):
    def run(self):
        self._client.outgoing_queue.flow_completed(self.msg.id)


class OutgoingAction(Action):
    def get_data(self):
        """
        Is called to get the packet (`BaseMQTTMessage`) to write on the
        connection.
        """
        return self.msg

    def post_write(self):
        """
        Is called after the bytearray provided by `get_data` is written
        """
        pass


class OutgoingPublish(OutgoingAction):
    def get_data(self):

        print("PUBLISH TO {} {} {} ".format(self._client.uid, self.msg.topic, self.msg.payload))
        if self.qos > MQTTConstants.AT_MOST_ONCE:
            self.msg.dup = self._client.outgoing_queue.is_sent(self.msg.id)
            #print("PUBLISH TO {} {} {} DUPLICATE: {}".format(self._client.uid, self.msg.topic, self.msg.payload,
            #                                              self.msg.dup))

        if self.qos == MQTTConstants.EXACTLY_ONCE:
            if self._client.outgoing_queue.is_pubconf(self.msg.id):
                return Pubrel.from_pub(self.msg)  # potentially misleading
            else:
                return self.msg
        else:
            return self.msg

    def post_write(self):
        if self.msg.qos == MQTTConstants.AT_MOST_ONCE:
            self._client.outgoing_queue.flow_completed(self.msg.id)
        else:
            self.msg.dup = True
            self._client.outgoing_queue.set_sent(self.msg.id)

            deadline = self._client.redelivery_deadline
            self._client.outgoing_queue.set_retrial(self.msg.id, deadline)


class OutgoingPubrel(OutgoingAction):
    def post_write(self):
        deadline = self._client.redelivery_deadline
        self._client.outgoing_queue.set_retrial(self.msg.id, deadline)
