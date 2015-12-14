@SuppressWarnings("unused")
public class Randomizer {

	private int randomTemp;
	private String topic;
	private int randomRGB;
	private String location;
	
	public Randomizer(){
		}
	
	public synchronized String getTemp(){
		randomTemp = (int)(Math.random() * 25);
		if(Math.random() < 0.2){
			randomTemp = randomTemp * -1;
		}
		return ""+randomTemp;
	}
	
	public synchronized String getLocation(int a){
		if(a < -4){
			location = "Novosibirsk";
		}else if(a < 15){
			location = "Berlin";
		}else{
			location = "Miami";
		}
		return location;
	}
}