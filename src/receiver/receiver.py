import struct
import time

import numpy as np
import plotly.graph_objects as go
import serial
from plotly.subplots import make_subplots

from config import ADC_CONFIG
from utils import PRINT_STATS, measure_time, print_performance_stats


class ADCReceiver:
    """Receives and parses ADC data from STM32"""

    # Protocol constants (must match STM32)
    START_MARKER = 0xFFFF
    END_MARKER = 0xFFFE
    EXPECTED_SAMPLES = ADC_CONFIG["samples_per_packet"]
    ANALYSIS_WINDOW = 2048  # IEC 61000-4-7 compliant: 200ms at 10.24kHz (2^11 samples)
    ADC_TO_MV_SCALE = ADC_CONFIG["max_value"] * 1000.0  # Precomputed: 65535000.0

    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.packet_count = 0
        self.error_count = 0
        self.last_sequence = None
        self.start_time = None

        self.voltage_buffer = []
        self.current_buffer = []
        self.analysis_count = 0
        self.current_vref_mv = ADC_CONFIG["vref"]  # updated from packets if available

    @staticmethod
    def calculate_crc16(data: bytes) -> int:
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

    def connect(self) -> bool:
        """Open serial port connection"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )

            time.sleep(0.1)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            time.sleep(0.2)

            return True
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            return False

    def disconnect(self):
        """Close serial port connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()

    def find_sync(self):
        """Search for start marker in byte stream"""
        sync_bytes = struct.pack("<H", self.START_MARKER)

        while True:
            byte = self.serial.read(1)
            if not byte:
                continue

            if byte == sync_bytes[0:1]:
                next_byte = self.serial.read(1)
                if next_byte == sync_bytes[1:2]:
                    return  # Found sync marker

    @measure_time
    def read_packet_bytes(self):
        """Read raw packet bytes from serial (I/O operation)"""
        # Read header (after start marker)
        header = self.serial.read(6)  # seq(2) + count(2) + vref_mv(2)
        if len(header) != 6:
            self.error_count += 1
            return None

        # Quick parse of sample count to know how much data to read
        _, sample_count, _ = struct.unpack("<HHH", header)
        if sample_count != self.EXPECTED_SAMPLES:
            self.error_count += 1
            return None

        # Read dual-channel ADC data: voltage_data[N] + current_data[N]
        voltage_bytes = self.serial.read(sample_count * 2)
        if len(voltage_bytes) != sample_count * 2:
            self.error_count += 1
            return None

        current_bytes = self.serial.read(sample_count * 2)
        if len(current_bytes) != sample_count * 2:
            self.error_count += 1
            return None

        # Read checksum and end marker
        trailer = self.serial.read(4)
        if len(trailer) != 4:
            self.error_count += 1
            return None

        return {
            "header": header,
            "voltage_bytes": voltage_bytes,
            "current_bytes": current_bytes,
            "trailer": trailer,
        }

    @measure_time
    def parse_packet(self, raw_packet: dict):
        """Parse and validate packet data (CPU processing)"""
        header = raw_packet["header"]
        voltage_bytes = raw_packet["voltage_bytes"]
        current_bytes = raw_packet["current_bytes"]
        trailer = raw_packet["trailer"]

        # Unpack header
        sequence, sample_count, vref_mv = struct.unpack("<HHH", header)

        # Unpack trailer
        checksum, end_marker = struct.unpack("<HH", trailer)

        # Verify end marker
        if end_marker != self.END_MARKER:
            self.error_count += 1
            return None

        # Verify checksum (header + data)
        data_bytes = voltage_bytes + current_bytes
        calculated_crc = self.calculate_crc16(header + data_bytes)
        if calculated_crc != checksum:
            self.error_count += 1
            return None

        # Track sequence for dropped packet detection
        if self.last_sequence is not None:
            expected_seq = (self.last_sequence + 1) & 0xFFFF
            if sequence != expected_seq:
                dropped = (sequence - expected_seq) & 0xFFFF
                self.error_count += dropped

        self.last_sequence = sequence
        self.packet_count += 1

        # Unpack samples
        voltage_samples = struct.unpack(f"<{sample_count}H", voltage_bytes)
        current_samples = struct.unpack(f"<{sample_count}H", current_bytes)

        return {
            "sequence": sequence,
            "voltage": list(voltage_samples),
            "current": list(current_samples),
            "vref_mv": vref_mv,
            "timestamp": time.time(),
        }

    def read_packet(self):
        """Read and parse one complete packet"""
        self.find_sync()

        raw_packet = self.read_packet_bytes()
        if raw_packet is None:
            return None

        return self.parse_packet(raw_packet)

    @measure_time
    def process_analysis_window(self, voltage: list, current: list, vdda_mv: int):
        """
        Execute power analysis on 2048-sample window (200ms at 10.24kHz).
        IEC 61000-4-7 compliant analysis window with perfect 2^11 FFT alignment.
        """
        # uint16_t ADC samples
        voltage_array = np.array(voltage, dtype=np.float64)
        current_array = np.array(current, dtype=np.float64)

        # float samples
        scale_factor = vdda_mv / self.ADC_TO_MV_SCALE
        voltage_v = voltage_array * scale_factor
        current_v = current_array * scale_factor

        v_mean = np.mean(voltage_v)
        v_rms = np.sqrt(np.mean(voltage_v**2))
        i_mean = np.mean(current_v)
        i_rms = np.sqrt(np.mean(current_v**2))

        v_mean_adc = np.mean(voltage_array)
        v_rms_adc = np.sqrt(np.mean(voltage_array**2))
        i_mean_adc = np.mean(current_array)
        i_rms_adc = np.sqrt(np.mean(current_array**2))

        return {
            "v_mean_adc": v_mean_adc,
            "v_rms_adc": v_rms_adc,
            "i_mean_adc": i_mean_adc,
            "i_rms_adc": i_rms_adc,
            "v_mean": v_mean,
            "v_rms": v_rms,
            "i_mean": i_mean,
            "i_rms": i_rms,
        }

    def plot_samples(self, voltage: list, current: list, vdda_mv: int):
        # Convert ADC samples to voltage using vectorized NumPy operations
        scale_factor = vdda_mv / self.ADC_TO_MV_SCALE
        voltage_v = (np.array(voltage, dtype=np.float64) * scale_factor).tolist()
        current_v = (np.array(current, dtype=np.float64) * scale_factor).tolist()

        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=(
                f"Channel 1 (Voltage) - {len(voltage)} samples, 200ms",
                f"Channel 2 (Current) - {len(current)} samples, 200ms",
            ),
            vertical_spacing=0.12,
        )

        fig.add_trace(
            go.Scattergl(
                x=list(range(len(voltage_v))),
                y=voltage_v,
                mode="markers",
                marker=dict(size=2, opacity=0.6),
                name="CH1",
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scattergl(
                x=list(range(len(current_v))),
                y=current_v,
                mode="markers",
                marker=dict(size=2, opacity=0.6),
                name="CH2",
            ),
            row=2,
            col=1,
        )

        fig.update_xaxes(title_text="Sample", row=2, col=1)
        fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
        fig.update_yaxes(title_text="Voltage (V)", row=2, col=1)
        fig.update_layout(
            height=600, showlegend=False, title_text="Voltage Samples Analysis Window"
        )
        fig.show()

    def receive_continuous(self, plot_first_window: bool = False):
        self.start_time = time.time()
        plotted = False

        print(f"Receiving data from {self.port} at {self.baudrate} baud...")
        print("Waiting for sync...")

        # Initial sync - wait for first valid packet
        sync_attempts = 0
        first_packet = None
        while first_packet is None and sync_attempts < 10:
            first_packet = self.read_packet()
            if first_packet is None:
                sync_attempts += 1
                if sync_attempts % 3 == 0:
                    print(f"  Still waiting for sync... (attempt {sync_attempts})")
                    # Flush buffers and try again
                    self.serial.reset_input_buffer()
                time.sleep(0.1)

        if first_packet is None:
            print("ERROR: Could not establish sync after 10 attempts")
            print("Make sure device is running and sending data.")
            return

        print("Synced. Receiving packets...\n")

        # Process the first packet
        self.voltage_buffer.extend(first_packet["voltage"])
        self.current_buffer.extend(first_packet["current"])

        while True:
            packet = self.read_packet()
            if packet:
                # Update current VREF value
                self.current_vref_mv = packet["vref_mv"]

                # Accumulate dual-channel samples
                self.voltage_buffer.extend(packet["voltage"])
                self.current_buffer.extend(packet["current"])

                # Process complete analysis windows
                if len(self.voltage_buffer) >= self.ANALYSIS_WINDOW:
                    voltage_window = self.voltage_buffer[: self.ANALYSIS_WINDOW]
                    current_window = self.current_buffer[: self.ANALYSIS_WINDOW]
                    self.voltage_buffer = self.voltage_buffer[self.ANALYSIS_WINDOW :]
                    self.current_buffer = self.current_buffer[self.ANALYSIS_WINDOW :]

                    # DEBUG: Plot first analysis window
                    if plot_first_window and not plotted:
                        self.plot_samples(
                            voltage_window, current_window, self.current_vref_mv
                        )
                        plotted = True

                    # Get statistics from this window
                    stats = self.process_analysis_window(
                        voltage_window, current_window, self.current_vref_mv
                    )
                    self.analysis_count += 1

                    elapsed = time.time() - self.start_time
                    print(
                        f"[{elapsed:6.1f}s] CH1_rms={stats['v_rms']:5.3f}V, CH2_rms={stats['i_rms']:5.3f}V, VREF={self.current_vref_mv:4d}mV, Pkts={self.packet_count:4d}, Err={self.error_count:2d}, Win={self.analysis_count:4d}"
                    )

    def print_summary(self):
        """Print summary statistics"""
        if self.start_time is None:
            return

        elapsed = time.time() - self.start_time
        if elapsed > 0:
            print("\n" + "=" * 60)
            print("Summary:")
            print(f"  Total packets received: {self.packet_count}")
            print(f"  Analysis windows processed: {self.analysis_count}")
            print(f"  Errors: {self.error_count}")
            print(f"  Duration: {elapsed:.1f}s")
            print(f"  Packet rate: {self.packet_count / elapsed:.1f} packets/s")
            print(f"  Analysis rate: {self.analysis_count / elapsed:.1f} windows/s")
            print("  Expected analysis rate: 5.0 windows/s (200ms per window)")
            print("=" * 60)

        # Print performance statistics if enabled
        if PRINT_STATS:
            print_performance_stats()
