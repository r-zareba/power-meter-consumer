#!/usr/bin/env python3
"""
ADC Data Receiver for STM32 Power Meter
Receives 10kHz ADC samples via UART and provides real-time analysis
"""

import argparse

import serial

from analytics.power_analyzer import PowerAnalyzer
from config import ADC_CONFIG
from messaging.mqtt_publisher import MQTTPublisher
from receiver.receiver import ADCReceiver
from storage.sqlite_manager import SQLiteManager


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
    parser.add_argument(
        "--plot", action="store_true", help="Plot first analysis window after sync"
    )
    parser.add_argument(
        "--print-measurements",
        action="store_true",
        help="Print full PowerMeasurement every 200ms (default: print 1-second aggregates only)",
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
    # Initialize database manager (if not disabled)
    db_manager = SQLiteManager(db_path="data/power_measurements.db")
    db_manager.connect()

    mqtt_publisher = MQTTPublisher(
        broker_host="localhost",
        broker_port=1883,
        device_id="power_meter_01",
        topic_prefix="power_meter",
    )
    mqtt_publisher.connect()

    # Create power analyzer
    power_analyzer = PowerAnalyzer(
        sampling_freq=ADC_CONFIG["sampling_freq"],
        mains_freq=50.0,
        adc_max_value=ADC_CONFIG["max_value"],
        nominal_voltage=230.0,  # EU 230V nominal (adjust for US: 120V)
    )

    receiver = ADCReceiver(
        port=args.port,
        baudrate=args.baud,
        power_analyzer=power_analyzer,
        db_manager=db_manager,
        mqtt_publisher=mqtt_publisher,
        print_measurements=args.print_measurements,
    )

    connected = receiver.connect()
    if not connected:
        print("Could not connect to serial port")
        if db_manager:
            db_manager.close()
        if mqtt_publisher:
            mqtt_publisher.disconnect()
        return

    print(f"Connected to serial port {args.port} at {args.baud} baud")

    try:
        receiver.receive_continuous(plot_first_window=args.plot)
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        receiver.print_summary()
        receiver.disconnect()
        if db_manager:
            db_manager.close()
        if mqtt_publisher:
            mqtt_publisher.disconnect()


if __name__ == "__main__":
    main()
