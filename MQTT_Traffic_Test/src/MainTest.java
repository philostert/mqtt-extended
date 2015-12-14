import static org.junit.Assert.*;

import java.awt.Color;
import java.util.ArrayList;
import java.util.Scanner;

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
	private int messages;
	private Color color;

	@BeforeClass
	public static void intialize() {
		client = new ClientCustom();
		
//		client.setBroker(client.getBroker());
//		client.setClientId(client.getClientId());
//		client.setQos(client.getQos());
		
		topic = "TestCases/";

		qos = client.getQos();
		content = client.getRan().getTemp();
		topic = "Locations/" + client.getRan().getLocation(Integer.parseInt(content));

		for (String m : client.getMessageList()) {
			System.out.println(m);
		}
	}

	/**
	 * Test pub/subbing one Topic
	 */
	@Test
	public void testOne() {
		client.sub(topic, qos);
		client.pub(topic, content, qos);
		while ((test = client.getMessage()) == null) {
			try {
				Thread.sleep(5000);
			} catch (InterruptedException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		}
		assertTrue(content.equals(client.getMessage().toString()));
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}

	/**
	 * Test pub/subbing multiple Topics
	 */
	@Test
	public void testTwo() {
		messages = 0;
		client.sub("TestCases/Locations/#", qos);
		publishOne();
		try {
			Thread.sleep(5000);
		} catch (InterruptedException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		assertTrue(messages==client.getMessageList().size());
		client.setMessage(null);
		client.setMessageList(new ArrayList<>());
	}
	
	/**
	 * Test if QoS is correct
	 */
	@Test
	public void testThree(){
		client.sub("TestCases/Colors", qos);
		publishFalse();
		try {
			Thread.sleep(5000);
		} catch (InterruptedException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		assertFalse(qos==client.getMessage().getQos());
	}
	
//	@Test
//	public void testDdos(){
//		client.sub("TestCases/DDoSTest", qos);
//		publishDDoS();
//		try {
//			Thread.sleep(5000);
//		} catch (InterruptedException e) {
//			// TODO Auto-generated catch block
//			e.printStackTrace();
//		}
//		assertFalse(messages==client.getMessageList().size());
//	}
	
	//PublishOne
	private void publishOne(){
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
	
	private void publishFalse(){
		color = client.getRan().getColor();
		topic = "TestCases/Colors";
		int qosNew;
		if(qos==0){
			qosNew=1;
		}else if(qos==1){
			qosNew=2;
		}else{
			qosNew=0;
		}
		client.pub(topic, ""+color.getRGB(), qosNew);
	}
	
	private void publishDDoS(){
		topic = "TestCases/DDoSTest";
		while(true){
			client.pub(topic, ""+Math.random(), qos);
			messages++;
		}
	}

}
