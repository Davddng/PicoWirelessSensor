# This example demonstrates a simple temperature sensor peripheral.
#
# The sensor's local value is updated, and it will notify
# any connected central every 10 seconds.

import bluetooth
import random
import struct
import time
import machine
import ubinascii
from ble_advertising import advertising_payload
from micropython import const
from machine import Pin
from bmp280 import *
from pms7003 import PMS7003
import dht


# Bus and GPIO pin config for external sensors
# BMP280 (Pressure and Temperature)
BMP280_I2C_SCL_PIN = 1
BMP280_I2C_SDA_PIN = 0
BMP280_I2C_BUS_SEL = 0

# PMS7003 (PM2.5 Air Quality)
PMS7003_UART_BUS_SEL = 1
PMS7003_RX_PIN = 5
PMS7003_TX_PIN = 4
PMS7003_SLEEP_CRTL_PIN = 22

# DHT22 (Humidity and Temperature)
DHT22_DAT_PIN = 17

# Onboard Temperature Sensor and Relay for Heating Element
ONBOARD_TEMP_ADC_PIN = 4
HEAT_RELAY_PIN = 16

# Bluetooth event codes
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_INDICATE_DONE = const(20)

# Bluetooth characteristic flags
_FLAG_READ = bluetooth.FLAG_READ
_FLAG_WRITE_NO_RESPONSE = bluetooth.FLAG_WRITE_NO_RESPONSE
_FLAG_NOTIFY = bluetooth.FLAG_NOTIFY
_FLAG_INDICATE = bluetooth.FLAG_INDICATE

# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.temperature
_TEMP_CHAR = (
    bluetooth.UUID(0x2A6E),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)
# org.bluetooth.characteristic.humidity
_HUMID_CHAR = (
    bluetooth.UUID(0x2A6F),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)
# org.bluetooth.characteristic.pressure
_PRESS_CHAR = (
    bluetooth.UUID(0x2A6D),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)
# org.bluetooth.characteristic.particulate Matter - PM1 Concentration 
_PM1_CHAR = (
    bluetooth.UUID(0x2BD5),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)
# org.bluetooth.characteristic.particulate Matter - PM2.5 Concentration
_PM25_CHAR = (
    bluetooth.UUID(0x2BD6),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)
# org.bluetooth.characteristic.particulate Matter - PM10 Concentration
_PM10_CHAR = (
    bluetooth.UUID(0x2BD7),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)
# org.bluetooth.characteristic.Boolean (indicates if internal heater is on)
_HEAT_CHAR = (
    bluetooth.UUID(0x2AE2),
    _FLAG_READ | _FLAG_WRITE_NO_RESPONSE | _FLAG_NOTIFY | _FLAG_INDICATE,
)

_ENV_SENSE_SERVICE = (
    _ENV_SENSE_UUID,
    (_TEMP_CHAR, _HUMID_CHAR, _PRESS_CHAR, _PM1_CHAR, _PM25_CHAR, _PM10_CHAR, _HEAT_CHAR),
)

# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)

