from datetime import timedelta
import logging

from tornado import gen
from tornado.ioloop import IOLoop

from broker import MQTTConstants

from broker.concurency import AsyncResult
from broker.messages import BaseMQTTMessage
from broker.util import MQTTUtils, HaltObject


logger = logging.getLogger('activity.connections')


class MQTTConnection():
    def __init__(self, stream, address):
        self._stream = stream
        self._address = address

        self._timeout_callback = None
        self._timeout_callback_fcn = None
        self._timeout = None
        self._timeout_max_interval = 3600

        self._read_async_result = None

        self._on_close_callback_fcn = None
        self._stream.set_close_callback(self._on_close_callback)

    @property
    def is_readable(self):
        return not self.halted() and \
            (not self.closed() or self.read_data_available())

    def halted(self):
        return isinstance(self._stream, HaltObject)

    def closed(self):
        try:
            return self._stream.closed()
        except MQTTConnectionClosed:
            return True

    def close(self):
        try:
            self.set_close_callback(None)
            self.set_timeout_callback(None)

            self._remove_timeout()

            self._stream.close()
            self._stream = HaltObject(MQTTConnectionClosed, 'stream closed')

            self._stop_reading()

        except MQTTConnectionClosed:
            # already closed / interrupted
            pass

    def set_close_callback(self, callback):
        self._on_close_callback_fcn = callback

    def set_timeout_callback(self, callback):
        self._timeout_callback_fcn = callback
        if callback is None:
            self._remove_timeout()

    def set_timeout(self, seconds):
        assert isinstance(seconds, int)
        self._timeout = seconds if seconds > 0 else None

    def closed_due_error(self):
        return self._stream.error is None

    def read_bytes_async(self, num_bytes):
        """
        Read bytes from `self._stream` with timeout.
        If there is result within the time limit, the Future returns the value.
        Otherwise the Future raises toro.Timeout.
        :param num_bytes: int
        :return: Bytes read from stream (as a Future)
        :rtype: Future
        """
        self._read_async_result = AsyncResult()

        def callback(r):
            if not self._read_async_result.ready():
                self._read_async_result.set(r)
            elif self._read_async_result.exception:
                # an exception was sat and the getter will raise it later
                pass
            else:
                logger.error('attempting to set _read_async_result twice')

        self._stream.read_bytes(num_bytes, callback=callback)
        return self._read_async_result.get(self._get_next_timeout())

    def read_data_available(self):
        return self._stream._read_buffer_size > 0

    @gen.coroutine
    def read_message(self):
        buffer = bytearray()
        chunk = yield self.read_bytes_async(MQTTConstants.MESSAGE_FIXED_HEADER_MINIMUM_SIZE)
        buffer.extend(chunk)

        while not MQTTUtils.is_length_field_complete(buffer[MQTTConstants.MESSAGE_TYPE_LENGTH:]):
            chunk = yield self.read_bytes_async(1)
            buffer.extend(chunk)

        msg_length, field_size = MQTTUtils.decode_length(buffer[MQTTConstants.MESSAGE_TYPE_LENGTH:])

        if msg_length > 0:
            chunk = yield self.read_bytes_async(msg_length)
            buffer.extend(chunk)

        self._update_timeout()
        return bytes(buffer)

    def _stop_reading(self):
        if self._read_async_result is not None and \
                not self._read_async_result.ready():
            self._read_async_result.set_exception(MQTTConnectionClosed('Stop requested'))

    @gen.coroutine
    def write_message(self, msg):
        assert isinstance(msg, BaseMQTTMessage)
        yield gen.Task(self._stream.write, msg.raw_data)

    def _remove_timeout(self):
        if self._timeout_callback is not None:
            IOLoop.instance().remove_timeout(self._timeout_callback)
            self._timeout_callback = None

    def _update_timeout(self):
        self._remove_timeout()
        if not self.closed():
            timeout = self._get_next_timeout()
            self._timeout_callback = IOLoop.instance().add_timeout(timeout, self._on_connection_timeout)

    def _get_next_timeout(self):
        if self._timeout is not None and self._timeout > 0:
            timeout = min(self._timeout, self._timeout_max_interval) * 1.5
        else:
            timeout = self._timeout_max_interval * 1.5

        return timedelta(seconds=timeout)

    def _on_connection_timeout(self):
        self.close()

        if callable(self._timeout_callback_fcn):
            self._timeout_callback_fcn(self)

    def _on_close_callback(self):
        self._remove_timeout()

        if callable(self._on_close_callback_fcn):
            self._on_close_callback_fcn(self)


class MQTTConnectionClosed(Exception):
    def __init__(self, msg):
        super(MQTTConnectionClosed, self).__init__(msg)
