import struct
import time

import numpy as np
import serial

# Import from config modules
from config import ADC_CONFIG
from simulator.config import CURRENT, DC_BIAS, VOLTAGE


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
    VREF = ADC_CONFIG["vref"]  # VREF in mV

    def __init__(self, port: str, baudrate: int):
        """
        Initialize STM32 simulator

        Args:
            port: Serial port path
            baudrate: Communication baud rate
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.sequence = 0
        self.time_offset = 0.0
        self.vref_mv = self.VREF

        # Calculate realistic UART transmission time
        # Each byte = 10 bits (1 start + 8 data + 1 stop)
        # Packet size = 8 + (samples_per_packet × 4) + 4 bytes
        packet_size = 8 + (self.SAMPLES_PER_PACKET * 4) + 4
        self.uart_tx_time = (packet_size * 10) / baudrate  # seconds

        # ADC sampling period (time to collect one packet worth of samples)
        self.sampling_period = self.SAMPLES_PER_PACKET / self.SAMPLING_FREQ  # seconds

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
        """Convert voltage (mV) to ADC value (0-65535) using actual VREF

        Args:
            voltage: Voltage in millivolts

        Returns:
            ADC value (16-bit: 0-65535)
        """
        adc = int((voltage / self.vref_mv) * self.ADC_MAX)
        return np.clip(adc, 0, self.ADC_MAX)

    def ac_to_adc(self, ac_voltage: float, dc_bias: float) -> int:
        """Convert AC voltage to DC-biased ADC value

        Args:
            ac_voltage: AC voltage component in Volts
            dc_bias: DC bias voltage in Volts (sensor-specific)

        Returns:
            ADC value (16-bit)
        """
        total_voltage = dc_bias + ac_voltage
        total_voltage_mv = total_voltage * 1000  # Convert to mV
        return self.voltage_to_adc(total_voltage_mv)

    def generate_sine_wave(
        self,
        amplitude_rms: float,
        dc_bias: float,
        phase: float = 0.0,
        harmonics: dict = None,
        harmonic_phases: dict = None,
        update_time_offset: bool = False,
    ) -> np.ndarray:
        """
        Generate sine wave samples for one packet

        Args:
            amplitude_rms: RMS voltage amplitude in Volts
            dc_bias: DC bias voltage in Volts (sensor-specific)
            phase: Phase offset in radians (fundamental)
            harmonics: Dict of {harmonic_num: amplitude_fraction}
                      e.g., {3: 0.2, 5: 0.1} adds 20% 3rd and 10% 5th harmonic
            harmonic_phases: Dict of {harmonic_num: phase_in_degrees}
                           e.g., {3: 45.0, 5: -30.0} for harmonic phase shifts
            update_time_offset: If True, increment time offset (call only once per packet)

        Returns:
            Array of ADC values (16-bit unsigned)
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
                    # Get harmonic phase shift (default to 0 if not specified)
                    harmonic_phase = 0.0
                    if harmonic_phases and harmonic_num in harmonic_phases:
                        harmonic_phase = np.deg2rad(harmonic_phases[harmonic_num])

                    signal += (
                        amplitude_peak
                        * harmonic_amplitude
                        * np.sin(2 * np.pi * harmonic_freq * t + harmonic_phase)
                    )

        # Convert to ADC values (using sensor-specific DC bias)
        adc_values = np.array(
            [self.ac_to_adc(v, dc_bias) for v in signal], dtype=np.uint16
        )

        # Update time offset for continuous signal (only after both channels generated)
        if update_time_offset:
            self.time_offset += self.SAMPLES_PER_PACKET / self.SAMPLING_FREQ

        return adc_values

    def calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC16-Modbus (must match STM32 algorithm)"""
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
        Build packet with STM32 protocol format

        Packet structure:
        - Start Marker (2 bytes): 0xFFFF
        - Sequence Number (2 bytes): uint16
        - Sample Count (2 bytes): uint16
        - VREF (2 bytes): uint16 in millivolts
        - Voltage Data (N×2 bytes): uint16 array
        - Current Data (N×2 bytes): uint16 array
        - Checksum (2 bytes): CRC16
        - End Marker (2 bytes): 0xFFFE

        Total: 8 + (N×4) + 4 bytes
        """
        # Header (8 bytes total)
        header = struct.pack(
            "<HHHH",
            self.START_MARKER,  # 0xFFFF
            self.sequence,  # Packet counter
            len(voltage_samples),  # Sample count
            self.vref_mv,  # VDDA voltage in mV (from VREFINT)
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
        """Build and transmit one packet with realistic UART timing"""
        packet = self.build_packet(voltage_samples, current_samples)

        # Throttle transmission to simulate realistic UART timing
        # Send data in chunks with delays to make receiver's read_packet_bytes
        # take realistic time (~44ms at 921600 baud)
        chunk_size = 128  # bytes per chunk (smaller = more realistic)
        bytes_per_second = self.baudrate / 10  # 10 bits per byte
        chunk_delay = chunk_size / bytes_per_second  # seconds per chunk

        for i in range(0, len(packet), chunk_size):
            chunk = packet[i : i + chunk_size]
            self.serial.write(chunk)
            self.serial.flush()
            # Sleep to throttle transmission (except after last chunk)
            if i + chunk_size < len(packet):
                time.sleep(chunk_delay)

    def run_simulation(self):
        """
        Run simulation continuously with configuration from simulator.config
        """
        # Extract harmonics amplitudes from config
        voltage_harmonics = {
            int(k.split("_")[1]): v
            for k, v in VOLTAGE.items()
            if k.startswith("harmonic_") and not k.endswith("_phase") and v > 0
        }

        current_harmonics = {
            int(k.split("_")[1]): v
            for k, v in CURRENT.items()
            if k.startswith("harmonic_") and not k.endswith("_phase") and v > 0
        }

        # Extract harmonic phases from config
        voltage_harmonic_phases = {
            int(k.split("_")[1]): v
            for k, v in VOLTAGE.items()
            if k.endswith("_phase") and k.startswith("harmonic_")
        }

        current_harmonic_phases = {
            int(k.split("_")[1]): v
            for k, v in CURRENT.items()
            if k.endswith("_phase") and k.startswith("harmonic_")
        }

        # Get phase shift in radians
        phase_shift_deg = CURRENT.get("phase_shift", 0.0)
        phase_shift_rad = np.deg2rad(phase_shift_deg)

        # Display configuration
        print("\n" + "=" * 60)
        print("STM32 Power Meter Simulator")
        print("=" * 60)

        # Display ADC configuration
        print("\nADC Configuration:")
        print(f"  Resolution: {self.ADC_BITS}-bit (0-{self.ADC_MAX})")
        print(f"  VREF: {self.vref_mv} mV")
        print(f"  Sampling Rate: {self.SAMPLING_FREQ} Hz")
        print(f"  DC Bias: {DC_BIAS:.2f} V")

        # Display timing information
        print("\nTiming:")
        print(
            f"  Sampling period: {self.sampling_period * 1000:.1f} ms ({self.SAMPLES_PER_PACKET} samples)"
        )
        print(
            f"  UART TX time: {self.uart_tx_time * 1000:.1f} ms (at {self.baudrate} baud)"
        )
        print(f"  Packet rate: {1 / self.sampling_period:.1f} pkt/s")

        # Display waveform configuration
        print("\nVoltage Waveform:")
        print(f"  RMS: {VOLTAGE['rms']:.3f} V")
        if voltage_harmonics:
            print("  Harmonics:")
            for h_num in sorted(voltage_harmonics.keys()):
                amp = voltage_harmonics[h_num]
                phase = voltage_harmonic_phases.get(h_num, 0.0)
                print(f"    {h_num}: {amp:.3f} @ {phase:+.1f}°")
        else:
            print("  Harmonics: None (clean sine wave)")

        print("\nCurrent Waveform:")
        print(f"  RMS: {CURRENT['rms']:.3f} V")
        print(
            f"  Phase shift: {phase_shift_deg:.1f}° {'(lag)' if phase_shift_deg < 0 else '(lead)' if phase_shift_deg > 0 else '(in phase)'}"
        )
        if current_harmonics:
            print("  Harmonics:")
            for h_num in sorted(current_harmonics.keys()):
                amp = current_harmonics[h_num]
                phase = current_harmonic_phases.get(h_num, 0.0)
                print(f"    {h_num}: {amp:.3f} @ {phase:+.1f}°")
        else:
            print("  Harmonics: None (clean sine wave)")

        print(f"\nPort: {self.port} @ {self.baudrate} baud")
        print(f"Packet size: {8 + self.SAMPLES_PER_PACKET * 4 + 4} bytes")
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")

        start_time = time.time()
        packet_count = 0

        try:
            while True:
                # Generate voltage and current waveforms
                voltage_adc = self.generate_sine_wave(
                    amplitude_rms=VOLTAGE["rms"],
                    dc_bias=DC_BIAS,
                    phase=0.0,
                    harmonics=voltage_harmonics if voltage_harmonics else None,
                    harmonic_phases=voltage_harmonic_phases
                    if voltage_harmonic_phases
                    else None,
                    update_time_offset=False,  # Don't update yet
                )

                current_adc = self.generate_sine_wave(
                    amplitude_rms=CURRENT["rms"],
                    dc_bias=DC_BIAS,
                    phase=phase_shift_rad,
                    harmonics=current_harmonics if current_harmonics else None,
                    harmonic_phases=current_harmonic_phases
                    if current_harmonic_phases
                    else None,
                    update_time_offset=True,  # Update after both channels generated
                )

                # Transmit packet (throttled transmission, takes ~44ms)
                tx_start = time.time()
                self.transmit_packet(voltage_adc, current_adc)
                tx_elapsed = time.time() - tx_start
                packet_count += 1

                # Sleep for remaining time to match sampling period
                # Packet should arrive every ~100ms (sampling period)
                remaining_time = self.sampling_period - tx_elapsed
                if remaining_time > 0:
                    time.sleep(remaining_time)

                # Status update every 10 packets (1 second)
                if packet_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(
                        f"  Sent {packet_count} packets ({elapsed:.1f}s, {packet_count / elapsed:.1f} pkt/s)"
                    )

        except KeyboardInterrupt:
            print("\nStopped by user")

        finally:
            elapsed = time.time() - start_time
            print("\nSimulation Summary:")
            print(f"  Total packets: {packet_count}")
            print(f"  Duration: {elapsed:.1f}s")
            print(f"  Rate: {packet_count / elapsed:.2f} pkt/s")
