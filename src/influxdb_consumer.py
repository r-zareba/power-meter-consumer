"""
MQTT to InfluxDB Consumer

Subscribes to MQTT topics, receives 1-second aggregate measurements,
and inserts them into InfluxDB time-series database.

This service runs independently from the main ADC receiver.
"""

import json
import sys
import time
from datetime import datetime

import paho.mqtt.client as mqtt

from models.aggregate_message import AggregateMessage
from storage.influxdb_manager import InfluxDBManager


class InfluxDBConsumer:
    """MQTT consumer that writes aggregate measurements to InfluxDB"""

    def __init__(
        self,
        mqtt_broker: str,
        mqtt_port: int,
        mqtt_topic: str,
        influx_host: str,
        influx_port: int,
        influx_username: str,
        influx_password: str,
        influx_database: str,
        batch_size: int,
    ):
        """
        Initialize MQTT to InfluxDB consumer.

        Args:
            mqtt_broker: MQTT broker host
            mqtt_port: MQTT broker port
            mqtt_topic: MQTT topic to subscribe to (supports wildcards)
            influx_host: InfluxDB host
            influx_port: InfluxDB port
            influx_username: InfluxDB username
            influx_password: InfluxDB password
            influx_database: InfluxDB database name
            batch_size: Number of messages to batch before writing (0 = no batching)
        """
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic
        self.batch_size = batch_size

        # Statistics
        self.messages_received = 0
        self.messages_written = 0
        self.errors = 0
        self.start_time = None

        # Batch buffer
        self.batch_buffer = []

        # Initialize InfluxDB manager
        print(f"Connecting to InfluxDB at {influx_host}:{influx_port}")
        self.influx_manager = InfluxDBManager(
            host=influx_host,
            port=influx_port,
            username=influx_username,
            password=influx_password,
            database=influx_database,
        )

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client(client_id="influxdb_consumer")
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            print(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            print(f"Subscribing to topic: {self.mqtt_topic}")
            client.subscribe(self.mqtt_topic)
        else:
            print(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        if rc != 0:
            print(f"Unexpected disconnect from MQTT broker, rc={rc}")
            print("Attempting to reconnect...")

    def _on_message(self, client, userdata, msg):
        """
        Callback when MQTT message is received.
        Parse JSON and insert into InfluxDB.
        """
        try:
            # Parse JSON payload
            payload = json.loads(msg.payload.decode())

            # Convert to AggregateMessage
            aggregate = self._parse_aggregate_message(payload)

            self.messages_received += 1

            # Add to batch or write immediately
            if self.batch_size > 0:
                self.batch_buffer.append(aggregate)

                # Write batch when full
                if len(self.batch_buffer) >= self.batch_size:
                    self._write_batch()
            else:
                # Write immediately (no batching)
                if self.influx_manager.insert_aggregate(aggregate):
                    self.messages_written += 1
                    if self.messages_written % 10 == 0:
                        self._print_stats()
                else:
                    self.errors += 1

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            self.errors += 1
        except Exception as e:
            print(f"Error processing message: {e}")
            self.errors += 1

    def _parse_aggregate_message(self, payload: dict) -> AggregateMessage:
        """
        Parse JSON payload into AggregateMessage object.

        Handles flat JSON structure that matches the dataclass fields directly.
        """
        return AggregateMessage(
            timestamp=datetime.fromisoformat(
                payload["timestamp"].replace("Z", "+00:00")
            ),
            device_id=payload["device_id"],
            # Voltage RMS
            v_rms_avg=payload["v_rms_avg"],
            v_rms_min=payload["v_rms_min"],
            v_rms_max=payload["v_rms_max"],
            v_rms_std=payload["v_rms_std"],
            # Current RMS
            i_rms_avg=payload["i_rms_avg"],
            i_rms_min=payload["i_rms_min"],
            i_rms_max=payload["i_rms_max"],
            i_rms_std=payload["i_rms_std"],
            # Active power
            P_avg=payload["P_avg"],
            P_min=payload["P_min"],
            P_max=payload["P_max"],
            P_std=payload["P_std"],
            # Reactive power
            Q_avg=payload["Q_avg"],
            Q_min=payload["Q_min"],
            Q_max=payload["Q_max"],
            Q_std=payload["Q_std"],
            # Apparent power
            S_avg=payload["S_avg"],
            S_min=payload["S_min"],
            S_max=payload["S_max"],
            S_std=payload["S_std"],
            # Power factor
            PF_avg=payload["PF_avg"],
            PF_min=payload["PF_min"],
            PF_max=payload["PF_max"],
            PF_std=payload["PF_std"],
            # Voltage THD
            v_thd_avg=payload["v_thd_avg"],
            v_thd_min=payload["v_thd_min"],
            v_thd_max=payload["v_thd_max"],
            v_thd_std=payload["v_thd_std"],
            # Current THD
            i_thd_avg=payload["i_thd_avg"],
            i_thd_min=payload["i_thd_min"],
            i_thd_max=payload["i_thd_max"],
            i_thd_std=payload["i_thd_std"],
            # Phase and DPF
            phase_diff_deg_avg=payload["phase_diff_deg_avg"],
            DPF_avg=payload["DPF_avg"],
            # CPC components
            cpc_active_current_avg=payload["cpc_active_current_avg"],
            cpc_reactive_current_avg=payload["cpc_reactive_current_avg"],
            cpc_scattered_current_avg=payload["cpc_scattered_current_avg"],
            cpc_generated_current_avg=payload["cpc_generated_current_avg"],
            # Frequency
            frequency_avg=payload["frequency_avg"],
            # Energy
            energy_wh=payload["energy_wh"],
            energy_varh=payload["energy_varh"],
            energy_vah=payload["energy_vah"],
            # Harmonics
            harmonics_grid_sourced_w=payload["harmonics_grid_sourced_w"],
            harmonics_load_sourced_w=payload["harmonics_load_sourced_w"],
        )

    def _write_batch(self):
        """Write buffered batch to InfluxDB"""
        if not self.batch_buffer:
            return

        if self.influx_manager.insert_batch(self.batch_buffer):
            self.messages_written += len(self.batch_buffer)
            print(f"Wrote batch of {len(self.batch_buffer)} messages to InfluxDB")
            self._print_stats()
        else:
            self.errors += 1
            print(f"Failed to write batch of {len(self.batch_buffer)} messages")

        # Clear buffer
        self.batch_buffer.clear()

    def _print_stats(self):
        """Print statistics"""
        if self.start_time is None:
            return

        elapsed = time.time() - self.start_time
        rate = self.messages_written / elapsed if elapsed > 0 else 0

        print(
            f"Stats: Received={self.messages_received}, "
            f"Written={self.messages_written}, "
            f"Errors={self.errors}, "
            f"Rate={rate:.2f} msg/s"
        )

    def start(self):
        """Start the consumer service"""
        print("\n" + "=" * 60)
        print("InfluxDB Consumer Service")
        print("=" * 60)
        print(f"MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")
        print(f"MQTT Topic: {self.mqtt_topic}")
        print(
            f"Batch size: {self.batch_size if self.batch_size > 0 else 'disabled (write immediately)'}"
        )
        print("=" * 60 + "\n")

        self.start_time = time.time()

        # Connect to MQTT broker
        print("Connecting to MQTT broker...")
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            sys.exit(1)

        # Start MQTT loop
        print("Starting MQTT message loop...")
        print("Press Ctrl+C to stop\n")

        try:
            self.mqtt_client.loop_forever()
        except KeyboardInterrupt:
            self._shutdown()

    def _shutdown(self):
        """Graceful shutdown"""
        print("\n\nShutting down...")

        # Write any remaining batched messages
        if self.batch_buffer:
            print(f"Writing final batch of {len(self.batch_buffer)} messages...")
            self._write_batch()

        # Disconnect MQTT
        self.mqtt_client.disconnect()

        # Close InfluxDB
        self.influx_manager.close()

        # Print final statistics
        print("\n" + "=" * 60)
        print("Final Statistics:")
        print(f"  Messages received: {self.messages_received}")
        print(f"  Messages written: {self.messages_written}")
        print(f"  Errors: {self.errors}")
        if self.start_time:
            elapsed = time.time() - self.start_time
            rate = self.messages_written / elapsed if elapsed > 0 else 0
            print(f"  Runtime: {elapsed:.1f}s")
            print(f"  Average rate: {rate:.2f} msg/s")
        print("=" * 60)

        sys.exit(0)
