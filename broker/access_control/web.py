import json
from logging import getLogger
from tornado import gen
from broker.access_control import Authorization


class WebAuthentication():
    def __init__(self, authentication_address):
        self.logger = getLogger('access_control.authentication.web')
        self.url = authentication_address

        import tornado.httpclient
        self.httpclient = tornado.httpclient

        from urllib.parse import urlencode
        self.urlencode = urlencode

    @gen.coroutine
    def _request_authorization(self, client_id, username, password):
        try:
            payload = self.urlencode({
                'clientid': client_id,
                'username': username,
                'password': password
            }).encode('utf-8')

            request = self.httpclient.HTTPRequest(url=self.url, method="POST",
                                                  headers=None, body=payload)

            response = yield self.httpclient.AsyncHTTPClient().fetch(request)

            assert isinstance(response, self.httpclient.HTTPResponse)
            if response.code == 200:
                return response.body
            else:
                self.logger.error('error authenticating user:%s - '
                                  'webserver returned unexpected status %s' %
                                  (username, response.code))
                return None
        except self.httpclient.HTTPError:
            self.logger.error('error authenticating user:%s' % username,
                              exc_info=True)
            return None

    @gen.coroutine
    def authenticate(self, client_id, username, password):
        self.logger.debug('authenticating client:%s user:%s' %
                          (client_id, username))
        result = yield self._request_authorization(client_id, username, password)
        if result:
            return self.make_authorization(username, result)
        else:
            return Authorization.denied()

    def make_authorization(self, username, auth_text):
        """
        Expects an authorization json object as follows:
            {
                "publish": ["example/weather-stations/F83A5D/#", ...],
                "subscribe": ["example/weather-server/status", ...]
            }

        Strings in publish and subscribe arrays can and should follow MQTT's
        topic specification. Wildcards are allowed.

        The value of `publish` and `subscribe` fields can also be `"*"`,
        meaning full authorization. If an empty list is passed, no
        authorization is granted.

        :param string auth_text:
        :return: an Authorization object
        :rtype: Authorization
        """
        try:
            if isinstance(auth_text, bytes):
                auth_text = auth_text.decode('utf-8')
            assert isinstance(auth_text, str)
            return Authorization.from_dict(json.loads(auth_text))
        except:
            self.logger.error('error parsing authorizations for user:%s' %
                              username,
                              exc_info=True)
            return None


