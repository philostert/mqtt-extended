from unittest import TestCase
from unittest.mock import MagicMock
from time import time

import mosquitto

from tests.util import MQTTTestUtils
from broker.messages import Subscribe


class BaseTransactionTestCase(TestCase):
    def setUp(self):
        self.host = 'localhost'
        self.port = 1883
        self.topic = '/foobar'

        self.client = mosquitto.Mosquitto('test-%d' % time())
        self.client.username_pw_set('testios', '123456')
        self.client.connect(self.host, self.port)

        self.mock_callbacks(self.client)

    @classmethod
    def mock_callbacks(cls, mosquitto_client):
            mosquitto_client.on_connect = MagicMock()
            mosquitto_client.on_unsubscribe = MagicMock()
            mosquitto_client.on_publish = MagicMock()
            mosquitto_client.on_message = MagicMock()
            mosquitto_client.on_subscribe = MagicMock()
            mosquitto_client.on_disconnect = MagicMock()


class TestUnsubscribe(BaseTransactionTestCase):
    def test_transaction(self):
        self.client.subscribe(self.topic, 1)
        self.client.unsubscribe(self.topic)

        t = MQTTTestUtils.loop_and_check_callback_thread(self.client,
                                                         'on_unsubscribe', 1)
        t.start()
        t.join(timeout=1)

        self.assertEqual(self.client.on_unsubscribe.call_count, 1)


class TestSubscribe(BaseTransactionTestCase):
    def test_subscribe(self):
        self.client.subscribe(self.topic, qos=1)

        t = MQTTTestUtils.loop_and_check_callback_thread(self.client,
                                                         'on_subscribe', 1)
        t.start()
        t.join(timeout=1)

        self.assertEqual(self.client.on_subscribe.call_count, 1)

    def multiple_subscribe(self):
        msg = Subscribe()
        msg.id = 5
        msg.subscription_intents = (('bob', 1), ('alice', 0))
        self.client._packet_queue(130, msg.raw_data, msg.id, msg.qos)

    def test_multiple_subscribe(self):
        self.multiple_subscribe()

        t = MQTTTestUtils.loop_and_check_callback_thread(self.client,
                                                         'on_unsubscribe', 1)
        t.start()
        t.join(timeout=1)

        self.assertEqual(self.client.on_subscribe.call_count, 1)

    def test_retained_message_on_subscribe(self):
        client = mosquitto.Mosquitto('test-%d' % time())
        self.mock_callbacks(client)
        client.username_pw_set('testios', '123456')
        client.connect(self.host, self.port)
        client.publish('bob', "12345", 1, True)
        client.disconnect()

        t = MQTTTestUtils.loop_and_check_callback_thread(client,
                                                         'on_publish', 1)
        t.start()
        t.join(timeout=1)
        self.assertEqual(client.on_publish.call_count, 1)

        self.multiple_subscribe()

        t = MQTTTestUtils.loop_and_check_callback_thread(self.client,
                                                         'on_message', 1)
        t.start()
        t.join(timeout=1)

        self.assertEqual(self.client.on_message.call_count, 1)


class TestConnection(BaseTransactionTestCase):
    def test_transaction(self):
        self.client.disconnect()

        MQTTTestUtils.loop_and_check_callback_thread(self.client).run()

        self.assertEqual(self.client.on_connect.call_count, 1)


class TestIncomingPublish(BaseTransactionTestCase):
    def test_qos1_publish_receives_puback(self):
        self.client.subscribe(self.topic, qos=1)
        self.client.publish(self.topic, 'foobar', qos=1)

        t = MQTTTestUtils.loop_and_check_callback_thread(self.client,
                                                         'on_publish', 1)
        t.start()
        t.join(timeout=1)

        self.assertEqual(self.client.on_publish.call_count, 1)


class TestOutgoingPublish(BaseTransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client.subscribe(self.topic, qos=1)

        self.publisher = mosquitto.Mosquitto('publisher')
        self.publisher.username_pw_set('foo_pub', '123456')
        self.publisher.connect(self.host, self.port)
        self.mock_callbacks(self.publisher)

    def test_qos1_publish_is_delivered(self):
        self.publisher.publish(self.topic, 'foobar', 1)

        c = MQTTTestUtils.loop_and_check_callback_thread(self.client, 'on_message', 1)
        p = MQTTTestUtils.loop_and_check_callback_thread(self.publisher, 'on_publish', 1)

        c.start()
        p.run()
        c.join(timeout=1)

        self.assertEqual(self.publisher.on_publish.call_count, 1)
        self.assertEqual(self.client.on_message.call_count, 1)

    def test_qos1_duplicated_message_is_not_routed_twice(self):
        # Mock it so we can count the received pubacks
        self.publisher._handle_pubackcomp = MagicMock(side_effect=self.publisher._handle_pubackcomp)

        n_messages = 2
        raw_data = bytearray(b'\x00\x07/foobar\x00\x05foobar')

        for i in range(0, n_messages):
            self.publisher._send_publish(5, self.topic, raw_data, 1,
                                         False, True)

        c = MQTTTestUtils.loop_and_check_callback_thread(self.client)
        p = MQTTTestUtils.loop_and_check_callback_thread(self.publisher, '_handle_pubackcomp', n_messages)

        c.start()
        p.run()

        c.join(timeout=1)

        self.assertEqual(self.publisher._handle_pubackcomp.call_count, n_messages)
        self.assertEqual(self.client.on_message.call_count, 1)