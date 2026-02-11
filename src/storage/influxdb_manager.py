"""
InfluxDB Manager

Handles connection and data insertion to InfluxDB time-series database.
Optimized for 1-second aggregate measurements from MQTT.
"""

from typing import Any, Dict

from influxdb import InfluxDBClient

from models.aggregate_message import AggregateMessage


class InfluxDBManager:
    """Manages InfluxDB connection and data insertion"""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
    ):
        """
        Initialize InfluxDB connection.

        Args:
            host: InfluxDB host address
            port: InfluxDB port (default 8086)
            username: InfluxDB username (optional for local setup)
            password: InfluxDB password (optional for local setup)
            database: Database name
        """
        self.host = host
        self.port = port
        self.database = database

        # Create InfluxDB client
        self.client = InfluxDBClient(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )

        # Create database if it doesn't exist
        self._create_database()

    def _create_database(self):
        """Create database if it doesn't exist"""
        try:
            databases = self.client.get_list_database()
            db_names = [db["name"] for db in databases]

            if self.database not in db_names:
                self.client.create_database(self.database)
                print(f"Created InfluxDB database: {self.database}")

                # Create retention policies
                self._create_retention_policies()
            else:
                print(f"Using existing InfluxDB database: {self.database}")

        except Exception as e:
            print(f"Error creating database: {e}")
            raise

    def _create_retention_policies(self):
        """
        Create retention policy for automatic data management.

        - autogen: 30-day retention for 1-second aggregates (rolling window)


        """
        try:
            # 30 days retention for 1-second data (default policy)
            self.client.create_retention_policy(
                name="autogen",
                duration="30d",
                replication="1",
                database=self.database,
                default=True,
            )
            print("Created retention policy: autogen (30 days, rolling window)")

        except Exception as e:
            print(f"Note: Retention policy may already exist ({e})")

    def aggregate_to_influx_point(self, aggregate: AggregateMessage) -> Dict[str, Any]:
        """
        Convert AggregateMessage to InfluxDB point format.

        Delegates to AggregateMessage.to_influx_point() which uses introspection
        to automatically include all fields. This ensures consistency - any field
        added to AggregateMessage automatically gets stored in InfluxDB.

        Args:
            aggregate: AggregateMessage object

        Returns:
            InfluxDB point dictionary
        """
        return aggregate.to_influx_point()

    def insert_aggregate(self, aggregate: AggregateMessage) -> bool:
        """
        Insert 1-second aggregate measurement into InfluxDB.

        Args:
            aggregate: AggregateMessage to insert

        Returns:
            True if successful, False otherwise
        """
        try:
            point = self.aggregate_to_influx_point(aggregate)
            success = self.client.write_points([point])

            if not success:
                print("Warning: Failed to write point to InfluxDB")
                return False

            return True

        except Exception as e:
            print(f"Error inserting aggregate into InfluxDB: {e}")
            return False

    def insert_batch(self, aggregates: list[AggregateMessage]) -> bool:
        """
        Insert multiple aggregates in a single batch (more efficient).

        Args:
            aggregates: List of AggregateMessage objects

        Returns:
            True if successful, False otherwise
        """
        try:
            points = [self.aggregate_to_influx_point(agg) for agg in aggregates]
            success = self.client.write_points(points)

            if not success:
                print(f"Warning: Failed to write {len(points)} points to InfluxDB")
                return False

            return True

        except Exception as e:
            print(f"Error inserting batch into InfluxDB: {e}")
            return False

    def close(self):
        """Close InfluxDB connection"""
        try:
            self.client.close()
            print("Closed InfluxDB connection")
        except Exception as e:
            print(f"Error closing InfluxDB connection: {e}")

    def query(self, query: str) -> Any:
        """
        Execute InfluxQL query.

        Args:
            query: InfluxQL query string

        Returns:
            Query result
        """
        try:
            return self.client.query(query)
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
