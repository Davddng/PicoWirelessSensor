import asyncio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError
import struct
import time
# Use this terminal command if bleak is stuck on install
# export SKIP_CYTHON=false

# _DEVICE_SEARCH_NAME = "pico"
_DEVICE_SEARCH_NAME = "28:CD:C1:0D:5C:C0"

# Scans nearby bluetooth BLE devices for name that matches input 
async def searchBLEDeviceName(name = _DEVICE_SEARCH_NAME):
    foundDevices = []
    while len(foundDevices) == 0:
        scanResults = await BleakScanner.discover(return_adv=True)
        for address, (d, adv) in scanResults.items():
            if name.lower() in str(d.name).lower():
                foundDevices.append(d)
            elif name.lower() in str(adv.local_name).lower():
                foundDevices.append(d)
            elif name.lower() in address.lower():
                foundDevices.append(d)

        if len(foundDevices) == 0:
            print("No devices found matching '%s'. Searching again..." % name)

    return foundDevices

# Retry connecting to device if disconnected
def clientDisconnectHandler(client):
    global _BLE_CLIENT
    print("Client disconnected")

async def setBLEClient():
    global _BLE_CLIENT
    foundDevices = await searchBLEDeviceName()
    _BLE_CLIENT = BleakClient(address_or_ble_device = foundDevices[0], disconnected_callback = clientDisconnectHandler)
    await _BLE_CLIENT.connect()
    print("Connected to: ", foundDevices[0].name)

# Print description and its value
async def printDescriptorDetails(descriptor):
    print("Descriptor: ", descriptor.description)
    print("Descriptor value: ", await _BLE_CLIENT.read_gatt_descriptor(descriptor.handle))

async def printCharacteristicDetails(characteristic):
    print("Characteristic description: ", characteristic.description)
    print("Characteristic UUID: ", characteristic.uuid)
    print("Characteristic descriptors: ")
    if len(characteristic.descriptors) == 0:
        print("None")
    else:
        for descriptor in characteristic.descriptors:
            await printDescriptorDetails(descriptor)
        print("______End of descriptors______")

async def printServiceDetails(service):
    print("Service description: ", service.description)
    print("List of characteristics in this service:")
    if len(service.characteristics) == 0:
        print("None")
    else: 
        for characteristic in service.characteristics:
            await printCharacteristicDetails(characteristic)
        print("______End of characteristics______")


async def runBluetoothService():

    def characteristicUpdate(characteristic, data):
        updatedVal = float(struct.unpack("<h", data)[0])
        updatedVal = updatedVal/100
        print("Update characteristic:", characteristic, " val:", updatedVal)
        # print(temp_characteristic.properties)

    async def connectBluetoothSensor():
        await setBLEClient()
        global _BLE_CLIENT, tasks
        
        print("Descriptors: ")
        if len(_BLE_CLIENT.services.descriptors) == 0:
            print("None")
        for descriptorNumber in _BLE_CLIENT.services.descriptors:
            descriptor = _BLE_CLIENT.services.get_descriptor(descriptorNumber)
            await printDescriptorDetails(descriptor)
        
        print("Services: ")
        if len(_BLE_CLIENT.services.services) == 0:
            print("None")
        for serviceNumber in _BLE_CLIENT.services.services:
            service = _BLE_CLIENT.services.get_service(serviceNumber)
            await printServiceDetails(service)

        
        for serviceNumber in _BLE_CLIENT.services.services:
            global env_service
            service = _BLE_CLIENT.services.get_service(serviceNumber)
            if "Environmental Sensing" in service.description:
                env_service = service
                break
        
        for characteristic in env_service.characteristics:
            global temp_characteristic, humidity_characteristic, pressure_characteristic, PM1_characteristic, PM25_characteristic, PM10_characteristic
            if "Temperature" in characteristic.description:
                temp_characteristic = characteristic
            elif "Humidity" in characteristic.description:
                humidity_characteristic = characteristic
            elif "Pressure" in characteristic.description:
                pressure_characteristic = characteristic
            elif "PM1 Concentration" in characteristic.description:
                PM1_characteristic = characteristic
            elif "PM2.5" in characteristic.description:
                PM25_characteristic = characteristic
            elif "PM10" in characteristic.description:
                PM10_characteristic = characteristic

        await _BLE_CLIENT.start_notify(temp_characteristic.uuid, characteristicUpdate)
        await _BLE_CLIENT.start_notify(humidity_characteristic.uuid, characteristicUpdate)
        await _BLE_CLIENT.start_notify(pressure_characteristic.uuid, characteristicUpdate)
        await _BLE_CLIENT.start_notify(PM10_characteristic.uuid, characteristicUpdate)
        await _BLE_CLIENT.start_notify(PM25_characteristic.uuid, characteristicUpdate)
        await _BLE_CLIENT.start_notify(PM1_characteristic.uuid, characteristicUpdate)

    await connectBluetoothSensor()
    counter = 0

    while True:
        print("counter: ", counter)
        counter += 1
        waitTime = await tasks.get()
        if waitTime == -1:
            break
        print("waitTime: ", waitTime)
        await asyncio.sleep(waitTime)
        sendData = struct.pack("<h", int(0))
        try:
            print("Is connected: ", _BLE_CLIENT.is_connected)
            await _BLE_CLIENT.write_gatt_char(char_specifier=temp_characteristic, data=sendData)
            await _BLE_CLIENT.write_gatt_char(char_specifier=humidity_characteristic, data=sendData)
            await _BLE_CLIENT.write_gatt_char(char_specifier=pressure_characteristic, data=sendData)
            await _BLE_CLIENT.write_gatt_char(char_specifier=PM10_characteristic, data=sendData)
        except:
            await connectBluetoothSensor()
            print("Bluetooth Error")

        # print(temperature)
        # temp = float(struct.unpack("<h", temperature)[0])
        # print("Temperature: ", temp, "C")
    
    await _BLE_CLIENT.stop_notify(temp_characteristic.uuid)
    await _BLE_CLIENT.disconnect()


async def testFunction():
    global tasks
    # print("sleeping for 20s")
    # await asyncio.sleep(20)
    while True:
        await tasks.put(1)
        await asyncio.sleep(35)

    # print("Done sleeping")
    await tasks.put(5)
    await asyncio.sleep(35)
    await tasks.put(5)
    await asyncio.sleep(0)
    # await tasks.put(5)
    # await asyncio.sleep(5)
    # await tasks.put(5)


async def main():
    global tasks
    tasks = asyncio.Queue()
    # asyncio.run(runBluetoothService())
    # asyncio.run(testFunction())

    taskList = await asyncio.gather(
        runBluetoothService(),
        testFunction(),
    )

    # test.__next__()
    # test.send(15)



    # foundDevices = asyncio.run(searchBLEDeviceName("pico"))
    # print("Found devices: ", foundDevices)
if __name__ == "__main__":
    asyncio.run(main())
