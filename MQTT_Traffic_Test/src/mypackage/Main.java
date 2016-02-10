package mypackage;

import java.util.ArrayList;

import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;

public class Main {
	// private static String topic;
	// private static String content;
	// private static int qos;
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

	public static void main(String[] args) {
		System.out.println("TEST");
		ran = new Randomizer();
		messageList = new ArrayList<>();
		broker = "tcp://127.0.0.1:1883";
		topic = "#";
		content = "Message from MqttPublishSample";
		qos = 2;
		clientId = "SubAll";
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
			sampleClient.subscribe(topic);
		} catch (MqttException e) {
			System.out.println("reason " + e.getReasonCode());
			System.out.println("msg " + e.getMessage());
			System.out.println("loc " + e.getLocalizedMessage());
			System.out.println("cause " + e.getCause());
			System.out.println("excep " + e);
			e.printStackTrace();
		}

		// ClientCustom c = new ClientCustom();
		//
		// qos = c.getQos();
		// content = c.getRan().getTemp();
		// topic = "TestCases/Locations/" +
		// c.getRan().getLocation(Integer.parseInt(content));
		//
		// testOne(c,topic,content,qos);
		//
		// testTwo(c,topic,content,qos);
		//
		// for(String m : c.getMessageList()){
		// System.out.println(m);
		// }
	}

	// private static void testOne(ClientCustom client, String topic, String
	// content, int qos) {
	// client.sub(topic, qos);
	// client.pub(topic, content, qos);
	// }
	//
	// private static void testTwo(ClientCustom client, String topic, String
	// content, int qos){
	// client.sub("TestCases/Locations/#", qos);
	//
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// try {
	// Thread.sleep(5000);
	// } catch (InterruptedException e) {
	// e.printStackTrace();
	// }
	// client.pub(topic,content,qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic,content,qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic,content,qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic,content,qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic,content,qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic,content,qos);
	// }

}
