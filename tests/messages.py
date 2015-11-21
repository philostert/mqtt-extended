from unittest import TestCase
from broker.messages import Publish


class TestPublishMessage(TestCase):
    def setUp(self):
        self.msg = Publish()
        self.msg.id = 1
        self.msg.topic = '/foobar'

    def test_hash_for_small_msg(self):
        self.msg.payload = b'abcd'
        self.assertEqual(self.msg.raw_data, self.msg.__hash__())

    def test_hash_for_large_msg(self):
        self.msg.payload = 64 * b'abcd'

        precal_digest = b"x\xb5\xc2\xdfJ\xd0'hp\x1d\xaeV\xa1\xec\xa9\x98" \
                        b"\xc8\xcb7\xd8\xb4a_\xb9\xfc\xb4\x8a$\x92\xf6\xceY"

        self.assertEqual(precal_digest, self.msg.__hash__())