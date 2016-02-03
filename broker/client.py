from collections import deque
from contextlib import ContextDecorator
from datetime import timedelta
import re
from logging import getLogger

from tornado import gen
from tornado import ioloop
from tornado.concurrent import Future
from tornado.iostream import StreamClosedError
from toro import Event
import toro

from broker.access_control import Authorization
from broker.actions import IncomingAction, OutgoingAction
from broker.concurency import CancelledException, DummyFuture

from broker.persistence import InMemoryClientPersistence, OutgoingPublishesBase, PacketIdsDepletedError
from broker.util import MQTTUtils
from broker.factory import MQTTMessageFactory, MQTTMessageMakeError, IncomingActionFactory, TypeFactoryError, \
    OutgoingActionFactory

from broker.messages import Publish, BaseMQTTMessage
from broker.connection import MQTTConnection, MQTTConnectionClosed


class MQTTClient():
    """
    Objects of this class encapsulate and abstract all aspects of a given
    client. A MQTTClient object may refer to a live, connected, client or a
    known client which albeit disconnected had the clean_sessions flag set to
    false and, thus, is kept by the server as an end point for routed messages.

    One may call :meth:`self.is_connected` to check whether is there a connected
    client or not.

    :param MQTTServer server: The server which the client is bound to;
    :param MQTTConnection connection: The connection to be used;
    :param str uid: A string used as the client's id;
    :param bool clean_session: The clean session flag, as per MQTT Protocol;
    :param int keep_alive: The keep alive interval, in seconds.
    :param ClientPersistenceBase persistence: An object that provides persistence
    """

    broker_re = re.compile(r'^(broker|uplink)', re.IGNORECASE) # matched against 'uid'

    def __init__(self, server, connection, authorization=None,
                 uid=None, clean_session=False,
                 keep_alive=60, persistence=None):

        self.uid = uid
        self.logger = getLogger('activity.clients')
        self.persistence = persistence or InMemoryClientPersistence(uid)

        self.subscriptions = ClientSubscriptions(persistence.subscriptions)

        self._connected = Event()

        self.last_will = None
        self.connection = None
        self.clean_session = None
        self.keep_alive = None
        self.receive_subscriptions = False

        self.server = server
        self.authorization = authorization or Authorization.no_restrictions()

        # Queue of the packets ready to be delivered
        self.outgoing_queue = OutgoingQueue(self.persistence.outgoing_publishes)

        self.update_configuration(clean_session, keep_alive)
        self.update_connection(connection)

    @property
    def incoming_packet_ids(self):
        return self.persistence.incoming_packet_ids

    @property
    def redelivery_deadline(self):
        s = self.keep_alive if self.keep_alive > 0 else 60
        return timedelta(seconds=s)

    def is_broker(self):
        """boolean whether this client claims to be a broker"""
        return not not MQTTClient.broker_re.match(self.uid)

    def update_connection(self, connection):
        """
        Updates the client's connection by disconnecting the previous one and
        configuring the new one's keep alive time according to ``keep_alive``.

        :param MQTTConnection connection: The new connection to be used;
        """
        if self.is_connected():
            self.disconnect()

        if connection is not None:
            assert isinstance(connection, MQTTConnection)

            self.connection = connection
            self.connection.set_timeout(self.keep_alive)
            self.connection.set_close_callback(self._on_stream_close)
            self.connection.set_timeout_callback(self._on_connection_timeout)

            if not self.connection.closed():
                self._connected.set()

    def update_configuration(self, clean_session=False, keep_alive=60):#, receive_subscriptions=None):
        """
        Updates the internal attributes.

        :param bool clean_session: A flag indicating whether this session should
          be brand new or attempt to reuse the last known session for a client
          with the same :attr:`self.uid` as this.
        :param int keep_alive: Connection's keep alive setting, in seconds.
        """
        self.clean_session = clean_session
        self.keep_alive = keep_alive
        #if receive_subscriptions is not None:
        #    self.receive_subscriptions = receive_subscriptions

    def update_authorization(self, authorization):
        self.authorization = authorization

        if not self.clean_session:
            self.unsubscribe_denied_topics()

    def start(self):
        """
        Starts the client fetching, processing and dispatching routines. Should
        be called after object instantiation or a :meth:`self.update_connection`
        call.

        The following coroutines are started:

          * :meth:`self._process_incoming_messages`
          * :meth:`self._process_outgoing_messages`
        """
        self.logger.debug("[uid: %s] starting co-routines" % self.uid)
        # put connection object in `_process_incoming_messages` scope
        # so corner cases can be handled appropriately
        self._process_incoming_packets(self.connection)
        self._process_outgoing_packets(self.connection)

    @property
    def connected(self):
        """
        An :class:`toro.Event` instance that is set whenever the client is
        connected and clear on disconnection. It's safe to wait on this property
        before stream related operations.
        """
        return self._connected

    def is_connected(self):
        """
        A shorthand for :meth:connected.is_set().
        """
        return self._connected.is_set()

    def configure_last_will(self,  topic, payload, qos, retain=False):
        """
        Configures a message to be send as the client's last will. This message
        will be send when the connected is disconnected by a connection timeout,
        protocol error or an unexpected disconnection.

        :param str topic: The topic which the message will be delivered;
        :param bytes payload: Message payload;
        :param bool retain: Message's retain flag.

        """
        if topic is not None and payload is not None and qos is not None:
            self.last_will = Publish(qos=qos, dup=False, retain=retain)
            self.last_will.topic = topic
            self.last_will.payload = payload

    def handle_last_will(self):
        """
        Checks if a client has a pending last will message and dispatches it for
        server processing.
        """
        if self.last_will is not None:
            self.dispatch_to_server(self.last_will)
            self.logger.debug("[uid: %s] Dispatched last will message %s" %
                              (self.uid, self.last_will.log_info()))

    def _get_action(self, msg, factory):
        try:
            action = factory.make(msg)
            action.bind_client(self)
            return action

        except KeyError:
            self.logger.exception("[uid: %s] Wrong message type %s" %
                                  (self.uid, type(msg)))

            self.logger.debug(
                "[uid: %s] Will be disconnect due to invalid message" %
                self.uid
            )

            self.disconnect()

    @gen.coroutine
    def _process_incoming_packets(self, connection):
        """
        This coroutinte fetches the message raw data from
        :attr:`self.incoming_queue`, parses it into the corresponding message
        object (an instance of one of the
        :class:`broker.messages.BaseMQTTMessage` subclasses) and passes it to
        the :attr:`self.incoming_transaction_manager` to be processed.

        It is started by calling :meth:`self.start()` and stops upon client
        disconnection.
        """
        while connection.is_readable:
            with client_process_context(self, connection):
                msg = yield connection.read_message()

                msg_obj = MQTTMessageFactory.make(msg)
                self.logger.debug("[B << C] [uid: %s] %s" %
                                  (self.uid, msg_obj.log_info()))

                action = self._get_action(msg_obj, IncomingActionFactory)
                assert isinstance(action, IncomingAction)
                action.run()

        self.logger.debug("[uid: %s] stopping _process_incoming_messages"
                          % self.uid)

    @gen.coroutine
    def _process_outgoing_packets(self, connection):
        """
        This coroutinte fetches the message raw data from
        :attr:`self.outgoing_queue`, parses it into the corresponding message
        object (an instance of one of the
        :class:`broker.messages.BaseMQTTMessage` subclasses) and passes
        it to the :attr:`self.outgoing_transaction_manager` to be processed.

        It is started by calling :meth:`self.start()` and stops upon client
        disconnection.
        """
        self.outgoing_queue.clear()
        self.outgoing_queue.retry_pending()

        while not connection.closed():
            with client_process_context(self, connection):
                msg = yield self.outgoing_queue.get()
                assert isinstance(msg, BaseMQTTMessage)

                action = self._get_action(msg, OutgoingActionFactory)
                assert isinstance(action, OutgoingAction)

                self.logger.debug("[B >> C] [uid: %s] %s" %
                                  (self.uid, msg.log_info()))
                yield self.write(action.get_data())

                action.post_write()

        self.logger.debug("[uid: %s] stopping _process_outgoing_messages" % self.uid)

    def publish(self, msg):
        """
        Puts a publish packet on the :attr:`self.outgoing_queue` to be sent
        to the client.

        :param msg: The message to be set or a iterable of its bytes.
        :type msg: Publish
        """
        try:
            self.outgoing_queue.put_publish(msg)
            self.logger.error('[uid: %s] Send publish packet to Subscriber with topic %s' % (self.uid, msg.topic))
        except PacketIdsDepletedError:
            self.logger.error('[uid: %s] Packet IDs depleted' % self.uid)

    def send_packet(self, packet):
        """
        Puts a packet on the :attr:`self.outgoing_queue` to be sent to the
        client.
        """
        self.outgoing_queue.put(packet)

    @gen.coroutine
    def write(self, msg):
        """
        Writes a MQTT Message to the client. If the client isn't connected,
        waits for the :attr:`self.connected` event to be set.

        :param MQTT Message msg: The message to be send. It must be a instance
          of :class:`broker.messages.BaseMQTTMessage` or it's subclasses.
        """
        yield self.connected.wait()
        yield self.connection.write_message(msg)

    def dispatch_to_server(self, pub_msg):
        """
        Dispatches a Publish message to the server for further processing, ie.
        delivering it to the appropriate subscribers.

        :param Publish pub_msg: A :class:`broker.messages.Publish` instance.
        """
        assert isinstance(pub_msg, Publish)

        if self.authorization.is_publish_allowed(pub_msg.topic):
            self.server.handle_incoming_publish(pub_msg, self.uid)
        else:
            self.logger.warn("[uid: %s] is not allowed to publish on %s" %
                             (self.uid, pub_msg.topic))

    def subscribe(self, subscription_mask, qos):
        """
        Subscribes the client to a topic or wildcarded mask at the informed QoS
        level. Calling this method also signalizes the server to enqueue the
        matching retained messages.

        When called for a (`subscripition_mask`, `qos`) pair for which the
        client has already a subscription it will silently ignore the command
        and return a suback.

        :param string subscription_mask: A MQTT valid topic or wildcarded mask;
        :param int qos: A valid QoS level (0, 1 or 2).
        :rtype: int
        :return: The granted QoS level (0, 1 or 2) or 0x80 for failed
          subscriptions.
        """
        if qos not in [0, 1, 2]:
            self.logger.warn('client tried to subscribe with invalid qos %s' % qos)
            return 0x80

        new_subscription = subscription_mask not in self.subscriptions or \
            self.subscriptions.qos(subscription_mask) != qos

        if not self.authorization.is_subscription_allowed(subscription_mask):
            self.logger.warn("[uid: %s] is not allowed to subscribe on %s" %
                             (self.uid, subscription_mask))
            del self.subscriptions[subscription_mask]
            qos = 0x80

        elif new_subscription:
            ereg = MQTTUtils.convert_to_ereg(subscription_mask)
            if ereg is not None:
                self.subscriptions.add(subscription_mask, qos, re.compile(ereg))
                self.server.enqueue_retained_message(self, subscription_mask)
                self.server.forward_subscription(subscription_mask, qos, sender_uid=self.uid)
            else:
                qos = 0x80
        if "#" in subscription_mask:
            print("SUBSCRIBING TO: {}".format(subscription_mask))
        return qos

    def unsubscribe(self, topics):
        """
        Unsubscribes the client from each topic in ``topics``. Safely
        ignores topics which the client is not subscribed to.

        :param iterable topics: An iterable of MQTT valid topic strings.
        """
        for topic in topics:
            del self.subscriptions[topic]

    def unsubscribe_denied_topics(self):
        for topic in self.subscriptions.masks:
            if not self.authorization.is_subscription_allowed(topic):
                self.unsubscribe(topic)

    def disconnect(self):
        """
        Closes the socket and disconnects the client. If
        :attr:`self.clean_session` is set, ensures that the incoming and
        outgoing queues are cleared and calls the server client removing
        routine.

        .. hint::
           It's safe to call this function without checking whether the
           connection is open or not.
        """
        if self.is_connected():
            self.logger.debug("[uid: %s] disconnecting client" % self.uid)
            self.connection.close()
            self._connected.clear()

        self.outgoing_queue.clear()

        if self.clean_session:
            self.logger.debug("[uid: %s] cleaning session" % self.uid)
            self.server.remove_client(self)

    def get_list_of_delivery_qos(self, msg):
        """
        Matches the ``msg.topic`` against all the current subscriptions and
        returns a list containing the QoS level for each matched subscription.

        :param Publish msg: A MQTT valid message.
        :rtype: tuple
        :return: A list of QoS levels, ie [0, 0, 1, 2, 0, 2]
        """
        # TODO CACHING THESE RESULTS PER CLIENT
        qos_list = []
        for mask in self.subscriptions.masks:
            qos = self.get_matching_qos(msg, mask)

            if qos is not None:
                qos_list.append(qos)

        return qos_list

    def get_matching_qos(self, msg, subscriptions_mask):
        """
        Matches the ``msg.topic`` against a single subscription defined by the
        subscription mask and returns the QoS level on which the message should
        be delivered.

        :param Publish msg: Message to be analysed;
        :param subscriptions_mask: A subscription mask that identifies one of
          the client's subscriptions.
        :return: QoS Level or None, in case it doesn't match.
        """
        assert isinstance(msg, Publish)

        qos, pattern = self.subscriptions[subscriptions_mask]

        if pattern.match(msg.topic) is not None:
            self.logger.debug("[uid: %s] %s matched by %s, MAXQOS: %d"
                              % (self.uid, msg.topic, subscriptions_mask, qos))

            return min(qos, msg.qos)

        return None

    def _on_connection_timeout(self, connection):
        """
        Callback called when the connection times out. Ensures clearing the
        :attr:`self.connected` event and processing the :meth:`self.disconnect`
        method.
        """
        self.logger.debug("[uid: %s] Connection timeout" % self.uid)
        self.handle_last_will()
        self.disconnect()

        connection.set_close_callback(None)
        connection.set_timeout_callback(None)

    def _on_stream_close(self, connection):
        """
        Callback called when the stream closes. Ensures clearing the
        :attr:`self.connected` event and processing the :meth:`self.disconnect`
        method.
        """
        self.logger.debug("[uid: %s] Stream closed %s" %
                          (self.uid, self.connection._address))

        try:
            if self.connection.closed_due_error():
                self.handle_last_will()

            self.disconnect()

        except MQTTConnectionClosed:
            # already closed / disconnected
            pass

        connection.set_close_callback(None)
        connection.set_timeout_callback(None)


