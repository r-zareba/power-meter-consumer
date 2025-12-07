#!/usr/bin/env python3
"""
ADC Data Receiver for STM32 Power Meter
Receives 10kHz ADC samples via UART and provides real-time analysis
"""

import argparse
import csv
import struct
import time
import serial


class ADCReceiver:
    """Base class for receiving and parsing ADC data from STM32"""

    # Protocol constants (must match STM32)
    START_MARKER = 0xAA55
    END_MARKER = 0x55AA
    EXPECTED_SAMPLES = 1000

    def __init__(self, port="/dev/ttyACM0", baudrate=921600):
        """Initialize serial connection"""
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.packet_count = 0
        self.error_count = 0
        self.last_sequence = None

    def connect(self):
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
            print(f"Connected to {self.port} at {self.baudrate} baud")
            
            # Flush buffers
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
            print("Disconnected")

    def find_sync(self):
        """Search for start marker in byte stream"""
        sync_bytes = struct.pack("<H", self.START_MARKER)

        # Read bytes until we find the start marker
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
                    crc = crc >> 1
        return crc

    def read_packet(self):
        """Read and parse one complete packet"""
        # Find start marker
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
        trailer = self.serial.read(4)  # checksum(2) + end_marker(2)
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
        checksum_data = header + data_bytes
        calculated_crc = self.calculate_crc16(checksum_data)
        if calculated_crc != checksum:
            print(
                f"Warning: checksum mismatch (expected 0x{checksum:04X}, got 0x{calculated_crc:04X})"
            )
            self.error_count += 1
            return None

        # Check sequence number for gaps
        if self.last_sequence is not None:
            expected_seq = (self.last_sequence + 1) & 0xFFFF
            if sequence != expected_seq:
                dropped = (sequence - expected_seq) & 0xFFFF
                print(
                    f"Warning: dropped {dropped} packet(s) (seq {self.last_sequence} -> {sequence})"
                )

        self.last_sequence = sequence

        # Parse ADC data
        adc_samples = struct.unpack(f"<{sample_count}H", data_bytes)
        adc_list = list(adc_samples)

        self.packet_count += 1

        return {"sequence": sequence, "samples": adc_list, "timestamp": time.time()}

    def receive_continuous(self, callback=None, duration=None):
        """
        Continuously receive packets

        Args:
            callback: Function to call with each packet
            duration: Optional duration in seconds (None = infinite)
        """
        start_time = time.time()

        try:
            while True:
                # Check duration
                if duration and (time.time() - start_time) > duration:
                    break

                packet = self.read_packet()
                if packet:
                    if callback:
                        callback(packet)

                    # Print stats every 100 packets
                    if self.packet_count % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = self.packet_count / elapsed
                        print(
                            f"Received {self.packet_count} packets "
                            f"({rate:.1f} pkt/s, {self.error_count} errors)"
                        )

        except KeyboardInterrupt:
            print("\nStopped by user")

        finally:
            elapsed = time.time() - start_time
            print("\nSummary:")
            print(f"  Total packets: {self.packet_count}")
            print(f"  Errors: {self.error_count}")
            print(f"  Duration: {elapsed:.1f}s")
            print(f"  Rate: {self.packet_count / elapsed:.1f} packets/s")


class ADCLogger(ADCReceiver):
    """Extends ADCReceiver with data logging"""

    def log_to_csv(self, filename, duration=60):
        """Log ADC data to CSV file"""
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp", "sequence", "sample_index", "adc_value"])

            def save_packet(packet):
                timestamp = packet["timestamp"]
                sequence = packet["sequence"]
                for i, value in enumerate(packet["samples"]):
                    writer.writerow([timestamp, sequence, i, value])

            self.receive_continuous(callback=save_packet, duration=duration)

    def log_to_binary(self, filename, duration=60):
        """Log raw ADC data to binary file (more efficient)"""
        with open(filename, "wb") as binfile:

            def save_packet(packet):
                # Write header
                binfile.write(struct.pack("<d", packet["timestamp"]))  # double
                binfile.write(struct.pack("<H", packet["sequence"]))  # uint16
                # Write samples
                for sample in packet["samples"]:
                    binfile.write(struct.pack("<H", sample))

            self.receive_continuous(callback=save_packet, duration=duration)


