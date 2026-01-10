#!/usr/bin/env python3
"""
ADC Data Receiver for STM32 Power Meter
Receives 10kHz ADC samples via UART and provides real-time analysis
"""

import argparse

import serial

from receiver.receiver import ADCReceiver


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="STM32 ADC Data Receiver")

    parser.add_argument(
        "--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)"
    )
    parser.add_argument(
        "--baud", type=int, default=921600, help="Baud rate (default: 921600)"
    )
    parser.add_argument(
        "--raw", action="store_true", help="Display raw bytes (no parsing)"
    )

    return parser.parse_args()


def read_raw_bytes(port: str, baudrate: int):
    """Read and display raw bytes from serial port"""
    ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.1)
    ser.reset_input_buffer()

    byte_count = 0
    while True:
        data = ser.read(64)
        if data:
            print(f"[{byte_count:06d}] {data.hex(' ')}")
            byte_count += len(data)


def main():
    """Main entry point"""
    args = parse_args()

    # Raw byte reading mode (for debugging)
    if args.raw:
        print(f"Raw mode: reading from {args.port} at {args.baud} baud")
        try:
            read_raw_bytes(args.port, args.baud)
        except KeyboardInterrupt:
            print("\nStopped by user")
        except Exception as e:
            print(f"Error: {e}")
        return

    # Normal packet mode
    receiver = ADCReceiver(port=args.port, baudrate=args.baud)
    connected = receiver.connect()
    if not connected:
        print("Could not connect to serial port")
        return

    print(f"Connected to serial port {args.port} at {args.baud} baud")

    try:
        receiver.receive_continuous()
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        receiver.print_summary()
        receiver.disconnect()


if __name__ == "__main__":
    main()
