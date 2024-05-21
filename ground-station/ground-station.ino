#include "RF24.h"
#include <SPI.h>

#define CE_PIN 7
#define CSN_PIN 8

const byte thisSlaveAddress[5] = {
    'R', 'x', 'A', 'A',
    'A'};
const byte GPS_PACKET_ID = 0;

RF24 radio(CE_PIN, CSN_PIN);

const byte GPS_LOC_PACKET_ID = 1;
const byte GPS_CLK_PACKET_ID = 2;
const byte POWER_PACKET_ID = 3;
const byte IMU_PACKET_ID = 4;

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

struct imu_packet{
  uint32_t id = IMU_PACKET_ID;
  float accX;
  float accY;
  float accZ;
  float roll;
  float pitch;
  float yaw;
  float temperature;
} imuPacket;

void writeTlm(const char *pkt, uint32_t length) {

  for (int i = 0; i < length; i++) {
    Serial.write(pkt[i]);
  }
}

void sendTlm() {
  writeTlm((const char *)&gpsLocPacket, sizeof(gpsLocPacket));
  writeTlm((const char *)&gpsClkPacket, sizeof(gpsClkPacket));
  writeTlm((const char *)&powerPacket, sizeof(powerPacket));
  writeTlm((const char *)&imuPacket, sizeof(imuPacket));
}

void setup() {
  Serial.begin(500000);
  radio.begin();     
  radio.setChannel(108);
  radio.setDataRate(RF24_250KBPS);

  // PA (Power Amplifier) Level can be one of four levels: RF24_PA_MIN,
  // RF24_PA_LOW, RF24_PA_HIGH and RF24_PA_MAX
  radio.setPALevel(RF24_PA_MIN);
  radio.openReadingPipe(1, thisSlaveAddress);
  radio.startListening();
}

void loop() {

  if (radio.available()) {

    byte payloadSize = radio.getPayloadSize(); // Ottieni la dimensione del payload

    byte payload[payloadSize]; // Crea un array di byte per memorizzare il payload
    radio.read(&payload, payloadSize); // Leggi il payload

    // Il 0 è la posizione del byte relativa all'ID del pacchetto
    if(payload[0] == GPS_LOC_PACKET_ID){
      memcpy(&gpsLocPacket, payload, sizeof(gpsLocPacket));
    }

    if(payload[0] == GPS_CLK_PACKET_ID){
      memcpy(&gpsClkPacket, payload, sizeof(gpsClkPacket));
    }

    if(payload[0] == POWER_PACKET_ID){
      memcpy(&powerPacket, payload, sizeof(powerPacket));
    }

    if(payload[0] == IMU_PACKET_ID){
      memcpy(&imuPacket, payload, sizeof(imuPacket));
    }

    sendTlm();
  }
}