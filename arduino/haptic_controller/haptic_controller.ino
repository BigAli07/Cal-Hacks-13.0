// PulsePath v1: active buzzers or driver-controlled vibration motors.
// GPIO must drive a suitable transistor/driver, not a motor directly.
// Passive piezo buzzers need a different tone driver; this sketch uses PWM.
const byte PINS[3] = {3,5,6}; // left, centre, right; coordinate wiring with robotics owner
char line[48]; byte used=0; bool overflow=false;
unsigned long lastPacket=0;
void off(){for(byte i=0;i<3;i++) analogWrite(PINS[i],0);}
void setup(){for(byte i=0;i<3;i++) pinMode(PINS[i],OUTPUT); off(); Serial.begin(115200);}
void loop(){
  if(millis()-lastPacket>500) off();
  while(Serial.available()){
    char c=Serial.read();
    if(c=='\n'){
      line[used]=0;
      if(!overflow && strcmp(line,"HELLO")==0){Serial.println("PULSEPATH/1");off();}
      else if(!overflow){
        int l,c,r; char extra;
        if(sscanf(line,"P1,%d,%d,%d%c",&l,&c,&r,&extra)==3 && l>=0 && l<=255 && c>=0 && c<=255 && r>=0 && r<=255){
          analogWrite(PINS[0],l);analogWrite(PINS[1],c);analogWrite(PINS[2],r);lastPacket=millis();
        }else off();
      }else off();
      used=0;overflow=false;
    }else if(c!='\r'){
      if(used<sizeof(line)-1)line[used++]=c;else overflow=true;
    }
  }
}
