# Source: Electrocredible.com, Language: MicroPython

from machine import Pin,I2C
from bmp280 import *
import time

bus = I2C(0,scl=Pin(1),sda=Pin(0),freq=200000)
bmp = BMP280(bus)

bmp.use_case(BMP280_CASE_INDOOR)

while True:
    pressure=bmp.pressure
    p_bar=pressure/100000
    p_mmHg=pressure/133.3224
    temperature=bmp.temperature
    print("Temperature: {} C".format(temperature))
    print("Pressure: {} Pa, {} bar, {} mmHg".format(pressure,p_bar,p_mmHg))
    time.sleep(1)