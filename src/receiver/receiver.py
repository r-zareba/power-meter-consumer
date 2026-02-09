import struct
import time
from datetime import datetime
from typing import List, Optional

import serial

from analytics.aggregation import create_aggregate_message
from analytics.plots import plot_raw_adc_samples
from analytics.power_analyzer import PowerAnalyzer
from config import ADC_CONFIG
from messaging.mqtt_publisher import MQTTPublisher
from models.mqtt_message import AggregateMessage
from models.power_measurement import PowerMeasurement
from storage.sqlite_manager import SQLiteManager
from utils import PRINT_STATS, measure_time, print_performance_stats


class ADCReceiver:
    """Receives and parses ADC data from STM32"""

    # Protocol constants (must match STM32)
    START_MARKER = 0xFFFF
    END_MARKER = 0xFFFE
    EXPECTED_SAMPLES = ADC_CONFIG["samples_per_packet"]
    ANALYSIS_WINDOW = 2048  # IEC 61000-4-7 compliant: 200ms at 10.24kHz (2^11 samples)
    ADC_TO_MV_SCALE = ADC_CONFIG["max_value"] * 1000.0  # Precomputed: 65535000.0
    MAINS_FREQ = 50.0  # Hz
    SAMPLING_FREQ = ADC_CONFIG["sampling_freq"]  # 10256 Hz
    N_SERIAL_SYNC_RETRIES = 10

    def __init__(
        self,
        port: str,
        baudrate: int,
        power_analyzer: PowerAnalyzer,
        db_manager: Optional[SQLiteManager] = None,
        mqtt_publisher: Optional[MQTTPublisher] = None,
        print_measurements: bool = False,
    ):
        """
        Initialize ADC Receiver.

        Args:
            port: Serial port path
            baudrate: Serial baudrate
            power_analyzer: Power analysis engine
            db_manager: SQLite database manager for storing measurements
            mqtt_publisher: MQTT publisher for 1-second aggregates
            print_measurements: If True, print every 200ms measurement; if False, print 1-second aggregates
        """
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

        # Analysis and storage dependencies
        self.power_analyzer = power_analyzer
        self.db_manager = db_manager
        self.mqtt_publisher = mqtt_publisher
        self.print_measurements = print_measurements

        # Buffer for 1-second aggregation (5 × 200ms measurements)
        self.measurement_buffer: List[PowerMeasurement] = []

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
    def analyze_power_window(
        self, voltage: list, current: list, vdda_mv: int, timestamp: datetime
    ) -> PowerMeasurement:
        """Helper method to track power analysis timing."""
        return self.power_analyzer.analyze_window(voltage, current, vdda_mv, timestamp)

    @measure_time
    def store_measurement(self, measurement: PowerMeasurement) -> None:
        """Helper method to track database insert timing."""
        if self.db_manager:
            self.db_manager.insert(measurement)

    @measure_time
    def create_aggregate(
        self, measurements: List[PowerMeasurement]
    ) -> AggregateMessage:
        """Helper method to track aggregation timing."""
        if self.mqtt_publisher:
            device_id = self.mqtt_publisher.device_id
        else:
            device_id = "test"
        return create_aggregate_message(measurements, device_id, self.MAINS_FREQ)

    @measure_time
    def publish_aggregate(self, aggregate: AggregateMessage) -> None:
        """Helper method to track MQTT publish timing."""
        if self.mqtt_publisher:
            self.mqtt_publisher.publish(aggregate)

    def handle_measurement(self, measurement: PowerMeasurement) -> None:
        """
        Handle a new 200ms measurement: store in DB and buffer for aggregation.

        Args:
            measurement: PowerMeasurement to process
        """
        # 1. Insert into SQLite database
        self.store_measurement(measurement)

        # 2. Add to buffer for 1-second aggregation
        self.measurement_buffer.append(measurement)

        # 3. If buffer is full (5 measurements = 1 second), publish aggregate
        if len(self.measurement_buffer) >= 5:
            aggregate = self.create_aggregate(self.measurement_buffer)

            self.publish_aggregate(aggregate)
            
            # Print aggregate data (every 1 second)
            if not self.print_measurements:
                self._print_aggregate(aggregate)

            # Clear buffer for next second
            self.measurement_buffer.clear()

    def receive_continuous(self, plot_first_window: bool = False):
        self.start_time = time.time()
        plotted = False

        print(f"Receiving data from {self.port} at {self.baudrate} baud...")
        print("Waiting for sync...")

        # Initial sync - wait for first valid packet
        sync_attempts = 0
        first_packet = None
        while first_packet is None and sync_attempts < self.N_SERIAL_SYNC_RETRIES:
            first_packet = self.read_packet()
            if first_packet is None:
                sync_attempts += 1
                if sync_attempts % 3 == 0:
                    print(f"  Still waiting for sync... (attempt {sync_attempts})")
                    self.serial.reset_input_buffer()
                time.sleep(0.1)

        if first_packet is None:
            print(
                f"ERROR: Could not establish sync after {self.N_SERIAL_SYNC_RETRIES} attempts"
            )
            print("Make sure device is running and sending data.")
            return

        print("Synced. Receiving packets...\n")

        # Process the first packet
        self.voltage_buffer.extend(first_packet["voltage"])
        self.current_buffer.extend(first_packet["current"])

        while True:
            packet = self.read_packet()
            if not packet:
                continue

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
                    plot_raw_adc_samples(
                        voltage_window,
                        current_window,
                        self.current_vref_mv,
                        ADC_CONFIG["max_value"],
                        "Raw ADC Samples (200ms Analysis Window)",
                    )
                    plotted = True

                # Perform comprehensive power analysis on this window
                measurement = self.analyze_power_window(
                    voltage_window,
                    current_window,
                    self.current_vref_mv,
                    datetime.now(),
                )
                self.analysis_count += 1

                # Handle measurement (store in DB + aggregate for MQTT)
                self.handle_measurement(measurement)

                # Print individual measurement if flag is set
                if self.print_measurements:
                    self._print_measurement(measurement)

    def _print_measurement(self, measurement: PowerMeasurement) -> None:
        """Print all metrics from 200ms measurement."""
        elapsed = time.time() - self.start_time
        print(f"\n{'='*80}")
        print(f"[{elapsed:6.1f}s] PowerMeasurement #{self.analysis_count} @ {measurement.timestamp}")
        print(f"{'='*80}")
        print("RMS Values:")
        print(f"  V_rms = {measurement.v_rms:7.3f} V")
        print(f"  I_rms = {measurement.i_rms:7.4f} A")
        print("Power:")
        print(f"  P  = {measurement.P:7.2f} W")
        print(f"  Q  = {measurement.Q:7.2f} VAR")
        print(f"  S  = {measurement.S:7.2f} VA")
        print(f"  PF = {measurement.PF:6.4f}")
        print("Harmonics:")
        print(f"  V_THD  = {measurement.v_thd*100:5.2f} %")
        print(f"  I_THD  = {measurement.i_thd*100:5.2f} %")
        print(f"  V1_amp = {measurement.v1_amp:7.3f} V")
        print(f"  I1_amp = {measurement.i1_amp:7.4f} A")
        print("Phase:")
        print(f"  φ   = {measurement.phase_diff_deg:6.2f} °")
        print(f"  DPF = {measurement.DPF:6.4f}")
        print("Power Quality:")
        print(f"  Frequency     = {measurement.frequency:6.3f} Hz")
        print(f"  Crest_V       = {measurement.crest_factor_v:5.3f}")
        print(f"  Crest_I       = {measurement.crest_factor_i:5.3f}")
        print(f"  V_deviation   = {measurement.voltage_deviation_pct:+6.3f} %")
        print(f"  K-factor      = {measurement.k_factor:6.3f}")
        print("CPC (Currents' Physical Components):")
        print(f"  DF = {measurement.cpc_distortion_factor:6.4f}")
        print(f"  I_active    = {measurement.cpc_active_current:7.4f} A  (λ_a = {measurement.cpc_active_ratio:6.4f})")
        print(f"  I_reactive  = {measurement.cpc_reactive_current:7.4f} A  (λ_r = {measurement.cpc_reactive_ratio:6.4f}, Q1 = {measurement.cpc_reactive_power:7.2f} VAR)")
        print(f"  I_scattered = {measurement.cpc_scattered_current:7.4f} A  (λ_s = {measurement.cpc_scattered_ratio:6.4f}, D_s = {measurement.cpc_scattered_power:7.2f} VA)")
        print(f"  I_generated = {measurement.cpc_generated_current:7.4f} A  (λ_g = {measurement.cpc_generated_ratio:6.4f}, D_g = {measurement.cpc_generated_power:7.2f} VA)")
        
        # Harmonic responsibility analysis
        print("Harmonic Power Flow (IEEE 519 Responsibility):")
        grid_sourced = []
        load_sourced = []
        for h in sorted(measurement.harmonic_power_flow.keys()):
            if h == 1:
                continue  # Skip fundamental
            p_h = measurement.harmonic_power_flow[h]
            if abs(p_h) > 0.01:  # Only show significant harmonics (>10mW)
                if p_h > 0:
                    grid_sourced.append((h, p_h))
                else:
                    load_sourced.append((h, p_h))
        
        if grid_sourced:
            print("  Grid sourced (Grid→Load):")
            for h, p_h in grid_sourced[:10]:  # Top 10
                print(f"    H{h:2d}: +{p_h:6.3f}W")
        
        if load_sourced:
            print("  Load sourced (Load→Grid):")
            for h, p_h in load_sourced[:10]:  # Top 10
                print(f"    H{h:2d}: {p_h:7.3f}W")
        
        if not grid_sourced and not load_sourced:
            print("  No significant harmonic power flow detected")
        
        print("Metadata:")
        print(f"  VREF={measurement.vref_mv}mV")
        print(f"{'='*80}\n")
    
    def _print_aggregate(self, aggregate: AggregateMessage) -> None:
        """Print 1-second aggregate data."""
        elapsed = time.time() - self.start_time
        
        print(
            f"[{elapsed:6.1f}s] 1s AGG: "
            f"P={aggregate.P.avg:6.2f}W({aggregate.P.min:.1f}-{aggregate.P.max:.1f}), "
            f"V={aggregate.v_rms.avg:5.1f}V({aggregate.v_rms.min:.1f}-{aggregate.v_rms.max:.1f}), "
            f"I={aggregate.i_rms.avg:5.2f}A({aggregate.i_rms.min:.2f}-{aggregate.i_rms.max:.2f}), "
            f"PF={aggregate.PF.avg:.3f}, Freq={aggregate.frequency_avg:.2f}Hz, "
            f"Energy: {aggregate.energy_wh:.4f}Wh, "
            f"Harmonics: Grid={aggregate.harmonics_grid_sourced_w:.2f}W, Load={aggregate.harmonics_load_sourced_w:.2f}W"
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
