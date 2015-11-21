import logging
from broker.factory import MQTTMessageFactory
from broker.persistence import PersistenceBase, ClientPersistenceBase, OutgoingPublishesBase, PacketIdGenerator
from .redis_types import RedisHashDict, RedisIntSet, RedisUnicodeSet, RedisIntList, RedisList


logger = logging.getLogger('persistence.redis')


class RedisPersistence(PersistenceBase):
    def __init__(self, redis):
        self.redis = redis
        self.client_uids = RedisUnicodeSet(redis, key="mqtt_broker:client_uids")

        self._clients = dict()

    def get_client_uids(self):
        return self.client_uids

    def get_retained_messages(self):
        return RedisHashDict(self.redis, '_retained_messages')

    def get_for_client(self, uid):
        client = self._clients.get(uid, None)

        if client is None:
            client = RedisClientPersistence(self.redis, uid)
            self._clients[uid] = client
            self.client_uids.add(uid)

        return client

    def remove_client_data(self, uid):
        self.client_uids.remove(uid)

        client = self._clients.get(uid, None)

        if client is not None:
            client.delete_data()
            del self._clients[uid]


class RedisClientPersistence(ClientPersistenceBase):
    def __init__(self, redis, uid):
        super().__init__(uid)
        self.redis = redis

        self._subscriptions = RedisSubscriptionsDict(
            hash_name="%s:subscriptions" % uid,
            redis=self.redis)

        self._incoming_packet_ids = RedisIntSet(redis=self.redis,
                                                key="%s:incoming_packet_ids" % uid)
        self._outgoing_publishes = RedisOutgoingPublishes(redis=self.redis, uid=uid)

    @property
    def subscriptions(self):
        return self._subscriptions

    @property
    def incoming_packet_ids(self):
        return self._incoming_packet_ids

    @property
    def outgoing_publishes(self):
        return self._outgoing_publishes

    def delete_data(self):
        self.redis.delete(
            '%s:subscriptions' % self.uid,
            "%s:incoming_packet_ids" % self.uid,
            )
        self._outgoing_publishes.remove_all()


class RedisSubscriptionsDict(RedisHashDict):
    @staticmethod
    def _decode_key(k):
        return k.decode("utf-8") if k else k

    @staticmethod
    def _decode_value(v):
        return int(v) if v else v

    def __getitem__(self, key):
        return self._decode_value(super().__getitem__(key))

    def items(self):
        yield from ((self._decode_key(k), self._decode_value(v))
                    for k, v in super().items())

    def keys(self):
        yield from (self._decode_key(k)
                    for k in super().keys())

    def values(self):
        yield from (self._decode_value(v)
                    for v in super().values())


class RedisOutgoingPublishes(OutgoingPublishesBase):
    def __init__(self, redis, uid):
        self.redis = redis
        self.uid = uid

        self._queue = RedisList(redis, "%s:outgoing_queue" % uid)
        self._inflight = RedisPacketsDict(redis, "%s:outgoing_inflight" % uid)

        self._inflight_ids = RedisIntList(redis, '%s:outgoing_ids' % uid)
        self._sent_ids = RedisIntSet(redis, "%s:outgoing_sent_ids" % uid)
        self._confirmed_ids = RedisIntSet(redis, "%s:outgoing_conf_ids" % uid)

        self._ids_gen = PacketIdGenerator(self._inflight)

    def insert(self, msg):
        msg.id = 0  # sets a dummy id just to make it encode,
                    # the actual id is set on `get_next` method.
        self._queue.append(msg.raw_data)

    def get_next(self):
        """
        Gets the next packet to be published.
        Should be used to start a new flow.
        """
        # todo: do in a transaction
        if len(self._queue) > 0:
            raw_data = self._queue.pop()

            msg = MQTTMessageFactory.make(raw_data)
            msg.id = self._ids_gen.next()
            self._inflight_ids.append(msg.id)
            self._inflight[msg.id] = msg.raw_data
            return msg

        else:
            return None

    @property
    def inflight_len(self):
        return len(self._inflight)

    def is_inflight(self, packet_id):
        return packet_id in self._inflight

    def get_all_inflight(self):
        for packet_id in self._inflight_ids:
            raw = self._inflight.get(packet_id)
            if raw is not None:
                yield MQTTMessageFactory.make(raw)

    def get_inflight(self, packet_id):
        if packet_id in self._inflight:
            raw = self._inflight.get(packet_id)
            if raw is not None:
                return MQTTMessageFactory.make(raw)
        else:
            raise KeyError('Unknown packet id')

    def set_sent(self, packet_id):
        if packet_id in self._inflight:
            self._sent_ids.add(packet_id)
        else:
            raise KeyError('Unknown packet id')

    def is_sent(self, packet_id):
        if packet_id in self._inflight:
            return packet_id in self._sent_ids
        else:
            raise KeyError('Unknown packet id')

    def set_pubconf(self, packet_id):
        if packet_id in self._inflight:
            self._confirmed_ids.add(packet_id)
        else:
            raise KeyError('Unknown packet id')

    def is_pubconf(self, packet_id):
        if packet_id in self._inflight:
            return packet_id in self._confirmed_ids
        else:
            raise KeyError('Unknown packet id')

    def remove(self, packet_id):
        # todo: do in a transaction
        if packet_id in self._inflight:
            self._inflight_ids.remove(packet_id)
            self._sent_ids.remove(packet_id)
            self._confirmed_ids.remove(packet_id)
            del self._inflight[packet_id]

    def remove_all(self):
        self.redis.delete(
            '%s:outgoing_queue' % self.uid,
            '%s:outgoing_inflight' % self.uid,
            '%s:outgoing_ids' % self.uid,
            '%s:outgoing_sent_ids' % self.uid,
            "%s:outgoing_conf_ids" % self.uid,
            )


class RedisPacketsDict(RedisHashDict):
    @staticmethod
    def _decode_key(k):
        return int(k) if k else k

    def items(self):
        yield from ((self._decode_key(k), v)
                    for k, v in super().items())

    def keys(self):
        yield from (self._decode_key(k)
                    for k in super().keys())

