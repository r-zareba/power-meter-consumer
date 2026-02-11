#!/usr/bin/env python3
"""
STM32 Power Meter Simulator

Simulates STM32 UART data transmission with dual-channel ADC data.
Generates synthetic voltage and current waveforms using the exact same
packet protocol as the real STM32.

Configuration is loaded from simulator/config.py

Usage:
    python src/run_stm32_simulator.py --port /dev/pts/3
"""

import argparse

from simulator.simulator import STM32Simulator


def main():
    """Main entry point for simulator"""
    parser = argparse.ArgumentParser(
        description="STM32 Power Meter Simulator - Configuration in simulator/config.py"
    )

    parser.add_argument(
        "--port", required=True, help="Serial port (e.g., /dev/pts/3, COM3)"
    )
    parser.add_argument(
        "--baud", type=int, default=921600, help="Baud rate (default: 921600)"
    )

    args = parser.parse_args()

    # Create simulator
    sim = STM32Simulator(port=args.port, baudrate=args.baud)

    if not sim.connect():
        return

    try:
        sim.run_simulation()
    finally:
        sim.disconnect()


if __name__ == "__main__":
    main()
