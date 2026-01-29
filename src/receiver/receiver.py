import struct
import time

import numpy as np
import plotly.graph_objects as go
import serial
from plotly.subplots import make_subplots

from config import ADC_CONFIG


class ADCReceiver:
    """Receives and parses ADC data from STM32"""

    # Protocol constants (must match STM32)
    START_MARKER = 0xFFFF
    END_MARKER = 0xFFFE
    EXPECTED_SAMPLES = ADC_CONFIG[
        "samples_per_packet"
    ]  # Samples per channel per packet
    ANALYSIS_WINDOW = (
        2048  # IEC 61000-4-7 compliant: 200ms at 10.24kHz (2^11 samples - perfect FFT)
    )

    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.packet_count = 0
        self.error_count = 0
        self.last_sequence = None
        self.start_time = None

        # Sample accumulation for 2-buffer analysis window (dual-channel)
        self.voltage_buffer = []
        self.current_buffer = []
        self.analysis_count = 0
        self.current_vref_mv = 3300  # Most recent VREF value from packets

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
            # Give port time to stabilize
            time.sleep(0.1)

            # Clear any stale data from buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            # Wait a bit more for simulator to start sending
            time.sleep(0.2)

            return True
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            return False

    def disconnect(self):
        """Close serial port"""
        if self.serial and self.serial.is_open:
            self.serial.close()

    def find_sync(self, max_bytes=None):
        """Search for start marker in byte stream

        Args:
            max_bytes: Maximum bytes to check before giving up (None = unlimited)
        """
        sync_bytes = struct.pack("<H", self.START_MARKER)
        bytes_checked = 0

        while max_bytes is None or bytes_checked < max_bytes:
            byte = self.serial.read(1)
            if not byte:
                # Timeout - keep trying in continuous mode
                if max_bytes is None:
                    continue
                return False
            bytes_checked += 1

            if byte == sync_bytes[0:1]:
                next_byte = self.serial.read(1)
                if next_byte == sync_bytes[1:2]:
                    return True
                if next_byte:
                    bytes_checked += 1

        return False

    def calculate_crc16(self, data):
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

    def read_packet(self):
        """Read and parse one complete packet"""
        if not self.find_sync():
            return None

        # Read header (after start marker)
        header = self.serial.read(6)  # seq(2) + count(2) + vref_mv(2)
        if len(header) != 6:
            self.error_count += 1
            return None

        sequence, sample_count, vref_mv = struct.unpack("<HHH", header)

        # Validate sample count
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

        # Combine for checksum calculation
        data_bytes = voltage_bytes + current_bytes

        # Read checksum and end marker
        trailer = self.serial.read(4)
        if len(trailer) != 4:
            self.error_count += 1
            return None

        checksum, end_marker = struct.unpack("<HH", trailer)

        # Verify end marker
        if end_marker != self.END_MARKER:
            self.error_count += 1
            return None

        # Verify checksum (header: seq + count)
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

        # Parse dual-channel ADC data
        voltage_samples = struct.unpack(f"<{sample_count}H", voltage_bytes)
        current_samples = struct.unpack(f"<{sample_count}H", current_bytes)

        return {
            "sequence": sequence,
            "voltage": list(voltage_samples),
            "current": list(current_samples),
            "vref_mv": vref_mv,
            "timestamp": time.time(),
        }

    def adc_to_voltage(self, adc_value: float, vdda_mv: float) -> float:
        """Convert ADC value to voltage (V)

        Args:
            adc_value: Raw ADC value (0-65535)
            vdda_mv: Reference voltage in millivolts (from VREFINT calibration)

        Returns:
            float: Voltage in range 0-3.3V
        """
        return (adc_value / ADC_CONFIG["max_value"]) * (vdda_mv / 1000.0)

    def adc_to_current(self, adc_value: float, vdda_mv: float) -> float:
        """Convert ADC value to voltage (V)

        Note: This converts to voltage, not current, as sensor is not yet applied.
        Current channel ADC also outputs 0-VDDA range.

        Args:
            adc_value: Raw ADC value (0-65535)
            vdda_mv: Reference voltage in millivolts (from VREFINT calibration)

        Returns:
            float: Voltage in range 0-3.3V
        """
        return (adc_value / ADC_CONFIG["max_value"]) * (vdda_mv / 1000.0)

    def process_analysis_window(self, voltage: list, current: list, vdda_mv: float):
        """
        Execute power analysis on 2048-sample window (200ms at 10.24kHz).
        IEC 61000-4-7 compliant analysis window with perfect 2^11 FFT alignment.

        Args:
            voltage: List of 2048 voltage ADC samples (ADC1)
            current: List of 2048 current ADC samples (ADC2)
            vdda_mv: Reference voltage in millivolts (from VREFINT calibration)

        Returns:
            dict: Statistics including mean and RMS values
        """
        voltage_array = np.array(voltage, dtype=np.float64)
        current_array = np.array(current, dtype=np.float64)

        # Calculate statistics in ADC domain
        v_mean_adc = np.mean(voltage_array)
        v_rms_adc = np.sqrt(np.mean(voltage_array**2))
        i_mean_adc = np.mean(current_array)
        i_rms_adc = np.sqrt(np.mean(current_array**2))

        # Convert to physical units using calibrated VDDA
        v_mean = self.adc_to_voltage(v_mean_adc, vdda_mv)
        v_rms = self.adc_to_voltage(v_rms_adc, vdda_mv)
        i_mean = self.adc_to_current(i_mean_adc, vdda_mv)
        i_rms = self.adc_to_current(i_rms_adc, vdda_mv)

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

    def plot_samples(self, voltage: list, current: list, vdda_mv: float = 3300.0):
        """
        Debug function: Plot voltage and current samples (one-time scatter plot)

        Args:
            voltage: List of voltage ADC samples
            current: List of current ADC samples
            vdda_mv: Actual VDDA voltage in millivolts (from VREFINT calibration)
        """
        # Convert ADC samples to voltage values using calibrated VDDA
        voltage_v = [self.adc_to_voltage(v, vdda_mv) for v in voltage]
        current_v = [self.adc_to_current(c, vdda_mv) for c in current]

        # Create subplots with Plotly
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=(
                f"Channel 1 (Voltage) - {len(voltage)} samples, 200ms",
                f"Channel 2 (Current) - {len(current)} samples, 200ms",
            ),
            vertical_spacing=0.12,
        )

        # Voltage scatter plot
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

        # Current scatter plot
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

        # Update layout
        fig.update_xaxes(title_text="Sample", row=2, col=1)
        fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
        fig.update_yaxes(title_text="Voltage (V)", row=2, col=1)

        fig.update_layout(
            height=600, showlegend=False, title_text="Voltage Samples Analysis Window"
        )

        fig.show()

    def receive_continuous(self, plot_first_window: bool = False):
        """Continuously receive packets and calculates stats every 1 second

        Args:
            plot_first_window: If True, plot the first complete analysis window
        """

        self.start_time = time.time()
        last_print_time = time.time()

        # Accumulators for 1-second averaging
        v_mean_sum = 0.0
        i_mean_sum = 0.0
        sample_count = 0

        # Debug flag - plot first analysis window if requested
        plotted = False

        print(f"Receiving data from {self.port} at {self.baudrate} baud...")
        print("Waiting for sync...")

        # Initial sync - be patient and wait for first valid packet
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

                    # Use calibrated VDDA from most recent packet
                    vref_mv = self.current_vref_mv

                    # DEBUG: Plot first analysis window
                    if plot_first_window and not plotted:
                        self.plot_samples(voltage_window, current_window, vref_mv)
                        plotted = True

                    # Get statistics from this window
                    stats = self.process_analysis_window(voltage_window, current_window, vref_mv)

                    # Accumulate for 1-second average (using converted values)
                    v_mean_sum += stats["v_rms"]  # Use RMS for AC measurements
                    i_mean_sum += stats["i_rms"]
                    sample_count += 1

                # Print average every 1 second
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    if sample_count > 0:
                        v_avg = v_mean_sum / sample_count
                        i_avg = i_mean_sum / sample_count
                        elapsed = current_time - self.start_time
                        print(
                            f"[{elapsed:6.1f}s] CH1_rms={v_avg:5.3f}V, CH2_rms={i_avg:5.3f}V, VREF={self.current_vref_mv:4d}mV, Pkts={self.packet_count:4d}, Err={self.error_count:2d}"
                        )

                        # Reset accumulators
                        v_mean_sum = 0.0
                        i_mean_sum = 0.0
                        sample_count = 0

                    last_print_time = current_time


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
