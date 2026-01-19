#!/usr/bin/env python3
"""
STM32 Power Meter Simulator

Simulates the STM32 UART data transmission with dual-channel ADC data.
Generates synthetic voltage and current waveforms and transmits them
using the exact same packet protocol as the real STM32.

Configuration is loaded from simulator_config.py

Usage:
    python run_stm32_simulator.py --port /dev/pts/3
    python run_stm32_simulator.py --port /dev/pts/3 --duration 60
"""

import argparse
import struct
import sys
import time
from pathlib import Path

import numpy as np
import serial

# Add parent directory to path to import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ADC_CONFIG, CURRENT_SENSOR, VOLTAGE_SENSOR
from scripts.simulator_config import CURRENT, VOLTAGE


class STM32Simulator:
    """Simulates STM32 ADC data transmission via UART"""

    # Protocol constants (must match STM32 and receiver)
    START_MARKER = 0xFFFF
    END_MARKER = 0xFFFE
    SAMPLES_PER_PACKET = ADC_CONFIG["samples_per_packet"]
    SAMPLING_FREQ = ADC_CONFIG["sampling_freq"]
    MAINS_FREQ = 50  # Hz

    # ADC parameters (from global config)
    ADC_BITS = ADC_CONFIG["bits"]
    ADC_MAX = ADC_CONFIG["max_value"]
    VREF = ADC_CONFIG["vref"]

    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.sequence = 0
        self.time_offset = 0.0

    def connect(self) -> bool:
        """Open serial port for transmission"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
            )
            print(f"Connected to {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            return False

    def disconnect(self):
        """Close serial port"""
        if self.serial and self.serial.is_open:
            self.serial.close()

    def voltage_to_adc(self, voltage: float) -> int:
        """Convert voltage (0-3.3V) to ADC value (0-4095)"""
        adc = int((voltage / self.VREF) * self.ADC_MAX)
        return np.clip(adc, 0, self.ADC_MAX)

    def ac_to_adc(self, ac_voltage: float, dc_bias: float) -> int:
        """Convert AC voltage to DC-biased ADC value
        
        Args:
            ac_voltage: AC voltage component
            dc_bias: DC bias voltage (sensor-specific)
        """
        total_voltage = dc_bias + ac_voltage
        return self.voltage_to_adc(total_voltage)

    def generate_sine_wave(
        self,
        amplitude_rms: float,
        dc_bias: float,
        phase: float = 0.0,
        harmonics: dict = None,
    ) -> np.ndarray:
        """
        Generate sine wave samples

        Args:
            amplitude_rms: RMS voltage amplitude
            dc_bias: DC bias voltage (sensor-specific)
            phase: Phase offset in radians
            harmonics: Dict of {harmonic_num: amplitude_fraction}
                      e.g., {3: 0.2, 5: 0.1} adds 20% 3rd and 10% 5th harmonic

        Returns:
            Array of ADC values
        """
        t = (np.arange(self.SAMPLES_PER_PACKET) / self.SAMPLING_FREQ) + self.time_offset

        # Fundamental frequency
        amplitude_peak = amplitude_rms * np.sqrt(2)
        signal = amplitude_peak * np.sin(2 * np.pi * self.MAINS_FREQ * t + phase)

        # Add harmonics if specified
        if harmonics:
            for harmonic_num, harmonic_amplitude in harmonics.items():
                if harmonic_amplitude > 0:  # Skip if zero
                    harmonic_freq = self.MAINS_FREQ * harmonic_num
                    signal += (
                        amplitude_peak
                        * harmonic_amplitude
                        * np.sin(2 * np.pi * harmonic_freq * t)
                    )

        # Convert to ADC values (using sensor-specific DC bias)
        adc_values = np.array(
            [self.ac_to_adc(v, dc_bias) for v in signal], dtype=np.uint16
        )

        # Update time offset for continuous signal
        self.time_offset += self.SAMPLES_PER_PACKET / self.SAMPLING_FREQ

        return adc_values

    def calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC16 (must match STM32 algorithm)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def build_packet(
        self, voltage_samples: np.ndarray, current_samples: np.ndarray
    ) -> bytes:
        """
        Build packet with exact STM32 protocol format

        Packet structure:
        - Start Marker (2 bytes): 0xFFFF
        - Sequence Number (2 bytes): uint16
        - Sample Count (2 bytes): uint16
        - Voltage Data (N×2 bytes): uint16 array
        - Current Data (N×2 bytes): uint16 array
        - Checksum (2 bytes): CRC16
        - End Marker (2 bytes): 0xFFFE
        """
        # Header
        header = struct.pack(
            "<HHH", self.START_MARKER, self.sequence, len(voltage_samples)
        )

        # Data (voltage + current)
        voltage_bytes = voltage_samples.tobytes()
        current_bytes = current_samples.tobytes()
        data_bytes = voltage_bytes + current_bytes

        # Calculate checksum over header (after start marker) + data
        checksum_data = header[2:] + data_bytes  # Skip start marker
        checksum = self.calculate_crc16(checksum_data)

        # Trailer
        trailer = struct.pack("<HH", checksum, self.END_MARKER)

        # Complete packet
        packet = header + data_bytes + trailer

        self.sequence = (self.sequence + 1) & 0xFFFF  # Wrap at 65535

        return packet

    def transmit_packet(self, voltage_samples: np.ndarray, current_samples: np.ndarray):
        """Build and transmit one packet"""
        packet = self.build_packet(voltage_samples, current_samples)
        self.serial.write(packet)
        self.serial.flush()

    def run_simulation(self, duration: float = None):
        """
        Run simulation with configuration from simulator_config.py
        """
        # Extract harmonics from config
        voltage_harmonics = {
            int(k.split("_")[1]): v
            for k, v in VOLTAGE.items()
            if k.startswith("harmonic_") and v > 0
        }

        current_harmonics = {
            int(k.split("_")[1]): v
            for k, v in CURRENT.items()
            if k.startswith("harmonic_") and v > 0
        }

        # Get phase shift in radians
        phase_shift_deg = CURRENT.get("phase_shift", 0.0)
        phase_shift_rad = np.deg2rad(phase_shift_deg)

        # Display configuration
        print("\n" + "=" * 60)
        print("STM32 Power Meter Simulator")
        print("=" * 60)

        # Display sensor configuration
        print("\nSensor Configuration:")
        print(f"  Voltage Sensor: {VOLTAGE_SENSOR['name']}")
        print(f"    Scaling: {VOLTAGE_SENSOR['scaling_factor']:.6f} V_sensor/V_mains")
        print(f"    DC Bias: {VOLTAGE_SENSOR['dc_bias']:.2f} V")
        print(f"    Max Input: {VOLTAGE_SENSOR['max_value']:.0f} V AC")

        print(f"  Current Sensor: {CURRENT_SENSOR['name']}")
        print(f"    Sensitivity: {CURRENT_SENSOR['sensitivity']:.3f} V/A")
        print(f"    DC Bias: {CURRENT_SENSOR['dc_bias']:.2f} V")
        print(f"    Max Current: ±{CURRENT_SENSOR['max_value']:.0f} A")

        # Display waveform configuration
        print("\nVoltage Waveform:")
        print(f"  RMS: {VOLTAGE['rms']:.3f} V (sensor output)")
        if voltage_harmonics:
            print(f"  Harmonics: {voltage_harmonics}")
        else:
            print("  Harmonics: None (clean sine wave)")

        print("\nCurrent Waveform:")
        print(f"  RMS: {CURRENT['rms']:.3f} V (sensor output)")
        print(
            f"  Phase shift: {phase_shift_deg:.1f}° {'(lag)' if phase_shift_deg < 0 else '(lead)' if phase_shift_deg > 0 else '(in phase)'}"
        )
        if current_harmonics:
            print(f"  Harmonics: {current_harmonics}")
        else:
            print("  Harmonics: None (clean sine wave)")

        print(f"\nPort: {self.port} @ {self.baudrate} baud")
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")

        start_time = time.time()
        packet_count = 0

        try:
            while True:
                # Generate voltage and current waveforms (with sensor-specific DC bias)
                voltage_adc = self.generate_sine_wave(
                    amplitude_rms=VOLTAGE["rms"],
                    dc_bias=VOLTAGE_SENSOR["dc_bias"],
                    phase=0.0,
                    harmonics=voltage_harmonics if voltage_harmonics else None,
                )

                current_adc = self.generate_sine_wave(
                    amplitude_rms=CURRENT["rms"],
                    dc_bias=CURRENT_SENSOR["dc_bias"],
                    phase=phase_shift_rad,
                    harmonics=current_harmonics if current_harmonics else None,
                )

                # Transmit packet
                self.transmit_packet(voltage_adc, current_adc)
                packet_count += 1

                # Timing: 1000 samples at 10kHz = 100ms per packet
                time.sleep(0.100)

                # Status update every 10 packets (1 second)
                if packet_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(
                        f"  Sent {packet_count} packets ({elapsed:.1f}s, {packet_count / elapsed:.1f} pkt/s)"
                    )

                # Stop if duration specified
                if duration and (time.time() - start_time) >= duration:
                    break

        except KeyboardInterrupt:
            print("\nStopped by user")


def main():
    parser = argparse.ArgumentParser(
        description="STM32 Power Meter Simulator - Configuration in simulator_config.py"
    )

    parser.add_argument(
        "--port", required=True, help="Serial port (e.g., /dev/pts/3, COM3)"
    )
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate")
    parser.add_argument(
        "--duration", type=float, help="Duration in seconds (default: infinite)"
    )

    args = parser.parse_args()

    # Create simulator
    sim = STM32Simulator(port=args.port, baudrate=args.baud)

    if not sim.connect():
        return

    try:
        sim.run_simulation(args.duration)
    finally:
        sim.disconnect()


if __name__ == "__main__":
    main()