class client_process_context(ContextDecorator):
    def __init__(self, client, connection):
        assert isinstance(client, MQTTClient)
        self.client = client
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type == StreamClosedError:
            self.client.disconnect()

        elif exc_type == toro.Timeout:
            self.client.logger.debug("[uid: %s] _process_incoming_messages: timed out" %
                                     (self.client.uid, ))
            self.client._on_connection_timeout(self.connection)

        elif exc_type == TypeFactoryError:
            self.client.logger.debug('[uid: %s] %s' % (self.client.uid, exc_val.message))
            self.client.disconnect()

        elif exc_type in [CancelledException, MQTTConnectionClosed, MQTTMessageMakeError]:
            pass

        elif isinstance(exc_val, Exception):
            self.client.logger.exception(
                "[uid: %s] Unhandled exception on client_process_context: %s" %
                (self.client.uid, str(exc_val))
            )

        return True  # suppress the raised exception


class ClientSubscriptions():
    """
    Encapsulates subscription persistence access and mask regex caching.
    """
    def __init__(self, subscriptions):
        self._subscriptions = subscriptions

        self._re_cache = dict()

    def add(self, mask, qos, pattern=None):
        self._re_cache[mask] = pattern or re.compile(MQTTUtils.convert_to_ereg(mask))
        self._subscriptions[mask] = qos

    def __contains__(self, item):
        return item in self._subscriptions

    def __getitem__(self, mask):
        assert self.__contains__(mask)
        return self.qos(mask), self._get_regex(mask)

    def qos(self, mask):
        return self._subscriptions[mask]

    def _get_regex(self, mask):
        compiled = self._re_cache.get(mask, None)

        if not compiled:
            ereg = MQTTUtils.convert_to_ereg(mask)
            compiled = re.compile(ereg)
            self._re_cache[mask] = compiled

        return compiled

    @property
    def masks(self):
        return self._subscriptions.keys()

    def __delitem__(self, mask):
        if mask in self._subscriptions:
            del self._subscriptions[mask]
        if mask in self._re_cache:
            del self._re_cache[mask]


