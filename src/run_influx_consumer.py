"""
Run InfluxDB Consumer Service

Entry point for MQTT to InfluxDB consumer service.
Subscribes to MQTT power measurement aggregates and inserts into InfluxDB.
"""

import signal

from influxdb_consumer import InfluxDBConsumer


def main():
    """Main entry point"""

    # Create and start consumer with hardcoded values
    # TODO: Move to environment variables or config file
    consumer = InfluxDBConsumer(
        mqtt_broker="localhost",
        mqtt_port=1883,
        mqtt_topic="power_meter/#",
        influx_host="localhost",
        influx_port=8086,
        influx_username="admin",
        influx_password="admin",
        influx_database="power_meter",
        batch_size=10,
    )

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda sig, frame: consumer._shutdown())

    consumer.start()


if __name__ == "__main__":
    main()
