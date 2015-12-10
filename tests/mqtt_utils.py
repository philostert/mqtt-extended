from unittest import TestCase
import re
from redis import StrictRedis
from broker.persistence.redis_types import RedisHashDict

from broker.util import MQTTUtils


class TestMQTTUtils(TestCase):
    def test_valid_subscription_masks(self):
        masks = (
            '',
            '#',
            'foo/#',
            '1/data/#',
            '1/control/user/2',
            '1/control/user/+',
            '1/control/+/2',
            '+/control/+/2',
            '+/control/+/#',
            '1/control/devices/wtcsctnfZ-1-2',
            '+',
            '+/',
            '+/#',
            '+/+',
            '+/+/',
            '+/+/#',
            '/+',
            '/+/+',
            '/+/+/#',
            'sport/tennis/player1',
            'sport/tennis/player1/ranking',
            'sport/tennis/player1/score/wimbledon',
            'sport/#',
            'sport/tennis/#',
            '+/tennis/#',
            'sport/+/player1',
            'sport/+/player1/#',
            '/',
            '//',
            '+//',
            '/+/',
            '//+',
            '/#',
            '//#',
            '+//#',
            '/+/#',
            '//+/#',
        )

        for mask in masks:
            self.assertTrue(MQTTUtils.subscription_is_valid(mask), "%s is invalid" % mask)

    def test_invalid_subscription_masks(self):
        masks = (
            '##',
            '++',
            '#/',
            '/#/+',
            '+#', '#+',
            '+#/', '#+/',
            '/+#', '/#+',
            'sports+',
            'sports#',
            '+sports',
            '#sports',
            'sports/#/',
            'sport/tennis#', 'sport#/tennis',
            '#sport/tennis', 'sport/#tennis',
            'sport/tennis+', 'sport+/tennis',
            'sport/+tennis', '+sport/tennis',
            '++/sport/tennis', 'sport/++/tennis', 'sport/tennis/++',
            '+++/sport/tennis', 'sport/+++/tennis', 'sport/tennis/+++',
            'sport/tennis/#/ranking',
            'sport/tennis/##/ranking',
            '#/sport/tennis/ranking',
            '##/sport/tennis/ranking',
            'sport/tennis/ranking/##',
            'sport/tennis/ranking/##/',
        )

        for mask in masks:
            self.assertFalse(MQTTUtils.subscription_is_valid(mask), "%s is valid" % mask)

    def test_substring_doesnt_match(self):
        super = "/foo/bar"
        sub = "/foo/ba"

        sub_ereg = MQTTUtils.convert_to_ereg(sub)

        self.assertTrue(re.match(sub_ereg, sub) is not None)
        self.assertTrue(re.match(sub_ereg, super) is None)

        ereg = MQTTUtils.convert_to_ereg('foo/bar')
        self.assertIsNotNone(re.match(ereg, 'foo/bar'))

        self.assertIsNone(re.match(ereg, 'foo/bar/'))
        self.assertIsNone(re.match(ereg, '/foo/bar'))
        self.assertIsNone(re.match(ereg, 'foo//bar'))

        self.assertIsNone(re.match(ereg, 'foo/bar/buzz'))
        self.assertIsNone(re.match(ereg, 'buzz/foo/bar'))
        self.assertIsNone(re.match(ereg, 'foo/buzz/bar'))

    def test_multilevel_match(self):
        sub = "foo/bar/#"
        sub_ereg = MQTTUtils.convert_to_ereg(sub)
        self.assertIsNone(re.match(sub_ereg, 'foo/b'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo/bar'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo/bar/'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo/bar/one'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo/bar/one/'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo/bar/one/two'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo/bar/one/two/'))

        self.assertIsNone(re.match(sub_ereg, 'foo/bar/#'))
        self.assertIsNone(re.match(sub_ereg, 'foo/bar/+'))
        self.assertIsNone(re.match(sub_ereg, 'foo/bar/+/'))
        self.assertIsNone(re.match(sub_ereg, 'foo/bar/+/#'))

    def test_single_level_match(self):
        sub_ereg = MQTTUtils.convert_to_ereg("foo/+/bar")

        self.assertIsNotNone(re.match(sub_ereg, 'foo/buzz/bar'))
        self.assertIsNotNone(re.match(sub_ereg, 'foo//bar'))

        self.assertIsNone(re.match(sub_ereg, 'foo/bar'))
        self.assertIsNone(re.match(sub_ereg, 'foo/bar/'))
        self.assertIsNone(re.match(sub_ereg, '/foo/bar'))
        self.assertIsNone(re.match(sub_ereg, 'foo/one/two/bar'))
        self.assertIsNone(re.match(sub_ereg, 'foo/one/bar/'))
        self.assertIsNone(re.match(sub_ereg, '/foo/one/bar'))
        self.assertIsNone(re.match(sub_ereg, 'foo/+/bar'))

        ereg = MQTTUtils.convert_to_ereg('foo/bar/+')
        self.assertIsNotNone(re.match(ereg, 'foo/bar/buzz'))
        self.assertIsNotNone(re.match(ereg, 'foo/bar/'))

        self.assertIsNone(re.match(ereg, 'foo/bar/+'))
        self.assertIsNone(re.match(ereg, 'foo/bar/#'))
        self.assertIsNone(re.match(ereg, 'foo/bar/+/'))
        self.assertIsNone(re.match(ereg, 'foo/bar/+/#'))

        ereg = MQTTUtils.convert_to_ereg('+/foo/bar')
        self.assertIsNotNone(re.match(ereg, 'buzz/foo/bar'))
        self.assertIsNotNone(re.match(ereg, '/foo/bar'))

        self.assertIsNone(re.match(ereg, 'foo/bar'))
        self.assertIsNone(re.match(ereg, '//foo/bar'))

    def test_mixed_match(self):
        ereg = MQTTUtils.convert_to_ereg('foo/+/bar/#')
        self.assertIsNotNone(re.match(ereg, 'foo/xyz/bar'))
        self.assertIsNotNone(re.match(ereg, 'foo/xyz/bar/'))
        self.assertIsNotNone(re.match(ereg, 'foo/xyz/bar/abc'))
        self.assertIsNotNone(re.match(ereg, 'foo//bar'))
        self.assertIsNotNone(re.match(ereg, 'foo//bar/'))
        self.assertIsNotNone(re.match(ereg, 'foo//bar/abc'))

        self.assertIsNone(re.match(ereg, 'foo/bar'))
        self.assertIsNone(re.match(ereg, 'foo/#'))
        self.assertIsNone(re.match(ereg, 'foo/+/bar'))
        self.assertIsNone(re.match(ereg, 'foo/+/bar/#'))
        self.assertIsNone(re.match(ereg, 'foo/+/bar/abc'))
        self.assertIsNone(re.match(ereg, 'foo/+/bar/abc/'))
        self.assertIsNone(re.match(ereg, 'foo/+/bar/abc/#'))
        self.assertIsNone(re.match(ereg, 'foo/+/bar/+/#'))
        self.assertIsNone(re.match(ereg, 'foo/xyz/bar/#'))
        self.assertIsNone(re.match(ereg, 'foo/xyz/bar/+'))
        self.assertIsNone(re.match(ereg, 'foo/xyz/bar/+/#'))


