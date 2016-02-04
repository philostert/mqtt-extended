import copy
from itertools import chain
from broker import MQTTConstants

from broker.util import MQTTUtils


class BaseMQTTMessage():
    _message_type = 0x00
    _fixed_header = ('type', 'dup', 'qos', 'retain', 'length')
    _message_fields = tuple()
    _default_values = {
        'dup': False,
        'qos': 0,
        'retain': False,
    }

    @classmethod
    def from_bytes(cls, bytes_):
        assert type(bytes_) == bytes
        obj = cls()

        _raw_data = bytes(bytes_)

        obj.type, obj.dup, obj.qos, obj.retain, obj.length, remaining_data \
            = MQTTUtils.strip_fixed_header(_raw_data)

        assert obj.type == obj._message_type
        obj._decode_data(remaining_data)

        # The raw_data already corresponds to the obj field data. We change it
        # back to false to avoid encoding the data again upon raw_data lookup.
        obj._raw_data = _raw_data
        obj._pending_update = False

        return obj

    def __init__(self, **kwargs):
        self._initialize_fields()

        for k, v in kwargs.items():
            self.__setattr__(k, v)

    def __setattr__(self, key, value):
        if key in self._fixed_header or key in self._message_fields:
            self._pending_update = True

        return super().__setattr__(key, value)

    def __hash__(self):
        return MQTTUtils.hash_message_bytes(self.raw_data)

    def log_info(self):
        return "[%s]%s" % (
            self.__class__.__name__,
            self._extra_log_info(),
        )

    def _extra_log_info(self):
        return ''

    def _encode_fixed_header(self, data):
        buffer = bytearray(1)
        buffer[0] |= self.type << 4
        buffer[0] |= (self.dup or 0) << 3
        buffer[0] |= (self.qos or 0) << 1
        buffer[0] |= self.retain or 0
        
        if not data:
            buffer.extend(MQTTUtils.encode_length(0))
        else:
            buffer.extend(MQTTUtils.encode_length(len(data)))

        return bytearray(buffer)

    def _encode_data(self):
        return bytes()

    def _decode_data(self, _data):
        pass

    def _initialize_fields(self):
        for item in chain(self._fixed_header, self._message_fields):
            value = self._default_values.get(item, None)
            self.__setattr__(item, value)

        self.type = self._message_type

        self._raw_data = bytes()
        self._pending_update = True

    def _update_raw_data(self):
        data = self._encode_data()
        header = self._encode_fixed_header(data)

        msg = bytearray()
        msg.extend(header)

        if data:
            msg.extend(data)

        self._raw_data = bytes(msg)

    @property
    def raw_data(self):
        if self._pending_update:
            self._update_raw_data()

        return self._raw_data

    def copy(self):
        c = copy.copy(self)
        c._pending_update = True
        return c


class Connect(BaseMQTTMessage):
    _message_type = 0x01
    _message_fields = (
        'protocol_name', 'protocol_version',
        'has_username', 'username',
        'has_passwd', 'password',
        'will_retain', 'will_topic', 'will_qos', 'will_flag', 'will_message',
        'clean_session', 'keep_alive', 'client_uid'
    )

    def _decode_data(self, _data):
        self.protocol_name, l = MQTTUtils.decode_string(_data)
        assert self.protocol_name == 'MQIsdp' or self.protocol_name == 'MQTT'

        cursor = l + 2
        self.protocol_version = _data[cursor]
        assert self.protocol_version == 3 or self.protocol_version == 4

        cursor += 1
        self.has_username = (_data[cursor] & 0x80) == 0x80
        self.has_passwd = (_data[cursor] & 0x40) == 0x40
        self.will_retain = (_data[cursor] & 0x20) == 0x20
        self.will_qos = (_data[cursor] & 0x18) >> 3
        self.will_flag = (_data[cursor] & 0x04) == 0x04
        self.clean_session = (_data[cursor] & 0x02) == 0x02
        cursor += 1

        self.keep_alive = MQTTUtils.decode_value(_data[cursor:cursor+2])
        cursor += 2

        self.client_uid, l = MQTTUtils.decode_string(_data[cursor:])
        cursor += l

        if self.will_flag:
            cursor += 2

            self.will_topic, l = MQTTUtils.decode_string(_data[cursor:])
            cursor += l + 2

            self.will_message, l = MQTTUtils.decode_string(_data[cursor:])
            cursor += l
        else:
            self.will_topic = None
            self.will_message = None

        if self.has_username:
            cursor += 2
            self.username, l = MQTTUtils.decode_string(_data[cursor:])
            cursor += l
        else:
            self.username = None

        if self.has_passwd:
            cursor += 2
            if cursor < self.length - 2:
                self.passwd, l = MQTTUtils.decode_string(_data[cursor:])
            else:
                self.passwd = None
        else:
            self.passwd = None

    def _encode_data(self):
        buffer = bytearray()

        # variable header
        buffer.extend(MQTTUtils.encode_string(self.protocol_name))
        buffer.append(MQTTUtils.encode_byte(self.protocol_version))

        connect_flags = 0x00
        connect_flags |= 0x80 if self.has_username else 0x00
        connect_flags |= 0x40 if self.has_passwd else 0x00
        connect_flags |= 0x20 if self.will_retain else 0x00
        connect_flags |= ((self.will_qos or 0x00) << 3) & 0x18
        connect_flags |= 0x04 if self.will_flag else 0x00
        connect_flags |= 0x02 if self.clean_session else 0x00
        buffer.append(connect_flags)

        buffer.extend(MQTTUtils.encode_value(self.keep_alive))

        # payload
        buffer.extend(MQTTUtils.encode_string(self.client_uid))

        if self.will_flag:
            buffer.extend(MQTTUtils.encode_string(self.will_topic))
            buffer.extend(MQTTUtils.encode_string(self.will_message))

        if self.has_username:
            buffer.extend(MQTTUtils.encode_string(self.username))

        if self.has_passwd:
            buffer.extend(MQTTUtils.encode_string(self.passwd))

        return bytes(buffer)

    def _extra_log_info(self):
        return " CS: %d, KA: %s, LW: %d" % (
            self.clean_session,
            self.keep_alive,
            self.will_flag)


