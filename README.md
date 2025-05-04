# IoT-Device-Test-Environment

## 📘 Project Overview
This repository contains the project-independent layer of a fully automated HIL (Hardware-in-the-Loop) test environment designed for testing IoT-connected devices.

The system targets an ESP32 board connected to a cloud-based MQTT broker. Through this broker, the ESP32 receives commands to control an industrial water pump via a connected inverter. Communication between the ESP32 and the inverter is achieved using the Modbus RTU protocol.

## 🧰 Features
- Supports MQTT and Modbus RTU protocols
- Provides Python APIs for developing custom test cases
- Designed for HIL testing of embedded systems with cloud connectivity

## 📦 Dependencies
This project depends on the following third-party libraries:
- [paho-mqtt](https://pypi.org/project/paho-mqtt/)
- [pymodbus](https://pypi.org/project/pymodbus/)
#### ⚠️ These libraries must be manually installed prior to using this environment.

## 🔒 Confidential Components
This repository includes only the base framework of the test environment. A project-specific layer with custom APIs was also developed but is excluded due to confidentiality constraints.

## 🧱 Architecture
The diagram below outlines how the full test environment is structured and intended to be used.

### 🧩 Software Architecture
The software architecture includes components for MQTT communication with the cloud and Modbus RTU communication with the IoT device. It provides Python APIs for creating test cases.
#### Note: This repository contains the project-independent layer only.

![Software Architecture](https://github.com/user-attachments/assets/056ab6bd-9a84-4546-8713-716a1b9f6137)

### 🛠️ HIL Hardware Environment
The diagram below illustrates the physical HIL setup to be used during testing.

![Hardware Architecture](https://github.com/user-attachments/assets/c823a7a4-069c-4d40-b1c0-aad64b05e5c1)
