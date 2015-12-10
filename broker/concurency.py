import toro


_no_exception = object()


class AsyncResult(toro.AsyncResult):
    """
    `toro.AsyncResult` with exception raising
    """

    def __init__(self, io_loop=None):
        super(AsyncResult, self).__init__(io_loop)
        self.exception = _no_exception

    def __str__(self):
        if self.error():
            return '<%s exception=%r>' % (self.__class__.__name__, self.exception)
        else:
            return super(AsyncResult, self).__str__()

    def set_exception(self, exception):
        """Set an exception and wake up all the waiters."""
        if self.ready():
            raise toro.AlreadySet

        self.exception = exception
        waiters, self.waiters = self.waiters, []
        for waiter in waiters:
            if not waiter.done():  # Might have timed out
                waiter.set_exception(exception)

    def error(self):
        return self.exception is not _no_exception

    def ready(self):
        if self.error():
            return True

        return super(AsyncResult, self).ready()

    def get_nowait(self):
        """
        Get the value if ready, re-raise the exception raised by the
        co-routine, or raise :class:`toro.NotReady`.
        """
        if self.error():
            raise self.exception
        elif self.ready():
            return self.value
        else:
            raise toro.NotReady


class Queue(toro.Queue):
    def cancel(self):
        """
        Cancel all blocked futures.
        :return:
        """
        for fut in self.getters:
            fut.set_exception(CancelledException("Cancel requested"))
        for item, fut in self.putters:
            fut.set_exception(CancelledException("Cancel requested"))

    def clear(self):
        self.queue.clear()


class CancelledException(Exception):
    pass


class DummyFuture():
    def done(self):
        return True

    def set_result(self, *args, **kwargs):
        raise RuntimeError('cannot set result on dummy future')

    def set_exception(self, ex):
        raise RuntimeError('cannot set exception on dummy future')
