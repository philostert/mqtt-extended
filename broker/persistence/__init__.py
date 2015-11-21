from itertools import cycle


class PersistenceBase():
    """
    Base 'interface' class that defines the basic methods for broker
    persistence.
    """
    def get_client_uids(self):
        """
        Retrieves the persisted clients uids.
        :return: an iterable list of uids (strings)
        """
        pass

    def get_retained_messages(self):
        """
        Retrieves the retained publishes
        :return: a dict[topic, publish]
        """
        pass

    def get_for_client(self, uid):
        """
        Get or creates an object to access persistence
        for a client.
        :return: a subclass of ClientPersistenceBase
        """
        return ClientPersistenceBase(uid)

    def remove_client_data(self, uid):
        """
        Permanently removes client persistence data
        """
        pass


class ClientPersistenceBase():
    def __init__(self, uid):
        self.uid = uid

    @property
    def subscriptions(self):
        """
        Retrieves the topics (and qos's) subscribed by the client.
        :return: a dict[topic, qos]
        """
        return None

    @property
    def incoming_packet_ids(self):
        """
        Retrieves the set of packet ids being received.
        Only used for QoS level 2 incoming packets
        :return: set of int
        """
        return None

    @property
    def outgoing_publishes(self):
        """
        Retrieves th
        :return:
        """
        return None


class OutgoingPublishesBase():
    """
    This class defines the protocol of the OutgoingPublishes persistence
    classes. Persistence should support storing an arbitrary number of
    messages, not being limited by the packet id limit (65K).

    The implementing class must store the messages in a queue when
    `insert` is called. Then, when a new publish flow is being started,
    `get_next` method is called. The `get_next` method should pop an item
    from that queue, assign a free packet id and persist it in an in-flight
    structure. Finnaly, when the flow is completed the `remove` method is
    called.

    Other methods are required to retrieve in-flight items and state, and
    to get and set 'sent' and 'confirmed' flags.
    """

    def insert(self, msg):
        """
        Creates and pushes a new outgoing publish entry, to the end of a
        queue.
        """
        pass

    def get_next(self):
        """
        Gets the next packet to be published. Pops an item from the queue and
        adds it to the in-flight structure.

        This method is called to start a new flow.

        Returns the publish packet when succeeded, and None when the queue is
        empty.
        """
        pass

    @property
    def inflight_len(self):
        """
        Gets the count of publishes in-flight.
        """
        return 0

    def is_inflight(self, packet_id):
        """
        Checks if the given packet_id is still in in-flight state.
        """
        pass

    def get_all_inflight(self):
        """
        Gets all the in-flight packets in the *same order* provided by the
        `get_next` method.

        This method is called when retrying to publish all the in-flight
        messages.
        """
        pass

    def get_inflight(self, packet_id):
        """
        Gets an specific in-flight packet, by packet_id. Called when retrying
        to publish an specific packet.
        """
        pass

    def set_sent(self, packet_id):
        """
        Marks an outgoing publish with "publish sent".
        This is used with publishes in QoS levels 1 or 2, after a publish
        packet is successfully written.
        """
        pass

    def is_sent(self, packet_id):
        """
        Checks whether the publish was previously sent or not.
        This is used with publishes in QoS levels 1 or 2 to decide to set the
        DUP flag or not.
        """
        pass

    def set_pubconf(self, packet_id):
        """
        Marks an outgoing publish with "publish confirmed".
        This is used with publishes in QoS level 2 exclusively, after a PUBREC
        packet is received.
        """
        pass

    def is_pubconf(self, packet_id):
        """
        Checks whether the publish was confirmed or not.
        This is used with publishes in QoS level 2 exclusively, when deciding
        to send a PUBLISH packet or a PUBREL packet.
        """
        pass

    def remove(self, packet_id):
        """
        Removes a publish entry from the in-flight structure by packet_id.
        After this method finishes, the packet_id can be reused.
        """
        pass


class PacketIdGenerator():
    """
    Cycles through the allowed range of packet_ids, skipping the ids in use.
    """
    def __init__(self, reserved):
        self._ids = cycle(range(1, 65535))
        self._max_ids = 65534
        self._reserved = reserved

    def next(self):
        if len(self._reserved) >= self._max_ids:
            raise PacketIdsDepletedError()

        for packet_id in self._ids:
            if packet_id not in self._reserved:
                return packet_id


class PacketIdsDepletedError(MemoryError):
    def __init__(self):
        msg = "All packet ids are reserved"
        super().__init__(msg)


from .in_memory import InMemoryPersistence, InMemoryClientPersistence
from .redis import RedisPersistence
