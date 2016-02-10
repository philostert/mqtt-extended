package mypackage;

import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.MqttCallback;
import org.eclipse.paho.client.mqttv3.MqttMessage;

public class CallBackTest implements MqttCallback {

	public CallBackTest() {
	}

	@Override
	public void connectionLost(Throwable cause) {

	}

	@Override
	public void messageArrived(String topic, MqttMessage message) throws Exception {
		System.out.println(
				"Topic: " + topic + " QoS: " + message.getQos() + " Message: " + new String(message.getPayload(), "UTF-8"));

	}

	@Override
	public void deliveryComplete(IMqttDeliveryToken token) {

	}

}
