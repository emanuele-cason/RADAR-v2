#include "RF24.h"
#include "SPI.h"
#include "nRF24L01.h"
#include <TinyGPS++.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_LSM6DS3TRC.h>
#include <Adafruit_LIS3MDL.h>
#include <Adafruit_AHRS.h>

RF24 radio(4, 5);              // Pin modulo tx/rx CE, CSN
/*
1 GND
2 3.3V
3 (CE) 4
4 (CSN) 5
5 (SCK) 18
6 (MOSI) 23
7 (MISO) 19 */

// Istanze sensori della IMU
Adafruit_LSM6DS3TRC lsm6ds;
Adafruit_LIS3MDL lis3mdl;

// Filtro AHRS per dati IMU
Adafruit_Madgwick filter;

#define GPS_BAUDRATE 9600

const int VOLTAGE_PIN = 35;
const int CURRENT_PIN = 34;

const byte GS_ADDRESS[5] = {'R', 'x', 'A', 'A', 'A'};
const int RADIO_CH = 108;
const int TX_INTERVAL = 100;

// IMU - Frequenza di aggiornamento e valori di calibrazione (da ristabilire quando cambia posizionamento IMU in fusoliera) - ottenuti da MotionCal, seguendo la guida:
//https://learn.adafruit.com/how-to-fuse-motion-sensor-data-into-ahrs-orientation-euler-quaternions/magnetic-calibration-with-motioncal
const int IMU_FREQ = 100;
float accelOffsets[3] = {0.0, 0.0, 0.0}; // accelerometro
float gyroOffsets[3] = {0.0, 0.0, 0.0}; // giroscopio
float magHardOffsets[3] = {-3.84, 33.35, -116.58}; // magnetometro
float magSoftOffsets[9] = {0.98, 0.04, -0.00, 0.04, 1.03, 0.00, -0.00, 0.00, 1.00};

const byte GPS_LOC_PACKET_ID = 1;
const byte GPS_CLK_PACKET_ID = 2;
const byte POWER_PACKET_ID = 3;
const byte IMU_PACKET_ID = 4;

TinyGPSPlus gps;
unsigned long lastTX;

unsigned long lastIMU;

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

void radioInit() {
  radio.begin();
  radio.setChannel(
      RADIO_CH); // Canale radio, 108 è sopra la maggiorparte delle reti wifi
  radio.setDataRate(RF24_250KBPS); // Livelli possibili: RF24_PA_MIN,
                                   // RF24_PA_LOW, RF24_PA_HIGH and RF24_PA_MAX
  radio.setPALevel(RF24_PA_MIN);
  radio.openWritingPipe(GS_ADDRESS);
}

void imuInit() {
  lsm6ds.begin_I2C();
  lis3mdl.begin_I2C();
  
  lsm6ds.setAccelRange(LSM6DS_ACCEL_RANGE_4_G);
  lsm6ds.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
  lis3mdl.setRange(LIS3MDL_RANGE_4_GAUSS);

  lsm6ds.setAccelDataRate(LSM6DS_RATE_1_66K_HZ);
  lsm6ds.setGyroDataRate(LSM6DS_RATE_1_66K_HZ);
  lis3mdl.setDataRate(LIS3MDL_DATARATE_1000_HZ);
  lis3mdl.setPerformanceMode(LIS3MDL_ULTRAHIGHMODE);
  lis3mdl.setOperationMode(LIS3MDL_CONTINUOUSMODE);

  filter.begin(IMU_FREQ);
}

void imuMagCalibrate(float &x, float &y, float &z){
    // Applica l'hard iron offset
  x -= magHardOffsets[0];
  y -= magHardOffsets[1];
  z -= magHardOffsets[2];

  // Applica la matrice di soft iron
  float xCal = magSoftOffsets[0] * x + magSoftOffsets[1] * y + magSoftOffsets[2] * z;
  float yCal = magSoftOffsets[3] * x + magSoftOffsets[4] * y + magSoftOffsets[5] * z;
  float zCal = magSoftOffsets[6] * x + magSoftOffsets[7] * y + magSoftOffsets[8] * z;

  x = xCal;
  y = yCal;
  z = zCal;
}

void radioTx(void *arg){

  while(true){

    radio.write(&gpsLocPacket, sizeof(gpsLocPacket));
    radio.write(&gpsClkPacket, sizeof(gpsClkPacket));
    radio.write(&powerPacket, sizeof(powerPacket));
    radio.write(&imuPacket, sizeof(imuPacket));   
    
    vTaskDelay(pdMS_TO_TICKS(TX_INTERVAL));
  }
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
  powerPacket.current = analogRead(CURRENT_PIN)*(3.3/4096.0);
  powerPacket.voltage = analogRead(VOLTAGE_PIN)*(3.3/4096.0);
}

void imuUpdate(){
  // Lettura dati dal LSM6DS3TRC
  sensors_event_t accel;
  sensors_event_t gyro;
  sensors_event_t temp;
  lsm6ds.getEvent(&accel, &gyro, &temp);

  // Lettura dati dal LIS3MDL
  sensors_event_t mag;
  lis3mdl.getEvent(&mag);

  imuPacket.temperature = temp.temperature;

  // Calibrazione dell'accelerometro
  float accelX = (accel.acceleration.x - accelOffsets[0]);
  float accelY = (accel.acceleration.y - accelOffsets[1]);
  float accelZ = (accel.acceleration.z - accelOffsets[2]);

  // Calibrazione del giroscopio
  float gyroX = (gyro.gyro.x - gyroOffsets[0])* SENSORS_RADS_TO_DPS;
  float gyroY = (gyro.gyro.y - gyroOffsets[1])* SENSORS_RADS_TO_DPS;
  float gyroZ = (gyro.gyro.z - gyroOffsets[2])* SENSORS_RADS_TO_DPS;

  // Calibrazione del magnetometro
  float magX = mag.magnetic.x;
  float magY = mag.magnetic.y;
  float magZ = mag.magnetic.z;
  imuMagCalibrate(magX, magY, magZ);

  // Aggiorna il filtro con i nuovi dati calibrati
  filter.update(gyroX, gyroY, gyroZ, accelX, accelY, accelZ, magX, magY, magZ);

  float avg_weight = 1;
  if (TX_INTERVAL > (1000/IMU_FREQ)) avg_weight = (1000.0 / IMU_FREQ) / TX_INTERVAL;

  imuPacket.accX = imuPacket.accX * (1 - avg_weight) + accelX * avg_weight;
  imuPacket.accY = imuPacket.accY * (1 - avg_weight) + accelY * avg_weight;
  imuPacket.accZ = imuPacket.accZ * (1 - avg_weight) + accelZ * avg_weight;
  
  imuPacket.roll = filter.getRoll();
  imuPacket.pitch = filter.getPitch();
  imuPacket.yaw = filter.getYaw();
}

void setup() {
  Serial2.begin(GPS_BAUDRATE);
  radioInit();
  imuInit();

  lastTX = 0;
  lastIMU = 0;

  xTaskCreate(
        radioTx,  // Funzione da eseguire
        "radioTx",    // Nome del task
        10000,         // Dimensione dello stack
        NULL,          // Parametro da passare al task
        1,             // Priorità del task
        NULL           // Puntatore al task handle
    );
}

void loop() {
  gpsUpdate();
  powerUpdate();

  if ((millis() - lastIMU) > (1000/IMU_FREQ)){
    imuUpdate();
    lastIMU = millis();
  }
}