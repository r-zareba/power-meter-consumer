#!/usr/bin/env python3
"""Debug tool to analyze raw serial data from STM32"""

import serial
import struct
import sys

port = 'COM5' if sys.platform == 'win32' else '/dev/ttyACM0'
baud = 921600

print(f"Opening {port} at {baud} baud...")
ser = serial.Serial(port, baud, timeout=2)

print("Reading raw data to find start marker 0xFFFF...")
buffer = bytearray()

for _ in range(100):  # Try 100 reads
    chunk = ser.read(100)
    buffer.extend(chunk)
    
    # Look for 0xFF 0xFF pattern (little-endian uint16 = 0xFFFF)
    for i in range(len(buffer) - 1):
        if buffer[i] == 0xFF and buffer[i+1] == 0xFF:
            print(f"\n✓ Found start marker at byte {i}")
            print(f"Next 32 bytes: {buffer[i:i+32].hex(' ')}")
            
            # Try to parse as packet header
            if len(buffer) >= i + 8:
                header = buffer[i:i+8]
                start, seq, count, vdda = struct.unpack('<HHHH', header)
                print(f"\nParsed header:")
                print(f"  Start:    0x{start:04X}")
                print(f"  Sequence: {seq}")
                print(f"  Count:    {count}")
                print(f"  VDDA:     {vdda} mV")
                
                if count == 1000 and 3000 <= vdda <= 3600:
                    print("\n✓ Header looks valid!")
                else:
                    print("\n✗ Header looks suspicious")
            
            buffer = buffer[i+2:]  # Skip past this marker
            break
    
    if len(buffer) > 5000:
        print(f"Buffer size: {len(buffer)} bytes, no valid marker yet...")
        buffer = buffer[-1000:]  # Keep last 1000 bytes

print(f"\nFinal buffer preview (first 200 bytes):")
print(buffer[:200].hex(' '))

ser.close()