class Connack(BaseMQTTMessage):
    _message_type = 0x02
    _message_fields = ('session_present', 'return_code')
    _return_codes = {
        0x00: 'Connection Accepted',
        0x01: 'Connection Refused: unacceptable protocol version',
        0x02: 'Connection Refused: identifier rejected',
        0x03: 'Connection Refused: server unavailable',
        0x04: 'Connection Refused: bad user name or password',
        0x05: 'Connection Refused: not authorized',
    }

    SESSION_PRESENT = 0x01
    ACCEPTED = 0x00

    def _decode_data(self, _data):
        self.session_present = _data[0] == self.SESSION_PRESENT
        self.return_code = _data[1]

    def _encode_data(self):
        buffer = bytearray()
        sp = self.SESSION_PRESENT if self.session_present else 0x00
        buffer.append(MQTTUtils.encode_byte(sp))
        buffer.append(MQTTUtils.encode_byte(self.return_code))
        return bytes(buffer)

    def human_readable(self):
        if self.return_code in self._return_codes:
            return self._return_codes[self.return_code]
        return 'Illegal return code %d' % self.return_code

    @classmethod
    def from_return_code(cls, return_code, session_present=False):
        assert return_code in cls._return_codes

        obj = cls()
        obj.session_present = session_present
        obj.return_code = return_code

        return obj

    def _extra_log_info(self):
        return " SP: %d, RC: %d" % (self.session_present, self.return_code)


class Disconnect(BaseMQTTMessage):
    _message_type = 0x0E

    @classmethod
    def ready_to_use(cls):
        obj = cls()
        return obj


class Publish(BaseMQTTMessage):
    _message_type = 0x03
    _message_fields = ('topic', 'id', 'payload')

    def _decode_data(self, _data):
        self.topic, l = MQTTUtils.decode_string(_data)
        cursor = l + 2

        if self.qos > MQTTConstants.AT_MOST_ONCE:
            self.id = MQTTUtils.decode_value(_data[cursor:cursor + 2])
            cursor += 2
        else:
            self.id = None

        self.payload = _data[cursor:]

    def _encode_data(self):
        buffer = bytearray()
        buffer.extend(MQTTUtils.encode_string(self.topic))

        if self.qos in [MQTTConstants.AT_LEAST_ONCE, MQTTConstants.EXACTLY_ONCE]:
            buffer.extend(MQTTUtils.encode_value(self.id))

        buffer.extend(self.payload)

        return bytes(buffer)

    def _extra_log_info(self):
        return ' DUP: %d, QOS: %d, RET: %d, ID: %#05d, LEN: %d' % (
            self.dup, self.qos, self.retain,
            self.id or 0,
            len(self.payload),
        )


class Subscribe(BaseMQTTMessage):
    _message_type = 0x08
    _message_fields = ('id', 'subscription_intents')

    _default_values = {
        'dup': False,
        'qos': 1,
        'retain': False,
    }

    QOS_PART_MASK = 0x03

    def _decode_data(self, _data):
        self.id = MQTTUtils.decode_value(_data[0:2])
        cursor = 2

        self.subscription_intents = []
        while cursor < self.length:
            topic, l = MQTTUtils.decode_string(_data[cursor:])
            cursor += l + 2

            qos = _data[cursor] & 0x03
            cursor += 1

            self.subscription_intents.append((topic, qos))

    def _encode_data(self):
        buffer = bytearray()
        buffer.extend(MQTTUtils.encode_value(self.id))

        for intent in self.subscription_intents:
            topic, qos = intent
            buffer.extend(MQTTUtils.encode_string(topic))
            buffer.append(MQTTUtils.encode_byte(qos) & self.QOS_PART_MASK)

        return bytes(buffer)

    def _extra_log_info(self):
        return ' ID: %#05d, RL: %s' % (
            self.id,
            ', '.join([str(l) for t, l in self.subscription_intents]) or '?',
        )

    @classmethod
    def generate_single_sub(cls, topic, qos):
        print("generating msg of type SUBSCRIBE")
        msg = Subscribe()
        intent = tuple((topic, qos))
        t, q = intent
        print("t,p: %s %d" % (t,q))
        msg.id = 444 # chosen by fair dice roll.
        msg.subscription_intents = []
        msg.subscription_intents.append(intent)
        for intent in msg.subscription_intents:
            print("LEARNING what is intent (cls):")
            print(intent.__class__)
            print(intent)
        # TODO remove overhead
        msg._update_raw_data() # i think that's it!
        byt = msg._encode_data()
        print("ENCODED raw data bytes and")
        print("SUBSCRIBE._raw_data:")
        print(byt)
        print(msg._raw_data)
        return msg


