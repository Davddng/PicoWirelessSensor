import time
import machine

UART_BUS_SEL = 1
RX_PIN = 5
TX_PIN = 4
SLEEP_CRTL_PIN = 22

class PMS7003:    
    def __init__(self, serial, startupTime, sleepCtrlPin):
        self.serial = serial
        self.sensorState = False
        self.startupTime = startupTime
        self.sleepCtrlPin = sleepCtrlPin

    # Desc: Updates sensor data on readings variable
    # Args: data - Data read from sensor
    def parseData(self, data, readings):
        readings["pm1"] = data[2] << 8 | data[3]
        readings["pm25"] = data[4] << 8 | data[5]
        readings["pm10"] = data[6] << 8 | data[7]
        readings["pm1env"] = data[8] << 8 | data[9]
        readings["pm25env"] = data[10] << 8 | data[11]
        readings["pm10env"] = data[12] << 8 | data[13]
        readings["pbd3"] = data[14] << 8 | data[15]
        readings["pbd5"] = data[16] << 8 | data[17]
        readings["pbd10"] = data[18] << 8 | data[19]
        readings["pbd25"] = data[20] << 8 | data[21]
        readings["pbd50"] = data[22] << 8 | data[23]
        readings["pbd100"] = data[24] << 8 | data[25]
        readings["reserved"] = data[26] << 8 | data[27]
        readings["checksum"] = data[28] << 8 | data[29]
        readings["error"] = 0

        # Checksum calculation
        checksum = 0x42 + 0x4d
        for i in range(0, 27):
            checksum += data[i]
        
        if checksum != readings['checksum']:
            readings['error'] = 1
        

    # Desc: Turn sensor on or off
    # Args: state - true = on, false = off
    def setSensorState(self, state): 
        print("sensor: ", state)
        sleepControl = machine.Pin(self.sleepCtrlPin, machine.Pin.OUT)

        if state:
            sleepControl.on()
        else:
            sleepControl.off()

    def setStartupTime(self, newStartupTime):
        self.startupTime = newStartupTime

    # Desc: Turns on sensor, waits 30 seconds for startup, then reads sensor data into the provided 'readings' variable
    # Args: serial - Serial connection eg. serial.Serial("/dev/ttyS0", 9600), readings - Object to put readings into, warmUpTime - Time to wait for sensor to wake from sleep
    def readAirQuality(self):
        self.setSensorState(True)
        for i in range(self.startupTime):
            print("Sleeping... %d/%d seconds elapsed" % (i, self.startupTime))
            time.sleep(1)
        
    #     first two bytes returned by sensor are 0x42 followed by 0x4d. Next 30 bytes are data
        tryCounter = -1
        while True:
            tryCounter += 1
            if ord(self.serial.read(1)) == 0x42:
                if ord(self.serial.read(1)) == 0x4d:
                    break
            else:
                if tryCounter <= 128:
                    continue
                else:
                    return -1

        sensorData = self.serial.read(30)
        readings = {}
        self.parseData(sensorData, readings)
        self.setSensorState(False)
        return readings


if __name__ == '__main__':
    uart = machine.UART(UART_BUS_SEL, baudrate=9600, bits=8, parity=None, stop=1, tx=machine.Pin(TX_PIN), rx=machine.Pin(RX_PIN))
    pms7003 = PMS7003(uart, 10, SLEEP_CRTL_PIN)
    readings = pms7003.readAirQuality()
    print(readings)