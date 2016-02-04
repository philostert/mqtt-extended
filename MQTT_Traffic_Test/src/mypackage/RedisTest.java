package mypackage;

import java.nio.charset.StandardCharsets;

import org.springframework.data.redis.serializer.JdkSerializationRedisSerializer;

import com.lambdaworks.redis.RedisClient;
import com.lambdaworks.redis.RedisURI;
import com.lambdaworks.redis.api.StatefulRedisConnection;
import com.lambdaworks.redis.api.sync.RedisCommands;

public class RedisTest {
	private String url;
	private int port;
	private RedisClient client;
	private StatefulRedisConnection<String, String> connection;
	private RedisCommands<String, String> syncCommands;
	private JdkSerializationRedisSerializer redisSerializer;

	/**
	 * Create a redisClient instance if it doesn't exist yet
	 * 
	 * @param passedUrl
	 * @param passedPort
	 * @return
	 */

	public static void main(String[] args) {
		RedisTest r = new RedisTest("localhost", 6379);
		JdkSerializationRedisSerializer rs = new JdkSerializationRedisSerializer();

		r.put("Test", 5);

		RedisContainer h = r.get("Test");
		
		byte[] bytes = h.getValue().getBytes((StandardCharsets.UTF_8));

		rs.deserialize(bytes);

		System.out.println(h.isResult() + " " + "");
	}

	public RedisTest(String passedUrl, int passedPort) {
		this.url = passedUrl;
		this.port = passedPort;
		if (client == null) {
			try {
				RedisURI redisURI = RedisURI.Builder.redis(url).withPort(port).withDatabase(1).build();
				client = RedisClient.create(redisURI);
				connection = client.connect();
				syncCommands = connection.sync();

				redisSerializer = new JdkSerializationRedisSerializer();

			} catch (Exception e) {
				System.out.println(e.getMessage());
			}
		}

	}

	public boolean shutdown(RedisTest t) {
		try {
			client.shutdown();
			return true;
		} catch (Exception e) {
			System.out.println("RedisClient didn't close correctly!\r\n" + e.getMessage());
			return false;
		}
	}

	public boolean put(String key, Object o) {
		try {
			syncCommands.set(key, redisSerializer.serialize(o).toString());
		} catch (Exception e) {
			System.out.println(e.getMessage());
			return false;
		}
		return true;
	}

	public RedisContainer get(String key) {
		if (syncCommands.get(key) == null) {
			return new RedisContainer(false, null);
		}
		return new RedisContainer(true, syncCommands.get(key));

	}

	public class RedisContainer {
		private boolean result;

		public boolean isResult() {
			return result;
		}

		public String getValue() {
			return value;
		}

		private String value;

		private RedisContainer(boolean b, String object) {
			this.result = b;
			this.value = object;
		}
	}

}
