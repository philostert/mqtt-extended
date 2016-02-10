package mypackage;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.awt.Color;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.SynchronousQueue;
import java.util.concurrent.ThreadPoolExecutor;

import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.junit.BeforeClass;
import org.junit.Test;

@SuppressWarnings("unused")
public class MainTest {
	private static String topic;
	private static String content;
	private static int qos;
	private static ClientCustom client;
	private static MqttMessage test;
	private static int messages;
	private static Color color;
	private static ArrayList<Thread> threadList;
	private static int unsubAmount = 20;

	public static void main(String[] args) {
		initialize();
		testOne();
		testTwo();
		testThree();
		testDos();
		testDosThreaded();
	}

	@BeforeClass
	public static void initialize() {
		client = new ClientCustom();

		// client.setBroker(client.getBroker());
		// client.setClientId(client.getClientId());
		// client.setQos(client.getQos());

		topic = "TestCases/";

		qos = client.getQos();
		content = client.getRan().getTemp();
		topic = "Locations/" + client.getRan().getLocation(Integer.parseInt(content));

		for (String m : client.getMessageList()) {
			System.out.println(m);
		}
	}

	@Test
	public static void testUnsub() {
		ArrayList<ClientCustom> cc = new ArrayList<>();
		pubUnsub();
		for (int i = 0; i < unsubAmount; i++) {
			client = new ClientCustom();
			cc.add(client);
			client.sub("Tests/Unsub", 2);
		}
		for (int i = 0; i < cc.size(); i++) {
			cc.get(i).unsub("Tests/Unsub");
		}
	}

	private static void pubUnsub() {
		// TODO Auto-generated method stub
		client.pub("Tests/Unsub", "unsub: " + System.currentTimeMillis(), 2);
	}

	/**
	 * Test pub/subbing one Topic
	 */
	@Test
	public static void testOne() {
		client.sub(topic, qos);
		client.pub(topic, content, qos);
		while ((test = client.getMessage()) == null) {
			try {
				Thread.sleep(5000);
			} catch (InterruptedException e) {
				e.printStackTrace();
			}
		}
		assertTrue(content.equals(client.getMessage().toString()));
		System.out.println("TestOne: " + content.equals(client.getMessage().toString()));
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}

	/**
	 * Test pub/subbing multiple Topics
	 */
	@Test
	public static void testTwo() {
		messages = 0;
		client.sub("TestCases/Locations/#", qos);
		publishOne();
		try {
			Thread.sleep(5000);
		} catch (InterruptedException e) {
			e.printStackTrace();
		}
		assertTrue(messages == client.getMessageList().size());
		System.out.println("TestTwo: " + (messages == client.getMessageList().size()));
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}

	/**
	 * Test if QoS is correct
	 */
	@Test
	public static void testThree() {
		messages = 0;
		client.sub("TestCases/Colors", qos);
		publishFalse();
		try {
			Thread.sleep(5000);
		} catch (InterruptedException e) {
			e.printStackTrace();
		}
		assertFalse(qos == client.getMessage().getQos());
		System.out.println("TestThree: " + (qos == client.getMessage().getQos()));
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}

	@Test
	public static void testDos() {
		if (client.getBroker().equals("tcp://broker.hivemq.com:1883")) {
			System.out.println("No DoS Test on Backup Broker");
			return;
		}
		messages = 0;
		client.sub("TestCases/DoSTest", qos);
		publishDoS();
		while (client.getMessageList().size() < messages) {
			try {
				Thread.sleep(5000);
			} catch (InterruptedException e) {
				e.printStackTrace();
			}
		}
		assertTrue(messages == client.getMessageList().size());
		System.out.println("TestDoS: " + (messages == client.getMessageList().size()));
		// FIXME: asdasd
		client.unsub("TestCases/DoSTest");
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}

	@Test
	public static void testDosThreaded() {
		if (client.getBroker().equals("tcp://broker.hivemq.com:1883")) {
			System.out.println("No DoS Test on Backup Broker");
			return;
		}
		messages = 0;
		client.sub("TestCases/DoSTest/Threaded", qos);
		publishDoSThreaded();
		while (client.getMessageList().size() < messages) {
			try {
				Thread.sleep(5000);
			} catch (InterruptedException e) {
				e.printStackTrace();
			}
		}
		assertTrue(messages == client.getMessageList().size());
		System.out.println("TestDosThread: " + (messages == client.getMessageList().size()));
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}

	private static void publishOne() {
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic, content, qos);
		messages++;
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic, content, qos);
		messages++;
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic, content, qos);
		messages++;
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic, content, qos);
		messages++;
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic, content, qos);
		messages++;
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic, content, qos);
		messages++;
	}

	private static void publishFalse() {
		color = client.getRan().getColor();
		topic = "TestCases/Colors";
		int qosNew;
		if (qos == 0) {
			qosNew = 1;
		} else if (qos == 1) {
			qosNew = 2;
		} else {
			qosNew = 0;
		}
		client.pub(topic, "" + color.getRGB(), qosNew);
	}

	private static void publishDoS() {
		topic = "TestCases/DoSTest";
		while (messages < 5000) {
			client.pub(topic, "" + Math.random(), qos);
			messages++;
		}
	}

	private static void publishDoSThreaded() {
		final String topicThreaded = "TestCases/DoSTest/Threaded";
		int threadAmount = 0;
		threadList = new ArrayList<>();
		while (threadAmount < 100) {
			threadList.add(new Thread() {
				@Override
				public void run() {
					while (true) {
						try {
							client.setClientId("" + Math.random() * System.currentTimeMillis());
							client.pub(topicThreaded, "" + Math.random(), qos);
							messages++;
						} catch (Exception e) {
							System.out.println(e.getMessage());
							break;
						}
					}
				}
			});
			threadAmount++;
		}
		ExecutorService exe = Executors.newCachedThreadPool();

		for (Thread t : threadList) {
			exe.execute(t);
		}
		exe.shutdown();
	}
}