class TestSubscriptionAuthorization(TestCase):
    def assertIsMatch(self, x, y):
        """
        Client is authorized to subscribe on `x` and tries to subscribe
        or publish on `y`. `x` should match `y`.
        """
        self.assertIsNotNone(re.match(x, y), '%s should match %s' % (x, y))

    def assertIsNotMatch(self, x, y):
        """
        Client is authorized to subscribe on `x` and tries to subscribe
        or publish on `y`. `x` should not match `y`.
        """
        self.assertIsNone(re.match(x, y), '%s should not match %s' % (x, y))

    def test_multi_level_mask(self):
        """
        tests for access_control.Authorization.is_subscription_allowed
        """
        multi_level = MQTTUtils.convert_to_ereg('foo/bar/#', allow_wildcards=True)

        self.assertIsMatch(multi_level, 'foo/bar')
        self.assertIsMatch(multi_level, 'foo/bar/')
        self.assertIsMatch(multi_level, 'foo/bar//')
        self.assertIsMatch(multi_level, 'foo/bar/#')

        self.assertIsMatch(multi_level, 'foo/bar/+')
        self.assertIsMatch(multi_level, 'foo/bar/+/')
        self.assertIsMatch(multi_level, 'foo/bar/+/#')

        self.assertIsMatch(multi_level, 'foo/bar/buzz/+/#')
        self.assertIsMatch(multi_level, 'foo/bar/fuzz/+/buzz/#')

    def test_single_level_mask(self):
        single_level = MQTTUtils.convert_to_ereg('foo/+/bar', allow_wildcards=True)
        self.assertIsMatch(single_level, 'foo/+/bar')
        self.assertIsMatch(single_level, 'foo/buzz/bar')
        self.assertIsMatch(single_level, 'foo//bar')

        self.assertIsNotMatch(single_level, 'foo/bar')

    def test_mixed_masks(self):
        mixed = MQTTUtils.convert_to_ereg('foo/+/bar/#', allow_wildcards=True)
        self.assertIsMatch(mixed, 'foo/+/bar')
        self.assertIsMatch(mixed, 'foo/+/bar/#')
        self.assertIsMatch(mixed, 'foo/+/bar/buzz')
        self.assertIsMatch(mixed, 'foo/+/bar/buzz/')
        self.assertIsMatch(mixed, 'foo/+/bar/buzz/#')
        self.assertIsMatch(mixed, 'foo/+/bar/+/#')
        self.assertIsMatch(mixed, 'foo/+/bar/+/+/#')
        self.assertIsMatch(mixed, 'foo/buzz/bar')
        self.assertIsMatch(mixed, 'foo/buzz/bar/')
        self.assertIsMatch(mixed, 'foo/buzz/bar/+')
        self.assertIsMatch(mixed, 'foo/buzz/bar/#')
        self.assertIsMatch(mixed, 'foo/buzz/bar/+/')
        self.assertIsMatch(mixed, 'foo/buzz/bar/+/#')

        self.assertIsNotMatch(mixed, 'foo/#')
        self.assertIsNotMatch(mixed, 'foo/+/#')
        self.assertIsNotMatch(mixed, 'foo/+/+/#')


class TestRedisHashDict(TestCase):
    def setUp(self):
        self.redis = StrictRedis()
        self.redis.delete('foobar')
        self.dict = RedisHashDict(self.redis, 'foobar')

    def test_items(self):
        self.dict[b'foo'] = b'bar'
        self.dict[b'bob'] = b'alice'

        truth = (b'foo', b'bar'), (b'bob', b'alice')

        for item in self.dict.items():
            self.assertIn(item, truth)