class BLETemperature:
    def __init__(self, ble, name=""):
        self.init_sensors()
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._handle = {}
        ((
        self._handle["temperature"], 
        self._handle["humidity"],
        self._handle["pressure"],
        self._handle["PM1"],
        self._handle["PM25"],
        self._handle["PM10"],
        self._handle["heat"],
        ),) = self._ble.gatts_register_services((_ENV_SENSE_SERVICE,))

        print(self._handle)
        self._connections = set()
        if len(name) == 0:
            name = 'Pico %s' % ubinascii.hexlify(self._ble.config('mac')[1],':').decode().upper()
        print('Sensor name %s' % name)
        self._payload = advertising_payload(
            name=name, services=[_ENV_SENSE_UUID], appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER
        )
        self._advertise()

    def init_sensors(self):
        i2c = machine.I2C(BMP280_I2C_BUS_SEL,scl=machine.Pin(BMP280_I2C_SCL_PIN),sda=machine.Pin(BMP280_I2C_SDA_PIN),freq=200000)
        self.bmp280 = BMP280(i2c)
        self.bmp280.use_case(BMP280_CASE_INDOOR)

        uart = machine.UART(PMS7003_UART_BUS_SEL, baudrate=9600, bits=8, parity=None, stop=1, tx=machine.Pin(PMS7003_TX_PIN), rx=machine.Pin(PMS7003_RX_PIN))
        self.pms7003 = PMS7003(uart, 30, PMS7003_SLEEP_CRTL_PIN)

        self.dht22 = dht.DHT22(machine.Pin(DHT22_DAT_PIN))


    # Interrupt ReQuest handler (IRQ)
    def _irq(self, event, data):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print("added connection:", conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            try: 
                self._connections.remove(conn_handle)
            except:
                print("disconnect irq error")
                print(self._connections)
            print("Client disconnect")
            # Start advertising again to allow a new connection.
            self._advertise()
        elif event == _IRQ_GATTS_INDICATE_DONE:
            conn_handle, value_handle, status = data
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, attr_handle = data
            if attr_handle == self._handle["temperature"]:
                print("Update temperature")
                updateValue = struct.pack("<h", int(round(self.bmp280.temperature * 100)))
                self.update_characteristic(notify=True, indicate=False, characteristic="temperature", value=updateValue)
            elif attr_handle == self._handle["humidity"]:
                print("Update humidity")
                self.dht22.measure()
                updateValue = struct.pack("<h", int(round(self.dht22.humidity() * 100)))
                self.update_characteristic(notify=True, indicate=False, characteristic="humidity", value=updateValue)
            elif attr_handle == self._handle["pressure"]:
                print("Update pressure")
                print(self.bmp280.pressure)
                updateValue = struct.pack("<h", int(round(self.bmp280.pressure / 10)))
                self.update_characteristic(notify=True, indicate=False, characteristic="pressure", value=updateValue)
            elif attr_handle in (self._handle["PM1"], self._handle["PM25"], self._handle["PM10"]):
                print("Update air particulate fields")
                airQuality = self.pms7003.readAirQuality()
                updateValue = struct.pack("<h", int(round(airQuality["pm1"] * 100)))
                self.update_characteristic(notify=True, indicate=False, characteristic="PM1", value=updateValue)
                updateValue = struct.pack("<h", int(round(airQuality["pm25"] * 100)))
                self.update_characteristic(notify=True, indicate=False, characteristic="PM25", value=updateValue)
                updateValue = struct.pack("<h", int(round(airQuality["pm10"] * 100)))
                self.update_characteristic(notify=True, indicate=False, characteristic="PM10", value=updateValue)


    def update_characteristic(self, notify=False, indicate=False, characteristic="temperature", value=b''):
        # Write the local value, ready for a central to read.
        # value = self.bmp280.temperature
        print("write %s: %.2f" % (characteristic, float(struct.unpack("<h", value)[0])))
        # self._ble.gatts_write(self._handle[characteristic], struct.pack("<h", int(value * 100)))
        self._ble.gatts_write(self._handle[characteristic], value)
        if notify or indicate:
            for conn_handle in self._connections:
                if notify:
                    # Notify connected centrals.
                    self._ble.gatts_notify(conn_handle, self._handle[characteristic])
                if indicate:
                    # Indicate connected centrals.
                    self._ble.gatts_indicate(conn_handle, self._handle[characteristic])


    def _advertise(self, interval_us=500000):
        self._ble.gap_advertise(interval_us, adv_data=self._payload)

class internalTemperatureSensor:
    def __init__(self, pin):
        self.sensor = machine.ADC(pin)
    
    def readTemperature(self):
        volt = self.sensor.read_u16() * (3.3/65535)
        temperature = 27 - (volt - 0.706)/0.001721
        return round(temperature, 1)
    
class heatingRelay:
    def __init__(self, pin):
        self.relayPin = Pin(pin, mode=Pin.OUT)
        self.relayStatus = False
     
    def setRelayState(self, state):
        if(state):
            self.relayPin.on()
            self.relayStatus = True
        else:
            self.relayPin.off()
            self.relayStatus = False
    def getRelayState(self):
        return self.relayStatus

def demo():
    ble = bluetooth.BLE()
    temp = BLETemperature(ble)
    counter = 0
    iTemp = internalTemperatureSensor(ONBOARD_TEMP_ADC_PIN)
    heater = heatingRelay(HEAT_RELAY_PIN)
    led = Pin('LED', Pin.OUT)
    try:
        while True:
            # if counter % 10 == 0:
            #     tempValue = struct.pack("<h", int(temp.bmp280.temperature * 100))
            #     temp.update_characteristic(notify=True, indicate=False, characteristic="temperature", value=tempValue)
            led.toggle()
            time.sleep_ms(1000)
            counter += 1
            internalTemp = iTemp.readTemperature()
            heaterStatus = heater.getRelayState()
            print(internalTemp)
            if(internalTemp < 5):
                if(not heaterStatus):
                    heater.setRelayState(True)
                    updateValue = struct.pack("<h", int(1))
                    temp.update_characteristic(notify=True, indicate=False, characteristic="heat", value=updateValue)
                print("heater on")
            if(internalTemp > 10):
                if(heaterStatus):
                    heater.setRelayState(False)
                    updateValue = struct.pack("<h", int(0))
                    temp.update_characteristic(notify=True, indicate=False, characteristic="heat", value=updateValue)
                print("heater off")

    except KeyboardInterrupt:
        print("Disconnecting...")
        for conn in temp._connections:
            ble.gap_disconnect(conn)

if __name__ == "__main__":
    demo()