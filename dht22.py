import dht
import machine
d = dht.DHT22(machine.Pin(17))
print(d.measure())
print(d.temperature())
print(d.humidity())