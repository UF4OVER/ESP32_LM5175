import BLE
import bluetooth
from machine import UART
import time

uart = UART(2, baudrate=115200, tx=26, rx=25)
ble = BLE.BLEUART(bluetooth.BLE(), name="UF4_LM5175")


def ble_handler():
    while ble.any():
        data = ble.read()
        if data:
            uart.write(data)


ble.irq(ble_handler)

while True:
    if uart.any():
        data = uart.read(uart.any())
        if data:
            ble.write(data)

    while ble.any():
        data = ble.read()
        if data:
            uart.write(data)

    time.sleep_us(100)
