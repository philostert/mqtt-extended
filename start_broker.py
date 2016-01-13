#!/usr/bin/env python

from tornado.options import parse_command_line, options, define
from tornado.ioloop import IOLoop
import signal
from logging import getLogger
from broker.access_control import SinglePasswordAuthentication, NoAuthentication, FileAuthentication, WebAuthentication
from broker.persistence import InMemoryPersistence, RedisPersistence

from broker.server import MQTTServer
from paho.mqtt.paho_partner_pair import Paho_Partner_Pair

define('rhost', 'localhost', str, "Redis host address")
define('rport', 6379, int, "Redis host port")
define('rpassword', None, str, "Redis password")
define('redis', False, bool, "Use redis as queue backend")

define('ssl', False, bool, "Use SSL/TLS on socket")
define('sslkey', None, str, "SSL/TLS Key file path")
define('sslcert', None, str, "SSL/TLS Certificate file path")

define('authfile', None, str, "Authentication and authorization config file path")
define('webauth', None, str, "Authentication and authorization web API address")
define('password', None, str, "Password for client authentication")


class OsSignalHandler():
    def __init__(self, log):
        self.log = log
        self.servers = list()

        # handle interrupts
        signal.signal(signal.SIGINT, self.handle_signal)
        # Handle unix kill command
        signal.signal(signal.SIGTERM, self.handle_signal)

    def add(self, server):
        self.servers.append(server)

    def handle_keyboard_interrupt(self):
        self._beautifully_exit()

    def handle_signal(self, *args):
        self._beautifully_exit()

    def _beautifully_exit(self):
        """ Handles client disconnection before stopping the broker. """
        print("Disconnecting clients")
        self.log.info('disconnecting clients')

        for server in self.servers:
            server.disconnect_all_clients()

        IOLoop.instance().stop()


def create_redis_persistence(options, log):
    import redis
    redis_client = redis.StrictRedis(
        host=options.rhost,
        port=options.rport,
        password=options.rpassword
    )

    print("[option] Using redis at (%s, %d)" %
          (options.rhost, options.rport))
    log.info("[option] Using redis at (%s, %d)" %
          (options.rhost, options.rport))

    return RedisPersistence(redis_client)


def create_ssl_options(options):
    if options.sslkey and options.sslcert:
        import ssl
        ssl_options = {
            "ssl_version": ssl.PROTOCOL_TLSv1,
            "cert_reqs": ssl.CERT_NONE,
            "keyfile": options.sslkey, 
            "certfile": options.sslcert,
        }
        print("[option] Using SSL/TLS")

    else:
        print("[option] To use SSL/TLS both sslkey and sslcert must be defined")
        ssl_options = None

    return ssl_options


def start_mqtt_server(persistence, clients,
                      authentication_agent, log):
    EXTERNAL_ADDRESS = "test.mosquitto.org"

    server = MQTTServer(authentication=authentication_agent,
                        persistence=persistence,
                        clients=clients,
                        ssl_options=None)
    ppp = Paho_Partner_Pair()
    server.listen(1883)
    ppp.connect(EXTERNAL_ADDRESS)
    print("listening port 1883")
    log.info("listening port 1883")

    return server


def start_secure_mqtt_server(persistence, clients,
                             authentication_agent, log):
    ssl_options = create_ssl_options(options)

    server = MQTTServer(authentication=authentication_agent,
                        persistence=persistence,
                        clients=clients,
                        ssl_options=ssl_options)

    server.listen(8883)
    print("listening port 8883")
    log.info("listening port 8883")

    return server


def get_persistence(options, log):
    if options.redis:
        log.info('persistence: redis')
        return create_redis_persistence(options, log)
    else:
        log.info('persistence: memory')
        return InMemoryPersistence()


def get_authentication_agent(options, log):
    if options.authfile is not None:
        print("auth: file")
        log.info("authentication agent: file authentication")
        return FileAuthentication(options.authfile)

    elif options.webauth is not None:
        print("auth: web")
        log.info("authentication agent: web authentication")
        return WebAuthentication(options.webauth)

    elif options.password is not None:
        print("auth: single pw authentication")
        log.info("authentication agent: single password authentication")
        return SinglePasswordAuthentication(options.password)

    else:
        print("auth: no authentication")
        log.info("authentication agent: no authentication")
        return NoAuthentication()


def main():
    log = getLogger('activity.broker')
    log.info('starting broker')

    persistence = get_persistence(options, log)
    authentication_agent = get_authentication_agent(options, log)

    signal_handler = OsSignalHandler(log)

    clients = dict()

    log.info('starting server')
    server = start_mqtt_server(persistence, clients,
                               authentication_agent, log)

    signal_handler.add(server)

    if options.ssl:
        print("starting secure server")
        log.info('starting secure server')
        sserver = start_secure_mqtt_server(persistence, clients,
                                           authentication_agent,
                                           log)

        signal_handler.add(sserver)

    else:
        sserver = None

    try:
        print("MQTT-Broker Started")
        log.info('broker started')
        IOLoop.instance().start()

    except KeyboardInterrupt:
        signal_handler.handle_keyboard_interrupt()

    print("MQTT-Broker Stopped")
    log.info('broker stopped')

parse_command_line()
main()

