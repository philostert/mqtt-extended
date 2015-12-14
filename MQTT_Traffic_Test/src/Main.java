public class Main {
	private static String topic;
	private static String content;
	private static int qos;
	
	

	public static void main(String[] args) {
		// TODO Auto-generated method stub
		ClientCustom c = new ClientCustom();

		qos = c.getQos();
		content = c.getRan().getTemp();
		topic = "TestCases/Locations/" + c.getRan().getLocation(Integer.parseInt(content));
		
		testOne(c,topic,content,qos);
		
		testTwo(c,topic,content,qos);
		
		for(String m : c.getMessageList()){
			System.out.println(m);
		}
	}

	private static void testOne(ClientCustom client, String topic, String content, int qos) {
		client.sub(topic, qos);		
		client.pub(topic, content, qos);
	}
	
	private static void testTwo(ClientCustom client, String topic, String content, int qos){
		client.sub("TestCases/Locations/#", qos);
		
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		try {
			Thread.sleep(5000);
		} catch (InterruptedException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		client.pub(topic,content,qos);
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic,content,qos);
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic,content,qos);
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic,content,qos);
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic,content,qos);
		content = client.getRan().getTemp();
		topic = "TestCases/Locations/" + client.getRan().getLocation(Integer.parseInt(content));
		client.pub(topic,content,qos);
	}

}