def analyze_signal(adc_data, sample_rate=10000):
    """Perform basic signal analysis on ADC data"""
    mean_val = sum(adc_data) / len(adc_data)
    min_val = min(adc_data)
    max_val = max(adc_data)
    variance = sum((x - mean_val) ** 2 for x in adc_data) / len(adc_data)
    std_val = variance ** 0.5
    
    return {
        "mean": mean_val,
        "std": std_val,
        "min": min_val,
        "max": max_val,
    }


def list_serial_ports():
    """List all available serial ports"""
    import serial.tools.list_ports

    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found")
        return

    print("Available serial ports:")
    for port in ports:
        print(f"  {port.device}: {port.description}")


def main():
    """Main entry point with command-line interface"""
    parser = argparse.ArgumentParser(
        description="STM32 ADC Data Receiver",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port /dev/ttyACM0 --baud 921600 --duration 10 --stats
  %(prog)s --port /dev/ttyACM0 --save data.bin --duration 60
  %(prog)s --port /dev/ttyACM0 --csv data.csv --duration 30
  %(prog)s --list-ports
        """,
    )

    parser.add_argument(
        "--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)"
    )
    parser.add_argument(
        "--baud", type=int, default=921600, help="Baud rate (default: 921600)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration in seconds (default: infinite)",
    )
    parser.add_argument(
        "--save", metavar="FILE", help="Save data to file (binary format)"
    )
    parser.add_argument("--csv", metavar="FILE", help="Save data to CSV file")
    parser.add_argument(
        "--list-ports", action="store_true", help="List available serial ports"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Print statistics for each packet"
    )
    parser.add_argument(
        "--raw", action="store_true", help="Just read and display raw bytes (no parsing)"
    )

    args = parser.parse_args()

    # List ports and exit
    if args.list_ports:
        list_serial_ports()
        return
    
    # Raw byte reading mode
    if args.raw:
        print("Raw byte reading mode - will display hex data as it arrives")
        try:
            ser = serial.Serial(
                port=args.port,
                baudrate=args.baud,
                timeout=0.1
            )
            print(f"Connected to {args.port}")
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.5)
            
            print("Reading raw data (Ctrl+C to stop)...")
            byte_count = 0
            while byte_count < 1000:
                data = ser.read(100)
                if data:
                    print(f"[{byte_count:04d}] {data.hex(' ')}")
                    byte_count += len(data)
                else:
                    print(".", end="", flush=True)
                    time.sleep(0.1)
            ser.close()
        except KeyboardInterrupt:
            print("\nStopped")
        except Exception as e:
            print(f"Error: {e}")
        return

    # Log to CSV
    if args.csv:
        logger = ADCLogger(port=args.port, baudrate=args.baud)
        if logger.connect():
            try:
                print(f"Logging to CSV file: {args.csv}")
                logger.log_to_csv(args.csv, duration=args.duration)
            finally:
                logger.disconnect()
        return

    # Log to binary file
    if args.save:
        logger = ADCLogger(port=args.port, baudrate=args.baud)
        if logger.connect():
            try:
                print(f"Logging to binary file: {args.save}")
                logger.log_to_binary(args.save, duration=args.duration)
            finally:
                logger.disconnect()
        return

    # Simple receive with optional statistics
    receiver = ADCReceiver(port=args.port, baudrate=args.baud)
    if receiver.connect():
        try:
            callback = None
            if args.stats:

                def print_stats(packet):
                    samples = packet["samples"]
                    mean_val = sum(samples) / len(samples)
                    min_val = min(samples)
                    max_val = max(samples)
                    variance = sum((x - mean_val) ** 2 for x in samples) / len(samples)
                    std_val = variance ** 0.5
                    print(
                        f"Seq {packet['sequence']:5d}: "
                        f"mean={mean_val:7.1f}, "
                        f"min={min_val:4d}, "
                        f"max={max_val:4d}, "
                        f"std={std_val:6.1f}"
                    )

                callback = print_stats

            receiver.receive_continuous(callback=callback, duration=args.duration)
        finally:
            receiver.disconnect()


if __name__ == "__main__":
    main()
