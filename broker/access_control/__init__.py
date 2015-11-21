from logging import getLogger
import re
from tornado import gen
from broker.util import MQTTUtils


class NoAuthentication():
    def __init__(self):
        self.logger = getLogger('access_control.authentication.none')

    @gen.coroutine
    def authenticate(self, client_id, username, password):
        return Authorization.no_restrictions()


class SinglePasswordAuthentication():
    def __init__(self, password):
        self.logger = getLogger('access_control.authentication.none')
        self.password = password

    @gen.coroutine
    def authenticate(self, client_id, username, password):
        if password == self.password:
            return Authorization.no_restrictions()
        else:
            self.logger.debug('client:%s user:%s auth error' %
                              (client_id, username))
            return Authorization.denied()



class Authorization():
    ALL = '*'
    NONE = []

    def __init__(self, allowed_publish_masks, allowed_subscription_masks):
        self._validate_authorization_entry(allowed_publish_masks)
        self._validate_authorization_entry(allowed_subscription_masks)

        self.allowed_publish_masks = allowed_publish_masks
        self.allowed_subscription_masks = allowed_subscription_masks

    def _validate_authorization_entry(self, ts):
        """
        Validates an authorization entry
        :param ts: authorization entry: an asterisk string `"*"` meaning
        fully authorized, or a list of (topic str, topic ereg)
        :type ts: str | list[(str, ereg)]
        :return:
        """

        if ts == self.ALL:
            pass

        elif isinstance(ts, list):
            for t, ereg in ts:
                assert isinstance(t, str)
                assert hasattr(ereg, 'match')

        else:
            raise ValueError('authorization has unexpected format')

    def is_subscription_allowed(self, topic):
        if self.allowed_subscription_masks == Authorization.ALL:
            return True

        for t, ereg in self.allowed_subscription_masks:
            if ereg.match(topic):
                return True

        return False

    def is_publish_allowed(self, topic):
        if self.allowed_publish_masks == Authorization.ALL:
            return True

        for t, ereg in self.allowed_publish_masks:
            if ereg.match(topic):
                return True

        return False

    def is_connection_allowed(self):
        return len(self.allowed_publish_masks) > 0 or \
            len(self.allowed_subscription_masks) > 0

    def is_fully_authorized(self):
        return self.allowed_publish_masks == self.ALL \
            and self.allowed_subscription_masks == self.ALL

    @classmethod
    def no_restrictions(cls):
        return cls(cls.ALL, cls.ALL)

    @classmethod
    def denied(cls):
        return cls(cls.NONE, cls.NONE)

    @classmethod
    def from_dict(cls, obj):
        """
        Expected format:
            {
                "publish": ["example/weather-stations/F83A5D/#", ...],
                "subscribe": ["example/weather-server/status", ...]
            }
        """
        if 'publish' in obj:
            publish = cls._clear_authorization_entry(obj['publish'])
        else:
            publish = cls.NONE

        if 'subscribe' in obj:
            subscribe = cls._clear_authorization_entry(obj['subscribe'],
                                                       allow_wildcards=True)
        else:
            subscribe = cls.NONE

        return cls(publish, subscribe)

    @classmethod
    def _clear_authorization_entry(cls, ts, allow_wildcards=False):
        """
        Validates an authorization entry
        :param ts: authorization entry: an asterisk string `'*'` meaning
        fully authorized, or a list of strings (topics, wildcards allowed)
        :type ts: str | list[str]
        :return:
        """

        if ts == cls.ALL:
            return ts

        elif isinstance(ts, list):
            rs = []
            for t in ts:
                assert isinstance(t, str)
                ereg = MQTTUtils.convert_to_ereg(t,
                        allow_wildcards=allow_wildcards)
                assert isinstance(ereg, str)
                rs.append((t, re.compile(ereg)))

            return rs

        else:
            raise ValueError('authorization has unexpected format')


from .file import FileAuthentication
from .web import WebAuthentication
