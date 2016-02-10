package mypackage;

import java.util.ArrayList;
import java.util.Scanner;

import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.MqttCallback;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;

public class ClientCustom implements MqttCallback {
	private Randomizer ran;
	private MemoryPersistence persistence;
	private String topic;
	private String content;
	private int qos;
	private String broker;
	private String clientId;
	private MqttClient sampleClient;
	private MqttMessage message;
	private ArrayList<String> messageList;

	public ClientCustom() {
		this.initialize();
	}

	/**
	 * 
	 * Initialize all needed Components
	 * 
	 */
	public void initialize() {
		ran = new Randomizer();
		messageList = new ArrayList<>();
		topic = "MQTT Examples";
		content = "Message from MqttPublishSample";
		qos = 2;
		broker = "tcp://broker.hivemq.com:1883";
		System.out.println("Set broker url \"tcp://...:port\" \n(Leave empty for Fallback to HiveMQ): ");
		@SuppressWarnings("resource")
		Scanner scanner = new Scanner(System.in);
		String input;
		if (!(input = scanner.nextLine()).isEmpty()) {
			broker = input;
		} else {
			System.out.println("Using backup Broker HiveMQ");
		}
		clientId = "JustATestProgram";
		persistence = new MemoryPersistence();
		try {
			sampleClient = new MqttClient(broker, clientId, persistence);
			MqttConnectOptions connOpts = new MqttConnectOptions();
			connOpts.setCleanSession(false);
			System.out.println("Connecting to broker: " + broker);
			sampleClient.connect(connOpts);
			sampleClient.setCallback(this);
			System.out.println("Connected");
		} catch (MqttException e) {
			System.out.println("reason " + e.getReasonCode());
			System.out.println("msg " + e.getMessage());
			System.out.println("loc " + e.getLocalizedMessage());
			System.out.println("cause " + e.getCause());
			System.out.println("excep " + e);
			e.printStackTrace();
		}
	}

	/**
	 * Call to publish message to
	 * 
	 * @param t
	 *            topic as String
	 * @param c
	 *            content as String
	 * @param q
	 *            qos as int
	 */
	// @SuppressWarnings("deprecation")
	public void pub(String t, String c, int q) {
		try {
			MqttMessage message = new MqttMessage(c.getBytes());
			message.setQos(q);
			message.setRetained(true);
			// System.out.println("Set publish qos = " + q);
			sampleClient.publish(t, message);
			// System.out.println("Message published to: " + t + " content:
			// "+c);
		} catch (MqttException e) {
			System.out.println("reason " + e.getReasonCode());
			System.out.println("msg " + e.getMessage());
			System.out.println("loc " + e.getLocalizedMessage());
			System.out.println("cause " + e.getCause());
			System.out.println("excep " + e);
			e.printStackTrace();
			// Thread.currentThread().stop();
		}
	}

	public void sub(String t, int q) {
		try {
			sampleClient.subscribe(t, q);
			System.out.println("Subscribed to: " + t);
		} catch (MqttException e) {
			System.out.println("reason " + e.getReasonCode());
			System.out.println("msg " + e.getMessage());
			System.out.println("loc " + e.getLocalizedMessage());
			System.out.println("cause " + e.getCause());
			System.out.println("excep " + e);
			e.printStackTrace();
		}
	}

	public void disconnect() {
		if (sampleClient == null) {
			System.out.println("ERROR: MQTTClient is null, nothing to disconnect");
			return;
		}
		try {
			sampleClient.disconnect();
			System.out.println("Disconnected");
			System.exit(0);
		} catch (MqttException e) {
			System.out.println("reason " + e.getReasonCode());
			System.out.println("msg " + e.getMessage());
			System.out.println("loc " + e.getLocalizedMessage());
			System.out.println("cause " + e.getCause());
			System.out.println("excep " + e);
			e.printStackTrace();
		}
	}

	public Randomizer getRan() {
		return ran;
	}

	public void setRan(Randomizer ran) {
		this.ran = ran;
	}

	public String getTopic() {
		return topic;
	}

	public void setTopic(String topic) {
		this.topic = topic;
	}

	public String getContent() {
		return content;
	}

	public void setContent(String content) {
		this.content = content;
	}

	public int getQos() {
		return qos;
	}

	public void setQos(int qos) {
		this.qos = qos;
	}

	public String getBroker() {
		return broker;
	}

	public void setBroker(String broker) {
		this.broker = broker;
	}

	public String getClientId() {
		return clientId;
	}

	public void setClientId(String clientId) {
		this.clientId = clientId;
	}

	public MqttMessage getMessage() {
		return message;
	}

	@Override
	public void connectionLost(Throwable arg0) {

	}

	@Override
	public void deliveryComplete(IMqttDeliveryToken arg0) {

	}

	@Override
	public void messageArrived(String arg0, MqttMessage arg1) throws Exception {
		message = arg1;
		messageList.add("Server answered on subscription: " + arg0 + " content: " + arg1);
		System.out.println("Server answered on subscription: " + arg0 + " content: " + arg1);
	}

	public ArrayList<String> getMessageList() {
		return messageList;
	}

	public void setMessage(MqttMessage message) {
		this.message = message;
	}

	public void setMessageList(ArrayList<String> messageList) {
		this.messageList = messageList;
	}

	public void unsub(String topic) {
		// TODO Auto-generated method stub
		try {
			sampleClient.unsubscribe(topic);
		} catch (MqttException e) {
			// TODO Auto-generated catch block
			System.out.println("Cant unsub: " + e.getLocalizedMessage());
		}
	}

}
