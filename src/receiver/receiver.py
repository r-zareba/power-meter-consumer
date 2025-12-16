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
    EXPECTED_SAMPLES = 1000
    ANALYSIS_WINDOW = 2000  # IEC 61000-4-7 compliant: 200ms at 10kHz (2 buffers)

    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.packet_count = 0
        self.error_count = 0
        self.last_sequence = None
        self.start_time = None

        # Sample accumulation for 2-buffer analysis window
        self.sample_buffer = []
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
            print(f"Warning: unexpected sample count {sample_count}")
            self.error_count += 1
            return None

        # Read ADC data
        data_bytes = self.serial.read(sample_count * 2)
        if len(data_bytes) != sample_count * 2:
            self.error_count += 1
            return None

        # Read checksum and end marker
        trailer = self.serial.read(4)
        if len(trailer) != 4:
            self.error_count += 1
            return None

        checksum, end_marker = struct.unpack("<HH", trailer)

        # Verify end marker
        if end_marker != self.END_MARKER:
            print(f"Warning: invalid end marker 0x{end_marker:04X}")
            self.error_count += 1
            return None

        # Verify checksum
        calculated_crc = self.calculate_crc16(header + data_bytes)
        if calculated_crc != checksum:
            print(
                f"Warning: checksum mismatch (0x{checksum:04X} vs 0x{calculated_crc:04X})"
            )
            self.error_count += 1
            return None

        # Check for dropped packets
        if self.last_sequence is not None:
            expected_seq = (self.last_sequence + 1) & 0xFFFF
            if sequence != expected_seq:
                dropped = (sequence - expected_seq) & 0xFFFF
                print(
                    f"Warning: dropped {dropped} packet(s) (seq {self.last_sequence} -> {sequence})"
                )

        self.last_sequence = sequence
        self.packet_count += 1

        # Parse ADC data
        adc_samples = struct.unpack(f"<{sample_count}H", data_bytes)
        return {
            "sequence": sequence,
            "samples": list(adc_samples),
            "timestamp": time.time(),
        }

    def process_analysis_window(self, samples: list):
        """
        Execute power analysis on 2000-sample window (200ms at 10kHz).
        IEC 61000-4-7 compliant analysis window.

        Args:
            samples: List of 2000 ADC samples
        """
        samples_array = np.array(samples, dtype=np.float64)

        start_time = time.time()
        # Basic statistics
        mean_val = np.mean(samples_array)
        rms_val = np.sqrt(np.mean(samples_array**2))

        end_time = time.time()

        print(f"Analysis done in miliseconds: {(end_time - start_time) * 1000:.2f} ms")


    def receive_continuous(self):
        """Continuously receive and accumulate samples for 2-buffer analysis"""

        self.start_time = time.time()

        print(
            f"Starting continuous reception with {self.ANALYSIS_WINDOW}-sample analysis windows"
        )
        print(f"(2 buffers {self.EXPECTED_SAMPLES} samples = 200ms at 10kHz)\n")

        while True:
            packet = self.read_packet()
            if packet:
                # Accumulate samples into buffer
                self.sample_buffer.extend(packet["samples"])

                # Check if we have enough samples for analysis window
                if len(self.sample_buffer) >= self.ANALYSIS_WINDOW:
                    # Extract exactly ANALYSIS_WINDOW samples
                    analysis_samples = self.sample_buffer[: self.ANALYSIS_WINDOW]

                    # Keep remaining samples for next window
                    self.sample_buffer = self.sample_buffer[self.ANALYSIS_WINDOW :]

                    # Perform analysis
                    self.analysis_count += 1
                    self.process_analysis_window(analysis_samples)

                # Status update every 10 packets
                if self.packet_count % 10 == 0:
                    print(
                        f"Packets: {self.packet_count}, Errors: {self.error_count}, Analyses: {self.analysis_count}"
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