class Suback(BaseMQTTMessage):
    _message_type = 0x09
    _message_fields = ('id', 'payload')

    @property
    def granted_qos_list(self):
        return [int(b) for b in self.payload]

    @granted_qos_list.setter
    def granted_qos_list(self, value):
        self.payload = bytes(value)

    def _decode_data(self, _data):
        cursor = 0
        self.id = MQTTUtils.decode_value(_data[cursor:cursor + 2])
        cursor += 2

        self.payload = _data[cursor:]

    def _encode_data(self):
        buffer = bytearray()
        buffer.extend(MQTTUtils.encode_value(self.id))
        buffer.extend(self.payload)

        return bytes(buffer)

    @classmethod
    def from_subscribe(cls, subscribe_msg, granted_qos):
        assert isinstance(subscribe_msg, Subscribe)
        obj = cls()
        obj.id = subscribe_msg.id
        obj.granted_qos_list = granted_qos

        return obj

    def _extra_log_info(self):
        return ' ID: %#05d, GL: %s' % (
            self.id,
            ', '.join([str(x) for x in self.granted_qos_list]) or '?',
        )


class Unsubscribe(BaseMQTTMessage):
    _message_type = 0x0A
    _message_fields = ('id', 'unsubscribe_list')

    _default_values = {
        'dup': False,
        'qos': 1,
        'retain': False,
    }

    def _decode_data(self, _data):
        cursor = 0
        self.id = MQTTUtils.decode_value(_data[cursor:cursor + 2])
        cursor += 2

        self.unsubscribe_list = []
        while cursor < self.length:
            topic, l = MQTTUtils.decode_string(_data[cursor:])
            cursor += l + 2

            self.unsubscribe_list.append(topic)

    def _encode_data(self):
        buffer = bytearray()
        buffer.extend(self.id)

        for topic in self.unsubscribe_list:
            buffer.extend(MQTTUtils.encode_string(topic))

    def _extra_log_info(self):
        return ' ID: %#05d, LEN: %d' % (
            self.id,
            len(self.unsubscribe_list),
        )


class Unsuback(BaseMQTTMessage):
    _message_type = 0x0B
    _message_fields = ('id',)

    def _decode_data(self, _data):
        self.id = MQTTUtils.decode_value(_data[0:2])

    def _encode_data(self):
        return bytes(MQTTUtils.encode_value(self.id))

    @classmethod
    def from_unsubscribe(cls, unsubscribe_msg):
        assert isinstance(unsubscribe_msg, Unsubscribe)
        return cls(id=unsubscribe_msg.id)

    def _extra_log_info(self):
        return ' ID: %#05d' % self.id


class Pingreq(BaseMQTTMessage):
    _message_type = 0x0C

    @classmethod
    def ready_to_use(cls):
        return cls()


class Pingresp(BaseMQTTMessage):
    _message_type = 0x0D

    @classmethod
    def from_pingreq(cls, pingreq_msg):
        assert isinstance(pingreq_msg, Pingreq)
        return cls()


class Puback(BaseMQTTMessage):
    _message_type = 0x04
    _message_fields = ('id', )

    @classmethod
    def from_id(cls, id_):
        assert isinstance(id_, int)
        return cls(id=id_)

    @classmethod
    def from_publish(cls, pub_msg):
        assert isinstance(pub_msg, Publish)
        return cls(id=pub_msg.id)

    def _decode_data(self, _data):
        self.id = MQTTUtils.decode_value(_data[0:2])

    def _encode_data(self):
        return bytes(MQTTUtils.encode_value(self.id))

    def _extra_log_info(self):
        return ' ID: %#05d' % self.id


class Pubrec(Puback):
    _message_type = 0x05


class Pubrel(Puback):
    _message_type = 0x06

    _default_values = {
        'dup': False,
        'qos': 1,
        'retain': False,
    }

    @classmethod
    def from_pub(cls, pub_msg):
        assert isinstance(pub_msg, Publish) \
            or isinstance(pub_msg, Pubrec)
        return cls(id=pub_msg.id)


class Pubcomp(Puback):
    _message_type = 0x07

    @classmethod
    def from_pubrel(cls, pub_msg):
        assert isinstance(pub_msg, Pubrel)
        return cls(id=pub_msg.id)
