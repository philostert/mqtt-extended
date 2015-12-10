import mosquitto
from threading import Thread


class MQTTTestUtils():
    @staticmethod
    def loop_and_check_callback_thread(mosquitto_client, callback=None, times=0):
        def _fcn():
            assert isinstance(mosquitto_client, mosquitto.Mosquitto)

            while not mosquitto_client.loop():
                if callback is not None:
                    if getattr(mosquitto_client, callback).call_count >= times:
                        mosquitto_client.disconnect()

        return Thread(target=_fcn, daemon=True)