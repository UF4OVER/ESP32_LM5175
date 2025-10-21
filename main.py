import BLE
import bluetooth
from machine import UART

uart = UART(2, baudrate=115200, tx=26, rx=25)
ble = BLE.BLEUART(bluetooth.BLE(), name="UF4-LM5175")


# BLE 写入回调（可选：PC -> ESP32 -> STM32 控制命令）
def ble_handler():
    # 当 PC 写入 RX 特征，会触发 BLE._irq 中将数据放到 RX 缓冲并调用此 handler
    data = ble.read()
    # 简单示例：直接把 PC 写入的数据透传到 STM32 UART（作为控制命令）
    if data:
        uart.write(data)


ble.irq(ble_handler)

# 主循环：读取 UART，转发数据到 BLE
while True:
    if uart.any():
        data = uart.read(uart.any())
        if data:
            ble.write(data)

    if ble.any():
        data = ble.read()
        if data:
            uart.write(data)
