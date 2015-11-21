from broker.factory import MQTTMessageFactory
from broker.persistence import PersistenceBase, ClientPersistenceBase, OutgoingPublishesBase, PacketIdGenerator


class InMemoryPersistence(PersistenceBase):
    def __init__(self):
        self.retained_messages = dict()
        self.clients = dict()

    def get_client_uids(self):
        return self.clients.keys()

    def get_retained_messages(self):
        return self.retained_messages

    def get_for_client(self, uid):
        client_persistence = self.clients.get(uid, None)

        if client_persistence is None:
            client_persistence = InMemoryClientPersistence(uid)
            self.clients[uid] = client_persistence

        return client_persistence

    def remove_client_data(self, uid):
        if uid in self.clients:
            del self.clients[uid]


class InMemoryClientPersistence(ClientPersistenceBase):
    def __init__(self, uid):
        super().__init__(uid)
        self._subscriptions = dict()
        self._incoming_packet_ids = set()
        self._outgoing_publishes = InMemoryOutgoingPublishes()

    @property
    def subscriptions(self):
        return self._subscriptions

    @property
    def incoming_packet_ids(self):
        return self._incoming_packet_ids

    @property
    def outgoing_publishes(self):
        return self._outgoing_publishes


class InMemoryOutgoingPublishes(OutgoingPublishesBase):
    def __init__(self):
        self._queue = list()

        self._inflight_ids = list()
        self._inflight = dict()

        self._ids_gen = PacketIdGenerator(self._inflight)

    def insert(self, msg):
        self._queue.append(msg)

    def get_next(self):
        if len(self._queue) > 0:
            msg = self._queue.pop(0)
            msg.id = self._ids_gen.next()
            entry = {
                'id': msg.id,
                'msg': msg,
            }
            self._inflight_ids.append(msg.id)
            self._inflight[msg.id] = entry
            return msg.copy()
        else:
            return None

    @property
    def inflight_len(self):
        return len(self._inflight_ids)

    def is_inflight(self, packet_id):
        return packet_id in self._inflight_ids

    def get_all_inflight(self):
        for packet_id in self._inflight_ids:
            entry = self._inflight.get(packet_id)
            if entry is not None:
                yield entry['msg'].copy()

    def get_inflight(self, packet_id):
        if packet_id in self._inflight_ids:
            entry = self._inflight.get(packet_id)
            if entry is not None:
                return entry['msg'].copy()
        else:
            raise KeyError('Unknown packet id')

    def set_sent(self, packet_id):
        p = self._inflight.get(packet_id)
        if p is not None:
            p['sent'] = True
        else:
            raise KeyError('Unknown packet id')

    def is_sent(self, packet_id):
        p = self._inflight.get(packet_id)
        if p is not None:
            return 'sent' in p
        else:
            raise KeyError('Unknown packet id')

    def set_pubconf(self, packet_id):
        p = self._inflight.get(packet_id)
        if p is not None:
            p['conf'] = True
        else:
            raise KeyError('Unknown packet id')

    def is_pubconf(self, packet_id):
        p = self._inflight.get(packet_id)
        if p is not None:
            return 'conf' in p
        else:
            raise KeyError('Unknown packet id')

    def remove(self, packet_id):
        if packet_id in self._inflight:
            del self._inflight[packet_id]

        if packet_id in self._inflight_ids:
            self._inflight_ids.remove(packet_id)
