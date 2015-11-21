from broker.actions import IncomingPublish, IncomingPuback, IncomingPubrec, IncomingPubrel, IncomingPubcomp, \
    IncomingSubscribe, IncomingUnsubscribe, IncomingPingreq, IncomingDisconnect, OutgoingPublish, OutgoingAction, \
    OutgoingPubrel
from .messages import Connect, Connack, Disconnect, Publish, Subscribe, \
    Pingreq, Puback, Pingresp, Suback, Unsubscribe, Unsuback, Pubrec, Pubrel, Pubcomp


class MQTTMessageFactory():
    _dispatch_table = {0x00: "null", 0x01: Connect, 0x02: Connack,
                       0x03: Publish, 0x04: Puback, 0x05: Pubrec,
                       0x06: Pubrel, 0x07: Pubcomp, 0x08: Subscribe,
                       0x09: Suback, 0x0A: Unsubscribe, 0x0B: Unsuback,
                       0x0C: Pingreq, 0x0D: Pingresp, 0x0E: Disconnect
    }

    def __init__(self):
        raise RuntimeError("One should not instantiate this class")

    @classmethod
    def make(cls, bytes_):
        if bytes_ is None:
            raise MQTTMessageMakeError('argument should not be None')

        try:
            msg_type = bytes_[0] >> 4
            class_ = cls._dispatch_table[msg_type]

            return class_.from_bytes(bytes_)

        except AttributeError:
            raise MQTTMessageMakeError('invalid message type')


class MQTTMessageMakeError(Exception):
    pass


class TypeFactory():
    registered_types = {}
    
    @classmethod
    def make(cls, obj, *args):
        t = type(obj)

        if t not in cls.registered_types:
            raise TypeFactoryError('unexpected message received - type:%s' % t)

        return cls.registered_types[t](obj, *args)


class TypeFactoryError(Exception):
    def __init__(self, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message


class IncomingActionFactory(TypeFactory):
    registered_types = {
        Publish: IncomingPublish,
        Puback: IncomingPuback,
        Pubrec: IncomingPubrec,
        Pubrel: IncomingPubrel,
        Pubcomp: IncomingPubcomp,
        Subscribe: IncomingSubscribe,
        Unsubscribe: IncomingUnsubscribe,
        Pingreq: IncomingPingreq,
        Disconnect: IncomingDisconnect,
    }


class OutgoingActionFactory(TypeFactory):
    registered_types = {
        Publish: OutgoingPublish,
        Puback: OutgoingAction,
        Pubrec: OutgoingAction,
        Pubrel: OutgoingPubrel,
        Pubcomp: OutgoingAction,
        Suback: OutgoingAction,
        Unsuback: OutgoingAction,
        Pingresp: OutgoingAction,
    }
