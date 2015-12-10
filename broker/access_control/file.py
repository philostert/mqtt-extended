import json
from logging import getLogger
from tornado import gen
from broker.access_control import Authorization


class FileAuthentication():
    def __init__(self, authentication_file_path):
        self.logger = getLogger('access_control.authentication.file')
        self.url = authentication_file_path

        try:
            self.auth = parse_auth_file(self._read_auth_file(authentication_file_path))
        except:
            self.logger.error(u'error reading auth file at ' + authentication_file_path)
            raise

    def _read_auth_file(self, path):
        with open(path, encoding='utf-8') as f:
            r = json.load(f)
        return r

    @gen.coroutine
    def authenticate(self, client_id, username, password):
        self.logger.debug('authenticating client:%s user:%s' %
                          (client_id, username))
        if username in self.auth and self.auth[username].check_pw(password):
            return self.auth[username].authorization
        else:
            return Authorization.denied()


def parse_auth_file(obj, use_bcrypt=True):
    """
    Expected format:
        [
            {
                "username": "john_doe",
                "password": "???",
                "publish": ["example/weather-stations/F83A5D/#", ...],
                "subscribe": ["example/weather-server/status", ...]
            }, ...
        ]
    """
    assert isinstance(obj, list)

    password_checker = Bcrypt() if use_bcrypt else PlainPassword()
    r = {}

    for item in obj:
        auth = Authentication.from_dict(item, password_checker)
        r[auth.username] = auth

    return r


class Authentication():
    def __init__(self, username, password, authorization=None, pwcheck=None):
        self.username = username
        self.password = password
        self.authorization = authorization
        self.password_checker = pwcheck

    def check_pw(self, password):
        return self.password_checker.checkpw(password, self.password)

    @classmethod
    def from_dict(cls, item, pwcheck=None):
        assert 'username' in item
        assert 'password' in item
        authorization = Authorization.from_dict(item)
        return cls(item['username'], item['password'], authorization, pwcheck)


class Bcrypt():
    def __init__(self):
        import bcrypt
        self.bcrypt = bcrypt

    def hashpw(self, password, rounds=12):
        if isinstance(password, str):
            password = bytes(password, 'utf-8')
        assert isinstance(password, bytes)
        return self.bcrypt.hashpw(password, self.bcrypt.gensalt(rounds)).decode('utf-8')

    def checkpw(self, password, hashed):
        if isinstance(password, str):
            password = bytes(password, 'utf-8')
        if isinstance(hashed, str):
            hashed = bytes(hashed, 'utf-8')
        assert isinstance(password, bytes)
        assert isinstance(hashed, bytes)
        return self.bcrypt.hashpw(password, hashed) == hashed


class PlainPassword():
    def checkpw(self, password, plain):
        return password == plain
