#include "RF24.h"
#include "SPI.h"
#include "nRF24L01.h"
#include <Wire.h>
#include <SparkFun_u-blox_GNSS_Arduino_Library.h>
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

// Istanza modulo GPS = GNSS
SFE_UBLOX_GNSS gnss;

// Istanze sensori della IMU
Adafruit_LSM6DS3TRC lsm6ds;
Adafruit_LIS3MDL lis3mdl;

// Filtro AHRS per dati IMU
Adafruit_Madgwick filter;

const int VOLTAGE_PIN = 35;
const int CURRENT_PIN = 34;

const byte GS_ADDRESS[5] = {'R', 'x', 'A', 'A', 'A'};
const int RADIO_CH = 108;
const int TX_INTERVAL = 100;

const int GNSS_INTERVAL = 500;

// IMU - Frequenza di aggiornamento e valori di calibrazione (da ristabilire quando cambia posizionamento IMU in fusoliera) - ottenuti da MotionCal, seguendo la guida:
//https://learn.adafruit.com/how-to-fuse-motion-sensor-data-into-ahrs-orientation-euler-quaternions/magnetic-calibration-with-motioncal
const int IMU_FREQ = 100;
float accelOffsets[3] = {0.0, 0.0, 0.0}; // accelerometro
float gyroOffsets[3] = {0.0, 0.0, 0.0}; // giroscopio
float magHardOffsets[3] = {-3.84, 33.35, -116.58}; // magnetometro
float magSoftOffsets[9] = {0.98, 0.04, -0.00, 0.04, 1.03, 0.00, -0.00, 0.00, 1.00};

const byte GNSS_LOC_PACKET_ID = 1;
const byte GNSS_CLK_PACKET_ID = 2;
const byte POWER_PACKET_ID = 3;
const byte IMU_PACKET_ID = 4;

unsigned long lastTX;
unsigned long lastIMU;

struct gnss_loc_packet {
  uint32_t id = GNSS_LOC_PACKET_ID;
  uint32_t nSat;
  float lat;
  float lon;
  float alt;
  float speed;
  float cog;
} gnssLocPacket;

// Momentaneamente non in uso, lasciato per necessità future di avere data/ora a bordo.
struct gnss_clk_packet {
  uint32_t id = GNSS_CLK_PACKET_ID;
  uint32_t day;
  uint32_t month;
  uint32_t year;
  uint32_t hour;
  uint32_t minute;
  uint32_t second;
} gnssClkPacket;

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
  radio.setPALevel(RF24_PA_MAX);
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

    radio.write(&gnssLocPacket, sizeof(gnssLocPacket));
    //radio.write(&gnssClkPacket, sizeof(gnssClkPacket));
    radio.write(&powerPacket, sizeof(powerPacket));
    radio.write(&imuPacket, sizeof(imuPacket));   
    
    vTaskDelay(pdMS_TO_TICKS(TX_INTERVAL));
  }
}

void gnssUpdate(void *arg){

  while(true){
    if (gnss.getPVT()){
      //Serial.println("Update gnss");
      gnssLocPacket.nSat = gnss.getSIV();
      gnssLocPacket.lat = gnss.getLatitude() / 10000000.0;
      gnssLocPacket.lon = gnss.getLongitude() / 10000000.0;
      gnssLocPacket.alt = gnss.getAltitudeMSL() / 1000.0 ;
      gnssLocPacket.speed = gnss.getGroundSpeed() / 1000.0;
      gnssLocPacket.cog = gnss.getHeading() / 100000.0;
    }

    vTaskDelay(pdMS_TO_TICKS(GNSS_INTERVAL));
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
  radioInit();
  
  Wire.begin();
  gnss.begin();

  gnss.setI2COutput(COM_TYPE_UBX); //Set the I2C port to output UBX only (turn off NMEA noise)
  gnss.saveConfigSelective(VAL_CFG_SUBSEC_IOPORT); //Save (only) the communications port settings to flash and BBR

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

    xTaskCreate(
        gnssUpdate,  // Funzione da eseguire
        "gnssUpdate",    // Nome del task
        10000,         // Dimensione dello stack
        NULL,          // Parametro da passare al task
        1,             // Priorità del task
        NULL           // Puntatore al task handle
    );

}

void loop() {
  
  powerUpdate();

  if ((millis() - lastIMU) > (1000/IMU_FREQ)){
    imuUpdate();
    lastIMU = millis();
  }
}