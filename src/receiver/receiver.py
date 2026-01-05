"""ADC Receiver for STM32 Power Meter"""

import struct
import time

import numpy as np
import serial


class ADCReceiver:
    """Receives and parses ADC data from STM32"""

    # Protocol constants (must match STM32)
    START_MARKER = 0xAA55
    END_MARKER = 0x55AA
    EXPECTED_SAMPLES = 1000  # Samples per channel per packet
    ANALYSIS_WINDOW = 2000  # IEC 61000-4-7 compliant: 200ms at 10kHz (2 packets per channel)

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
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            return True
        except serial.SerialException as e:
            print(f"Failed to open serial port: {e}")
            return False

    def disconnect(self):
        """Close serial port"""
        if self.serial and self.serial.is_open:
            self.serial.close()

    def find_sync(self):
        """Search for start marker in byte stream"""
        sync_bytes = struct.pack("<H", self.START_MARKER)
        bytes_checked = 0

        while bytes_checked < 10000:
            byte = self.serial.read(1)
            if not byte:
                return False
            bytes_checked += 1

            if byte == sync_bytes[0:1]:
                next_byte = self.serial.read(1)
                if next_byte == sync_bytes[1:2]:
                    return True
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
        header = self.serial.read(4)  # seq(2) + count(2)
        if len(header) != 4:
            self.error_count += 1
            return None

        sequence, sample_count = struct.unpack("<HH", header)

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

        # Verify checksum
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
            "timestamp": time.time(),
        }

    def process_analysis_window(self, voltage: list, current: list):
        """
        Execute power analysis on 2000-sample window (200ms at 10kHz).
        IEC 61000-4-7 compliant analysis window.

        Args:
            voltage: List of 2000 voltage ADC samples (ADC1)
            current: List of 2000 current ADC samples (ADC2)
            
        Returns:
            dict: Statistics including v_mean, v_rms, i_mean, i_rms
        """
        voltage_array = np.array(voltage, dtype=np.float64)
        current_array = np.array(current, dtype=np.float64)
        
        return {
            "v_mean": np.mean(voltage_array),
            "v_rms": np.sqrt(np.mean(voltage_array**2)),
            "i_mean": np.mean(current_array),
            "i_rms": np.sqrt(np.mean(current_array**2)),
        }


    def receive_continuous(self):
        """Continuously receive packets and print averaged voltage/current every 1 second"""

        self.start_time = time.time()
        last_print_time = time.time()
        
        # Accumulators for 1-second averaging
        v_mean_sum = 0.0
        i_mean_sum = 0.0
        sample_count = 0

        print(f"Receiving data from {self.port} at {self.baudrate} baud...\n")

        while True:
            packet = self.read_packet()
            if packet:
                # Accumulate dual-channel samples
                self.voltage_buffer.extend(packet["voltage"])
                self.current_buffer.extend(packet["current"])

                # Process complete analysis windows
                if len(self.voltage_buffer) >= self.ANALYSIS_WINDOW:
                    voltage_window = self.voltage_buffer[: self.ANALYSIS_WINDOW]
                    current_window = self.current_buffer[: self.ANALYSIS_WINDOW]
                    self.voltage_buffer = self.voltage_buffer[self.ANALYSIS_WINDOW :]
                    self.current_buffer = self.current_buffer[self.ANALYSIS_WINDOW :]

                    # Get statistics from this window
                    stats = self.process_analysis_window(voltage_window, current_window)
                    
                    # Accumulate for 1-second average
                    v_mean_sum += stats["v_mean"]
                    i_mean_sum += stats["i_mean"]
                    sample_count += 1

                # Print average every 1 second
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    if sample_count > 0:
                        v_avg = v_mean_sum / sample_count
                        i_avg = i_mean_sum / sample_count
                        elapsed = current_time - self.start_time
                        print(f"[{elapsed:6.1f}s] V_avg={v_avg:7.1f} ADC, I_avg={i_avg:7.1f} ADC, Packets={self.packet_count:4d}, Errors={self.error_count:2d}")
                        
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
