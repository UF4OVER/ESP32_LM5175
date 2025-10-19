# MicroPython on ESP32: UART <- STM32, parse frames, 转发到 BLE NUS (通知)
# 依赖: 你的 lib/BLE.py 在 lib 目录下，并且能 import BLE
# 修改 UART 参数为实际引脚/设备

import time
import struct
import BLE
import bluetooth
from machine import UART, Pin

SYNC = b'\xA5\x5A'
VER = 0x01
TYPE_FLOAT_ARRAY = 0x01

# UART config: 根据板子修改 tx/rx 引脚与 UART id
uart = UART(2, baudrate=115200, tx=26, rx=25)  # 示例
ble = BLE.BLEUART(bluetooth.BLE(), name="UF4-LM5175")


# CRC16-CCITT (0x1021, init 0xFFFF)
def crc16_ccitt(data: bytes, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) & 0xFFFF) ^ 0x1021
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


uart_buf = bytearray()


# 将解析到的有效帧原样转发给连接的 BLE central（保留帧格式，PC 端解析）
def forward_frame_to_ble(frame: bytes):
    # frame 包含完整帧（含 sync 和 CRC）
    # 如果 frame 很大，需要分片（BLE MTU）——本示例直接写入，视 BLE 底层是否自动分片
    ble.write(frame)


# 流式解析器：从 uart_buf 中提取完整帧
def try_parse_frames():
    global uart_buf
    frames = []
    i = 0
    while True:
        # 找到 sync
        idx = uart_buf.find(SYNC, i)
        if idx == -1:
            # 删除前面无用数据
            if i > 0:
                uart_buf = uart_buf[i:]
            break
        # 确保有最小头长度： sync(2)+ver(1)+type(1)+count(1)+seq(1)+crc(2) = 8 bytes
        if len(uart_buf) < idx + 8:
            # 等待更多字节
            if idx > 0:
                uart_buf = uart_buf[idx:]
            break
        # 读取 header
        ver = uart_buf[idx + 2]
        typ = uart_buf[idx + 3]
        count = uart_buf[idx + 4]
        # total frame length
        total_len = 2 + 1 + 1 + 1 + 1 + 4 * count + 2
        if len(uart_buf) < idx + total_len:
            # 等待更多
            if idx > 0:
                uart_buf = uart_buf[idx:]
            break
        # 提取 candidate frame
        frame = bytes(uart_buf[idx: idx + total_len])
        # 验证
        if ver != VER or typ != TYPE_FLOAT_ARRAY or count == 0:
            # 跳过这个 sync（可能是误触发）
            i = idx + 1
            continue
        # CRC check: calc over ver...payload
        crc_recv = frame[-2] | (frame[-1] << 8)
        crc_calc = crc16_ccitt(frame[2:-2])
        if crc_recv != crc_calc:
            # bad frame: skip this sync and continue
            i = idx + 1
            continue
        # good frame
        frames.append(frame)
        # advance index past this frame
        i = idx + total_len
        # remove processed bytes
        uart_buf = uart_buf[i:]
        i = 0
    return frames


# BLE 写入回调（可选：PC -> ESP32 -> STM32 控制命令）
def ble_handler():
    # 当 PC 写入 RX 特征，会触发 BLE._irq 中将数据放到 RX 缓冲并调用此 handler
    data = ble.read()
    # 简单示例：直接把 PC 写入的数据透传到 STM32 UART（作为控制命令）
    if data:
        uart.write(data)


ble.irq(ble_handler)

# 主循环：读取 UART，解析完整帧并转发到 BLE
while True:
    # 读串口可用数据追加到 uart_buf
    if uart.any():
        data = uart.read(uart.any())
        if data:
            uart_buf.extend(data)
    # 尝试解析出完整帧
    frames = try_parse_frames()
    for frm in frames:
        forward_frame_to_ble(frm)
    time.sleep_ms(5)
