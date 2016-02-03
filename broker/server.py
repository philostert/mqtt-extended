import tornado.concurrent
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.log import access_log
from tornado import gen
from logging import getLogger
import toro
from broker import MQTTConstants
from broker.access_control import NoAuthentication, Authorization
from broker.client import MQTTClient
from broker.exceptions import ConnectError
from broker.messages import Publish, Connect, Connack, Subscribe
from broker.connection import MQTTConnection
from broker.factory import MQTTMessageFactory
from broker.persistence import InMemoryPersistence
from paho.mqtt.extended_client import Extended_Client
from paho.mqtt.paho_partner_pair import Paho_Partner_Pair

client_logger = getLogger('activity.clients')


class MQTTServer(TCPServer):
    """
    This is the highest abstraction of the package and represents the whole MQTT
    Broker. It's main roles are handling incoming connections, keeping tabs for
    the known client sessions and dispatching messages based on subscription
    matching.
    """

    def __init__(self, authentication=None, persistence=None, clients=None,
                 ssl_options=None):
        super().__init__(ssl_options=ssl_options)

        self.clients = clients if clients is not None else dict()
        assert isinstance(self.clients, dict)

        self.persistence = persistence or InMemoryPersistence()
        self.authentication = authentication or NoAuthentication()

        self.recreate_sessions(self.persistence.get_client_uids())

        self._retained_messages = RetainedMessages(self.persistence.get_retained_messages())
        assert isinstance(self._retained_messages, RetainedMessages)

        self.hacked_topic_list = []
        self.paho_partner_pair = None  # Paho_Partner_Pair(external_address="m2m.eclipse.org")
        self.uplink = None  # self.paho_partner_pair.internal_client

    def register_paho_partner_pair(self, pair):  # pair: Paho_Partner_Pair):
        assert isinstance(pair, Paho_Partner_Pair)
        self.paho_partner_pair = pair
        # XXX this was wrong!: self.uplink = pair.internal_client

    def has_uplink(self):
        """ checks whether a paho_partner_pair was registered and uplink is
        represented by a common tegris client object.
        :return:
        """
        if self.paho_partner_pair and self.uplink:
            return True
        return False

    def recreate_sessions(self, uids):
        access_log.info("recreating %s sessions" % len(uids))
        for uid in uids:
            if uid not in self.clients:
                self.add_client(self.recreate_client(str(uid)))

    def get_known_client(self, connect_msg):
        """
        Returns a known MQTTClient instance that has the same uid defined on
        the Connect message.

        .. caution::
          If the connect message defines the usage of a clean session, this
          method will clear any previous session matching this client ID and
          automatically return None

        :param connect_msg Connect: A connect message that specifies the client.
        """
        assert isinstance(connect_msg, Connect)

        client = self.clients.get(connect_msg.client_uid)
        if client is not None:
            assert isinstance(client, MQTTClient)
            if connect_msg.clean_session:
                # Force server to remove the client, regardless of its
                # previous clean_sessions configuration
                self.remove_client(client)
                client = None

        return client

    def get_or_create_client(self, connection, msg, authorization):
        if not authorization.is_connection_allowed():
            raise ConnectError("Authentication failed uid:%s user:%s"
                               % (msg.client_uid, msg.username))

        client = self.get_known_client(msg)

        if client is None:
            client = self.create_client(connection, msg, authorization)
        else:
            self.update_client(connection, msg, authorization, client)

        self.configure_last_will(client, msg)
        return client

    def create_client(self, connection, msg, authorization):
        client_persistence = self.persistence.get_for_client(msg.client_uid)
        client = MQTTClient(
                server=self,
                connection=connection,
                authorization=authorization,
                uid=msg.client_uid,
                clean_session=msg.clean_session,
                keep_alive=msg.keep_alive,
                persistence=client_persistence,
        )

        # verbosity... testing
        type = "plain-client"
        if (client.is_broker()):
            type = "broker"
        access_log.info("[uid: %s] new session created (client type: %s)"
                        % (client.uid, type))
        return client

    def recreate_client(self, client_uid):
        return MQTTClient(
                server=self,
                connection=None,
                uid=client_uid,
                clean_session=False,
                persistence=self.persistence.get_for_client(client_uid)
        )

    def update_client(self, connection, msg, authorization, client):
        client.update_configuration(
                clean_session=msg.clean_session,
                keep_alive=msg.keep_alive
        )
        client.update_connection(connection)
        client.update_authorization(authorization)

        access_log.info("[uid: %s] Reconfigured client upon "
                        "reconnection." % client.uid)

    def configure_last_will(self, client, connect_msg):
        """
        Configures the last will message options for a given client on its
        connect message. Both the client and the connect message *must* point
        to the same client uid.

        :param client MQTTClient: A client instance;
        :param connect_msg Connect: A Connect message that specifies the client.
        """
        assert isinstance(connect_msg, Connect)
        assert isinstance(client, MQTTClient)
        assert connect_msg.client_uid == client.uid

        if connect_msg.will_message is not None:
            will_payload = connect_msg.will_message.encode()
        else:
            will_payload = None
        client.configure_last_will(
                topic=connect_msg.will_topic,
                payload=will_payload,
                qos=connect_msg.will_qos,
                retain=connect_msg.will_retain
        )

    @gen.coroutine
    def handle_stream(self, stream, address):
        """
        This coroutine is called by the Tornado loop whenever it receives a
        incoming connection. The server resolves the first message sent, checks
        if it's a CONNECT frame and configures the client accordingly.

        :param IOStream stream: A :class:`tornado.iostream.IOStream` instance;
        :param tuple address: A tuple containing the ip and port of the
          connected client, ie ('127.0.0.1', 12345).
        """
        with stream_handle_context(stream) as context:
            connection = MQTTConnection(stream, address)

            msg = yield self.read_connect_message(connection)
            context.client_uid = msg.client_uid

            authorization = yield self.authenticate(msg)
            yield self.write_connack_message(connection, msg, authorization)

            context.client = client = self.get_or_create_client(
                    connection, msg, authorization)

            client.start()
            self.add_client(client)

    @gen.coroutine
    def read_connect_message(self, connection):
        bytes_ = yield connection.read_message()
        msg = MQTTMessageFactory.make(bytes_)

        if not isinstance(msg, Connect):
            raise ConnectError('The first message is expected to be CONNECT')

        client_logger.debug("[B << C] [uid: %s] %s" %
                            (msg.client_uid, msg.log_info()))

        return msg

    @gen.coroutine
    def authenticate(self, msg):
        if not msg.client_uid and not msg.clean_session:
            raise ConnectError('Client must provide an id to connect '
                               'without clean session')

        authorization = yield self.authentication.authenticate(
                msg.client_uid,
                msg.username, msg.passwd)

        assert isinstance(authorization, Authorization)
        if authorization.is_fully_authorized():
            client_logger.debug('[uid: %s] user:%s fully authorized' %
                                (msg.client_uid, msg.username))
        return authorization

    @gen.coroutine
    def write_connack_message(self, connection, msg, authorization):
        if not authorization.is_connection_allowed():
            ack = Connack.from_return_code(0x04)

        else:
            sp = self.is_session_present(msg)
            ack = Connack.from_return_code(0x00, session_present=sp)

        client_logger.debug("[B >> C] [uid: %s] %s" %
                            (msg.client_uid, ack.log_info()))

        yield connection.write_message(ack)

    def is_session_present(self, msg):
        return not msg.clean_session and msg.client_uid in self.clients

    def add_client(self, client):
        """
        Register a client to the Broker.

        :param MQTTClient client: A :class:`broker.client.MQTTClient` instance.
        """
        assert isinstance(client, MQTTClient)
        self.clients[client.uid] = client

        if not self.uplink and "uplink" == client.uid:
            # self.uplink shall be the tegris-representation of the local
            # paho partner pair client facing tegris. It's likely that
            # no external client could connect beforehand with uid 'uplink'.
            self.uplink = client

    def remove_client(self, client):
        """
        Removes a client from the know clients list. It's safe to call this
        method without checking if the client is already known.

        :param MQTTClient client: A :class:`broker.client.MQTTClient` instance;

        .. caution::
           It won't force client disconnection during the process, which can
           result in a lingering client in  the Tornado loop.
        """
        assert isinstance(client, MQTTClient)

        self.persistence.remove_client_data(client.uid)

        if client.uid in self.clients:
            del self.clients[client.uid]
            access_log.info("[uid: %s] session cleaned" % client.uid)

    def dispatch_message(self, client, msg, cache=None):
        """
        Dispatches a message to a client based on its subscriptions. It is safe
        to call this method without checking if the client has matching
        subscriptions.

        :param MQTTClient client: The client which will possibly receive the
          message;
        :param Publish msg: The message to be delivered.
        :param dict cache: A dict that will be used for raw data caching.
          Defaults to a empty dictionary if None.
        """
        print("dispatching Publish to client_id: %s of class %s" % (client.uid, client.__class__))

        assert isinstance(msg, Publish)
        assert isinstance(client, MQTTClient)
        assert client.uid in self.clients

        cache = cache if cache is not None else {}
        qos_list = client.get_list_of_delivery_qos(msg)

        for qos in qos_list:

            # If the client is not connected, drop QoS 0 messages
            if client.is_connected() or \
                            qos > MQTTConstants.AT_MOST_ONCE:

                if qos not in cache:
                    msg_copy = msg.copy()
                    msg_copy.qos = qos
                    cache[qos] = msg_copy

                client.publish(cache[qos])

        # TODO remove all code below - this is just a test of the forwarding method
        '''
        if "uplink" == client.uid:
            print("SEND TO UPLINK - ALWAYS ALL! TESTING")
            qos = 0
            if qos not in cache:
                msg_copy = msg.copy()
                msg_copy.retain = True # retain!!!
                msg_copy.qos = qos
                cache[qos] = msg_copy

            client.publish(cache[qos])
        '''
    """
    1. Write to hacked topic list
    2. Check if uplink is set
    3. Check for origin
    4. Assert that all types fit
    5. Send new topic to upstream
    """

    def decide_uplink_publish(self, msg, sender_uid):
        # 0.
        msg.retain = True
        # 1.
        if not (msg.topic, msg.qos) in self.hacked_topic_list:
            print("Added Topic to Publishlist: {} QoS: {} Payload: {}".format(msg.topic, msg.qos, msg.payload))
            self.hacked_topic_list.append((msg.topic, msg.qos))
        else:
            return # already announced once
        # 2.
        if not self.has_uplink():
            print("cancel: decide_uplink_publish - has no uplink!")
            return
        # 3. don't send it back where it came from
        if self.uplink.uid == sender_uid:
            return
        # TODO decide whether to publish with contents or announce without contents!
        # announce only: keep track of (topic, qos) and announce only once
        # 4.
        assert isinstance(self.uplink, MQTTClient)
        assert isinstance(msg, Publish)
        # 5.
        print("Announcing %s" % msg.topic)
        self.uplink.send_packet(msg)
        '''
        upl = self.clients.get("uplink")
        if upl is not None:
            assert isinstance(upl, MQTTClient)
            print("found uplink")
            upl.send_packet(msg)
        '''
        # XXX announce via shorter route; try long route to test long route in general
        # self.uplink.send_packet(msg) # long route
        # self.paho_partner_pair.announce(msg.topic, msg.qos) # shorter route
        #self.paho_partner_pair.announce(msg)
        # shorter route

    def broadcast_message(self, msg, sender_uid):
        """
        Broadcasts a message to all clients with matching subscriptions,
        respecting the subscription QoS and restrictions on packet loops.

        :param Publish msg: A :class:`broker.messages.Publish` instance.
        :param MQTTClient sender: The client which sent the message.
        """
        assert isinstance(msg, Publish)
        assert isinstance(sender_uid, str)

        # Broadcasted messages must always be delivered with the retain flag
        # set to false to clients which are plain clients (non-brokers)
        msg_reduced = msg.copy()
        msg_reduced.retain = False

        cache = {}

        for client in self.clients.values():
            # XXX Packet loop restriction #4: no forwarding to sender if sender
            # also receives subscriptions.
            if client.uid == sender_uid and client.receive_subscriptions:
                continue
            if client.is_broker():
                self.dispatch_message(client, msg, cache)
            else:
                self.dispatch_message(client, msg_reduced, cache)
        print("CALL DECIDE UPLINK PUBLISH")
        self.decide_uplink_publish(msg, sender_uid)

    def forward_subscription(self, topic, granted_qos, sender_uid):
        """
        :param topic: topic name or topic mask (with wildcards)
        :param sender_uid: sender's ID, don't send subscription back there!
        :return: FIXME (not specified yet)
        """
        """
        if not (topic, granted_qos) in self.hacked_topic_list:
            access_log.info("[.....] forwarding subscription from: \"%s\"" % sender_uid)
            # TODO rebuild package with subscription intents; think about qos
            msg = Subscribe()

            # recipients = [c for c in self.clients if c.receive_subscriptions and not c.uid == sender_uid]
            recipients = filter(lambda client: client.receive_subscriptions and not client.uid == sender_uid,
                            self.clients.values())
            for client in recipients:
                client.send_packet(msg)
            # TODO send it to "uplink" message broker if it did not come from there
            if sender_uid:  # XXX uplink is not a client, assume sender_uid would be None
                pass
                # Uplink.send_packet(msg)
        """
        access_log.info("[.....] forwarding subscription from: \"%s\"" % sender_uid)

        # TODO rebuild package with subscription intents; think about qos
        msg = Subscribe.generate_single_sub(topic, granted_qos)
        if msg:
            return
        print("BROKEN!")

        # recipients = [c for c in self.clients if c.receive_subscriptions and not c.uid == sender_uid]
        recipients = filter(lambda client: client.receive_subscriptions and not client.uid == sender_uid,
                            self.clients.values())
        for client in recipients:
            client.send_packet(msg)

        # TODO send it to "uplink" message broker if it did not come from there
        if sender_uid:  # XXX uplink is not a client, assume sender_uid would be None
            pass
            # Uplink.send_packet(msg)

    def disconnect_client(self, client):
        """
        Disconnects a MQTT client. Can be safely called without checking if the
        client is connected.

        :param MQTTClient client: The MQTTClient to be disconnect
        """
        assert isinstance(client, MQTTClient)
        client.disconnect()

    def disconnect_all_clients(self):
        """ Disconnect all known clients. """

        # The tuple() is needed because the dictionary could change during the
        # iteration
        for client in tuple(self.clients.values()):
            self.disconnect_client(client)

    def handle_incoming_publish(self, msg, sender_uid):
        """
        Handles an incoming publish. This method is normally called by the
        clients a mechanism of notifying the server that there is a new message
        to be processed. The processing itself consists of retaining the message
        according with the `msg.retain` flag and broadcasting it to the
        subscribers.

        :param Publish msg: The Publish message to be processed.
        :param MQTTClient sender: The client which sent the message.
        """
        assert isinstance(sender_uid, str)

        if msg.retain is True:
            self._retained_messages.save(msg, sender_uid)

        # access_log.info("[.....] broadcasting payload: \"%s\"" % msg.payload)
        self.broadcast_message(msg, sender_uid)

    def enqueue_retained_message(self, client, subscription_mask):
        """
        Enqueues all retained messages matching the `subscription_mask` to be
        sent to the `client`.

        :param MQTTClient client: A known MQTTClient.
        :param str subscription_mask: The subscription mask to match the
          messages against.
        """

        # print(self._retained_messages._messages)
        assert isinstance(client, MQTTClient)
        for e in self._retained_messages.items():
            print("INFO: {}".format(e))
        for topic, (message, sender_uid) in self._retained_messages.items():
            # XXX Packet loop restriction #4: no forwarding to sender if sender
            # also receives subscriptions.
            if client.uid == sender_uid and client.is_broker():#receive_subscriptions:
                continue

            if message is not None:
                msg_obj = Publish.from_bytes(message)
                qos = client.get_matching_qos(msg_obj, subscription_mask)

                if qos is not None:
                    # creates a copy of the object to avoid reference errors
                    msg_copy = msg_obj.copy()
                    msg_copy.qos = qos
                    client.publish(msg_copy)


class stream_handle_context():
    def __init__(self, stream):
        self.stream = stream
        self.client = None
        self.client_uid = '?'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type == toro.Timeout:
            access_log.debug("[uid: %s] connection timeout"
                             % self.client_uid)

        elif exc_type == StreamClosedError:
            access_log.warning('[uid: %s] stream closed unexpectedly'
                               % self.client_uid)

        elif exc_type == ConnectError:
            self.stream.close()
            access_log.info('[uid: %s] connection refused: %s'
                            % (self.client_uid, exc_val.message))

        elif exc_type == Exception:
            access_log.exception('[uid: %s] error handling stream'
                                 % self.client_uid, exc_info=True)

        if exc_val is not None:
            if self.client is not None:
                self.client.disconnect()

        return True  # suppress the raised exception


class RetainedMessages():
    def __init__(self, retained_messages):
        self._messages = retained_messages

    def save(self, msg, sender_uid):
        assert isinstance(msg, Publish)
        if len(msg.payload) == 0:
            if msg.topic in self._messages:
                del self._messages[msg.topic]
        else:
            self._messages[msg.topic] = (msg.raw_data, sender_uid)

    def items(self):
        return self._messages.items()
