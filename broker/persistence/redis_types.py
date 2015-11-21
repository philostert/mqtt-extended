from collections import UserDict
from redis import StrictRedis
from toro import Queue


class RedisQueue(Queue):

    def __init__(self, key, maxsize=0, io_loop=None, redis_obj=None):
        super().__init__(maxsize, io_loop)
        self.redis = redis_obj
        self.key = key
        self._size = None

    def _init(self, maxsize):
        pass

    def _get(self):
        assert isinstance(self.redis, StrictRedis)
        if self.qsize() > 0:
            item = self.redis.rpop(self.key)
            self._size = self.qsize() - 1 if item is not None else None

            return item

        else:
            return None

    def _put(self, item):
        assert isinstance(self.redis, StrictRedis)
        if self.redis.lpush(self.key, item) > 0:
            self._size = None

    def qsize(self):
        if self._size is None:
            self._size = self.redis.llen(self.key)

        return self._size

    def empty(self):
        return self.qsize() == 0

    @property
    def queue(self):
        # I know it stinks, but toro uses *assert not self.queue* to check if
        # the queue is not empty...
        return not self.empty()

    def clear(self):
        self.redis.delete(self.key)


class RedisHashDict(UserDict):
    def __init__(self, redis, hash_name):
        assert isinstance(redis, StrictRedis)
        super().__init__()
        self.redis = redis
        self.name = hash_name

    def __contains__(self, key):
        return self.redis.hexists(self.name, key)

    def __len__(self):
        return self.redis.hlen(self.name)

    def __getitem__(self, key):
        value = self.redis.hget(self.name, key)

        if value is not None:
            return value

        raise KeyError(key)

    def __setitem__(self, key, value):
        return self.redis.hset(self.name, key, value)

    def __delitem__(self, key):
        return self.redis.hdel(self.name, key)

    def items(self):
        for k, v in self.redis.hscan_iter(self.name):
            yield (k, v)

    def keys(self):
        yield from self.redis.hkeys(self.name)

    def values(self):
        yield from self.redis.hvals(self.name)


class RedisList():
    def __init__(self, redis, key):
        self.redis = redis
        self.key = key

    def append(self, value):
        self.redis.rpush(self.key, value)

    def remove(self, value):
        self.redis.lrem(self.key, 1, value)

    def items(self):
        for x in self.redis.lscan_iter(self.key):
            yield self._decode(x)

    def pop(self):
        return self._decode(self.redis.lpop(self.key))

    def __getitem__(self, k):
        return self.redis.lindex(self.key, k)

    def __iter__(self):
        for i in range(len(self)):
            yield self.redis.lindex(self.key, i)

    def __contains__(self, item):
        # preferable to not use this
        for x in self:
            if self._decode(x) == item:
                return True

        return False

    def __len__(self):
        return self.redis.llen(self.key)

    def _decode(self, val):
        # override to decode items retrieved from redis
        return val


class RedisIntList(RedisList):
    def _decode(self, val):
        return int(val)


class RedisSet():
    def __init__(self, redis, key):
        self.redis = redis
        self.key = key

    def add(self, value):
        self.redis.sadd(self.key, value)

    def remove(self, value):
        self.redis.srem(self.key, value)

    def items(self):
        for x in self.redis.sscan_iter(self.key):
            yield self._decode(x)

    def __iter__(self):
        return iter(self.items())

    def __len__(self):
        return self.redis.scard(self.key)

    def __contains__(self, item):
        return self.redis.sismember(self.key, item)

    def _decode(self, val):
        # override to decode items retrieved from redis
        return val


class RedisUnicodeSet(RedisSet):
    def _decode(self, val):
        return val.decode("utf-8") if val else val


class RedisIntSet(RedisSet):
    def _decode(self, val):
        return int(val) if val else val
