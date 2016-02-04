package mypackage;

import java.util.ArrayList;

import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.MqttCallback;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;

public class TestWildCard_Subscription {
	private static Randomizer ran;
	private static MemoryPersistence persistence;
	private static String topic;
	private static String content;
	private static int qos;
	private static String broker;
	private static String clientId;
	private static MqttClient sampleClient;
	private MqttMessage message;
	private static ArrayList<String> messageList;
	private static CallBackTest cbt;

	public static void Main(String[] args) {
		ran = new Randomizer();
		messageList = new ArrayList<>();
		topic = "MQTT Examples";
		content = "Message from MqttPublishSample";
		qos = 2;
		clientId = "JustATestProgram";
		persistence = new MemoryPersistence();
		cbt = new CallBackTest();
		try {
			sampleClient = new MqttClient(broker, clientId, persistence);
			MqttConnectOptions connOpts = new MqttConnectOptions();
			connOpts.setCleanSession(true);
			System.out.println("Connecting to broker: " + broker);
			sampleClient.connect(connOpts);
			sampleClient.setCallback(cbt);
			System.out.println("Connected");
			sampleClient.subscribe("#");
		} catch (MqttException e) {
			System.out.println("reason " + e.getReasonCode());
			System.out.println("msg " + e.getMessage());
			System.out.println("loc " + e.getLocalizedMessage());
			System.out.println("cause " + e.getCause());
			System.out.println("excep " + e);
			e.printStackTrace();
		}

	}
}
