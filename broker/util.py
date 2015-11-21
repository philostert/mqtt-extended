import re
from hashlib import sha256

from broker import MQTTConstants


class MQTTUtils:
    def __init__(self):
        raise RuntimeError("One should not instantiate this class")

    @classmethod
    def is_length_field_complete(cls, length_bytes):
        b = length_bytes[-1]
        return not (b & 0x80) == 0x80

    @classmethod
    def encode_length(cls, length):
        encoded = bytearray()
        while True:
            digit = length % 128
            length //= 128
            if length > 0:
                digit |= 128

            encoded.append(digit)
            if length <= 0:
                break

        return encoded

    @classmethod
    def decode_length(cls, length_bytes):
        length = 0
        multiplier = 1
        field_size = 0

        for b in length_bytes:
            field_size += 1
            length += (b & 0x7F) * multiplier
            multiplier *= 0x80

            if (b & 0x80) != 0x80:
                break

        return length, field_size

    @classmethod
    def encode_byte(cls, value):
        return value & 0xFF

    @classmethod
    def encode_value(cls, value):
        encoded = bytearray()
        encoded.append(value >> 8)
        encoded.append(value & 0xFF)

        return encoded

    @classmethod
    def decode_value(cls, value_array):
        value = 0
        multiplier = 1
        for i in value_array[::-1]:
            value += i * multiplier
            multiplier <<= 8

        return value

    @classmethod
    def encode_string(cls, string):
        string = bytes(string, encoding="UTF-8")

        encoded = bytearray()
        encoded.append(len(string) >> 8)
        encoded.append(len(string) & 0xFF)
        for i in string:
            encoded.append(i)

        return encoded

    @classmethod
    def decode_string(cls, encodedString):
        length = 256 * encodedString[0] + encodedString[1]
        return str(encodedString[2:2+length], encoding="UTF-8"), int(length)

    @classmethod
    def strip_fixed_header(cls, msg):
        buffer = msg
        msg_type = (buffer[0] & 0xF0) >> 4
        dup = (buffer[0] & 0x08) == 0x08
        qos = (buffer[0] & 0x06) >> 1
        retain = (buffer[0] & 0x01) == 0x01
        length, field_size = MQTTUtils.decode_length(msg[MQTTConstants.MESSAGE_TYPE_LENGTH:])

        return msg_type, dup, qos, retain, length, buffer[MQTTConstants.MESSAGE_TYPE_LENGTH + field_size:]

    @classmethod
    def convert_to_ereg(cls, subscription_mask, allow_wildcards=False):
        if cls.subscription_is_valid(subscription_mask):
            ereg = "^%s$" % subscription_mask
            if allow_wildcards:
                ereg = re.sub("(/?)\+(/?)", "\g<1>([^\x00#/]+|\+|)\g<2>", ereg)
                ereg = re.sub("/#\$", "(/.*$|$)", ereg)
            else:
                ereg = re.sub("(/?)\+(/?)", "\g<1>([^\x00#+/]+|)\g<2>", ereg)
                ereg = re.sub("/#\$", "(/[^\x00#+]*$|$)", ereg)
            return ereg

    @classmethod
    def subscription_is_valid(cls, subscription_mask):
        pattern = "^(([^\x00#+/]+|\+|)(/[^\x00#+/]+|/\+|/)*(/#|/)?|#)$"
        return re.match(pattern, subscription_mask) is not None

    @classmethod
    def hash_message_bytes(cls, bytes_):
        """
        A custom hash function for raw messages. For small messages (less than
        64 bytes) it will return the byte sequence itself, for larger messages
        return the bytes' sha256 digest.
        """
        if len(bytes_) > 64:
            crypto = sha256()
            crypto.update(bytes_)
            return crypto.digest()

        return bytes_


class HaltObject():
    """
    A class which instances raises exception on any get/set/del or method call.
    The raised exception can be defined on init method.
    """
    def __init__(self, halt_exception_type=None, halt_message=''):
        if halt_exception_type is None:
            halt_exception_type = Exception
        else:
            assert issubclass(halt_exception_type, Exception)

        super(HaltObject, self).__setattr__('_exception', halt_exception_type)
        super(HaltObject, self).__setattr__('_message', halt_message)

    def __getattr__(self, name):
        raise self._exception(self._message)

    def __setattr__(self, name, value):
        raise self._exception(self._message)

    def __delattr__(self, name):
        raise self._exception(self._message)
