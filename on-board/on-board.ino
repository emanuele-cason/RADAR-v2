#include "RF24.h"
#include "SPI.h"
#include "nRF24L01.h"
#include <TinyGPS++.h>

RF24 radio(4, 5);              // Pin modulo tx/rx CE, CSN
/*
1 GND
2 3.3V
3 (CE) 4
4 (CSN) 5
5 (SCK) 18
6 (MOSI) 23
7 (MISO) 19 */

#define GPS_BAUDRATE 9600

const int VOLTAGE_PIN = 34;
const int CURRENT_PIN = 35;

const byte GS_ADDRESS[5] = {'R', 'x', 'A', 'A', 'A'};
const int RADIO_CH = 108;

const int TX_INTERVAL = 100;

const byte GPS_LOC_PACKET_ID = 1;
const byte GPS_CLK_PACKET_ID = 2;
const byte POWER_PACKET_ID = 3;

TinyGPSPlus gps;
unsigned long lastTX;

struct gps_loc_packet {
  uint32_t id = GPS_LOC_PACKET_ID;
  uint32_t nSat;
  float lat;
  float lon;
  float alt;
  float speed;
  float cog;
} gpsLocPacket;

struct gps_clk_packet {
  uint32_t id = GPS_CLK_PACKET_ID;
  uint32_t day;
  uint32_t month;
  uint32_t year;
  uint32_t hour;
  uint32_t minute;
  uint32_t second;
} gpsClkPacket;

struct power_packet {
  uint32_t id = POWER_PACKET_ID;
  float voltage;
  float current;
} powerPacket;

void radioInit() {
  radio.begin();
  radio.setChannel(
      RADIO_CH); // Canale radio, 108 è sopra la maggiorparte delle reti wifi
  radio.setDataRate(RF24_250KBPS); // Livelli possibili: RF24_PA_MIN,
                                   // RF24_PA_LOW, RF24_PA_HIGH and RF24_PA_MAX
  radio.setPALevel(RF24_PA_MIN);
  radio.openWritingPipe(GS_ADDRESS);
}

void radioTx(){
  radio.write(&gpsLocPacket, sizeof(gpsLocPacket));
  radio.write(&gpsClkPacket, sizeof(gpsClkPacket));
  radio.write(&powerPacket, sizeof(powerPacket));
}

void gpsUpdate(){
  if (Serial2.available()){
    if (gps.encode(Serial2.read())) {

      if (gps.satellites.isValid()) {
        gpsLocPacket.nSat = gps.satellites.value();
      }

      if (gps.location.isValid()) {
        gpsLocPacket.lat = gps.location.lat();
        gpsLocPacket.lon = gps.location.lng();
      }

      if (gps.altitude.isValid()){
        gpsLocPacket.alt = gps.altitude.meters();
      }

      if (gps.speed.isValid()) {
        gpsLocPacket.speed = gps.speed.kmph();
      }

      if (gps.time.isValid()){
        gpsClkPacket.hour = gps.time.hour();
        gpsClkPacket.minute = gps.time.minute();
        gpsClkPacket.second = gps.time.second();
      }

      if (gps.date.isValid()){
        gpsClkPacket.day = gps.date.day();
        gpsClkPacket.month = gps.date.month();
        gpsClkPacket.year = gps.date.year();
      }
    }
  }
}

void powerUpdate(){
  powerPacket.current = (analogRead(CURRENT_PIN)*(3.3/4096)-0.33)*38.8788;
  powerPacket.voltage = analogRead(VOLTAGE_PIN)*(3.3/4095.0);
}

void setup() {
  Serial2.begin(GPS_BAUDRATE);
  radioInit();

  lastTX = 0;
}

void loop() {
  gpsUpdate();
  powerUpdate();
  
  if ((millis() - lastTX) > TX_INTERVAL){
    radioTx();
    lastTX = millis();
  }
}