class OutgoingQueue():
    """
    This class controls packets to be delivered to the remote client.
    It encapsulates the logic to send packets and start new publish flows.
    """
    def __init__(self, outgoing_publishes):
        self.max_inflight = 1

        assert isinstance(outgoing_publishes, OutgoingPublishesBase)
        self.publishes = outgoing_publishes

        self.packets = deque()
        self.retrial_handles = dict()

        self.future = DummyFuture()

    def retry_pending(self):
        for packet in self.publishes.get_all_inflight():
            self.retrial_handles[packet.id] = None
            self.put(packet)

    def put(self, packet):
        """
        Puts a packet to the outgoing queue.
        No checks are done on the provided packets.
        """
        assert isinstance(packet, BaseMQTTMessage)
        if not self.future.done():
            self.future.set_result(packet)
        else:
            self.packets.append(packet)

    def put_publish(self, packet):
        """
        Puts a publish packet to the outgoing queue.
        If the QoS level is 0 it is only placed on the outgoing queue.
        Otherwise the packet is persisted and scheduled for publishing.
        """
        assert isinstance(packet, Publish)

        if packet.qos == 0:
            self.put(packet)
        else:
            self.publishes.insert(packet)
            self._start_next_flow()

    def set_sent(self, packet_id):
        if self.publishes.is_inflight(packet_id):
            self.publishes.set_sent(packet_id)

    def is_sent(self, packet_id):
        return self.publishes.is_inflight(packet_id) and \
               self.publishes.is_sent(packet_id)

    def is_pubconf(self, packet_id):
        return self.publishes.is_inflight(packet_id) and \
               self.publishes.is_pubconf(packet_id)

    def set_pubconf(self, packet_id):
        if self.publishes.is_inflight(packet_id):
            self.publishes.set_pubconf(packet_id)

    def get(self):
        """
        Gets the next packet to be sent to the remote client.
        :return: a `Future`
        """
        if not self.future.done():
            self.future.set_exception(CancelledException('Only one future supported'))

        self.future = Future()

        # try to start next publish flow first,
        # otherwise the outgoing packets would have to deplete before
        # any publish flows could start
        started = self._start_next_flow()

        if not started and self.packets:
            self.future.set_result(self.packets.popleft())

        return self.future

    def clear(self):
        """
        Clears the in-memory state of the outgoing queue. The data in
        persistence is left as is. If there is any pending `Future`
        waiting for result, it is cancelled.
        """
        for packet_id in self.retrial_handles.keys():
            self.cancel_retrial(packet_id)

        self.packets.clear()
        self.retrial_handles.clear()

        if not self.future.done():
            msg = 'Outgoing queue was cleansed'
            self.future.set_exception(CancelledException(msg))

        self.future = DummyFuture()

    def flow_completed(self, packet_id):
        """
        Removes the publish corresponding to the `packet-id` from the inflight
        set and from persistence.
        """
        if packet_id:
            self.publishes.remove(packet_id)
        if packet_id in self.retrial_handles:
            self.cancel_retrial(packet_id)
            del self.retrial_handles[packet_id]

        self._start_next_flow()

    def _start_next_flow(self):
        if self.publishes.inflight_len < self.max_inflight:
            packet = self.publishes.get_next()
            if packet:
                self.retrial_handles[packet.id] = None
                self.put(packet)
                return True

        return False

    def _retry_flow(self, packet_id):
        if self.publishes.is_inflight(packet_id):
            self.retrial_handles[packet_id] = None
            self.put(self.publishes.get_inflight(packet_id))

    def set_retrial(self, packet_id, deadline):
        handle = self.retrial_handles.get(packet_id)

        if handle:
            self.cancel_retrial(packet_id)

        callback = lambda: self._retry(packet_id)
        handle = ioloop.IOLoop.current().add_timeout(deadline, callback)
        self.retrial_handles[packet_id] = handle

    def cancel_retrial(self, packet_id):
        handler = self.retrial_handles.get(packet_id)
        if handler is not None:
            ioloop.IOLoop.current().remove_timeout(handler)
            self.retrial_handles[packet_id] = None

    def _retry(self, packet_id):
        if packet_id in self.retrial_handles:
            self._retry_flow(packet_id)
