# Remote Aircraft Data Acquisition and Recording (R.A.D.A.R.)

This repository contains all software components for the **telemetry system**, including:

1. **Data Monitor** – A Python desktop application for real-time flight data visualization (graphs, artificial horizon, logging).
2. **Ground Station firmware (Arduino)** – Code for receiving telemetry data packets via NRF24L01 radio modules and forwarding them to the Data Monitor through serial communication.
3. **Onboard firmware (ESP32)** – Firmware running on the UAV’s ESP32, responsible for collecting sensor data, structuring it into packets, and sending it via radio to the Ground Station.

The system is modular and adaptable, allowing easy integration of new sensors and telemetry packets with minimal changes.


## 1. Data Monitor

### Interface Preview

![Interface Screenshot 1](/data-monitor/demo-images/interface-complete.png)  

<br>

![Interface Screenshot 2](/data-monitor/demo-images/interface-complete-accel.jpg)  


### Main Features
- **Data Acquisition**
  - Reads live data from the selected serial port.
  - Decodes incoming telemetry packets (GPS, clock/time, power, IMU).

- **Data Table**
  - Displays position, altitude, speed, course, power status, acceleration vector, orientation (roll, pitch, yaw), temperature, and more.
  - Updates dynamically with incoming data.

- **Plots**
  - Interactive plots for position, power, attitude, acceleration, and trajectory.
  - Modes: *Manual*, *Follow* (rolling buffer), *Complete* (all data).
  - Includes markers, buffer sync, and clearing functions.

- **Artificial Horizon**
  - Real-time visualization of roll and pitch.

- **Logging**
  - Records telemetry data and user markers into CSV files.
  - Start/stop logging via GUI button with visual feedback.

---

## 2. Ground Station firmware (Arduino)

The Ground Station acts as a bridge between the UAV and the Data Monitor:

**Workflow**
  1. NRF24L01 listens for incoming telemetry packets.
  2. Each packet is identified by a **packet ID** (e.g., GPS, clock, power, IMU).
  3. The payload is copied into the corresponding data structure.
  4. All received data is forwarded via **Serial** to the Data Monitor.

---

## 3. Onboard firmware (ESP32)

The onboard ESP32 is responsible for collecting and transmitting telemetry data.

**Workflow**
   1. Initializes the NRF24L01 radio, sensor inputs, and data structures.
   2. Configures tasks for transmission and sensor updates.
   3. Updates sensor data at defined frequencies.
   4. Packages the latest values into telemetry packets.
   5. Sends all packets to the Ground Station at regular intervals.
