import static org.junit.Assert.*;

import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.junit.BeforeClass;
import org.junit.Test;

@SuppressWarnings("unused")
public class MainTest {
	private static String topic;
	private static String content;
	private static int qos;
	private static ClientCustom client;
	private MqttMessage test;

	@BeforeClass
	public static void intialize() {
		client = new ClientCustom();

		qos = client.getQos();
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));

		for (String m : client.getMessageList()) {
			System.out.println(m);
		}
	}

	@Test
	public void testOne() {
		client.sub(topic, qos);
		client.pub(topic, content, qos);
		while ((test = client.getMessage()) == null) {
			try {
				Thread.sleep(50);
			} catch (InterruptedException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		}
		assertTrue(content.equals(client.getMessage().toString()));
	}

	// @Test
	// public void testTwo() {
	// client.sub("TestCases/Locations/#", qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// try {
	// Thread.sleep(5000);
	// } catch (InterruptedException e) {
	// // TODO Auto-generated catch block
	// e.printStackTrace();
	// }
	// client.pub(topic, content, qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic, content, qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic, content, qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic, content, qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic, content, qos);
	// content = client.getRan().getTemp();
	// topic = "TestCases/Locations/" +
	// client.getRan().getLocation(Integer.parseInt(content));
	// client.pub(topic, content, qos);
	// }

}
