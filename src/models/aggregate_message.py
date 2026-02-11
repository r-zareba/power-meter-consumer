"""MQTT aggregate message model for 1-second data."""

import json
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, Dict


@dataclass
class AggregateMessage:
    """
    1-second aggregate message for MQTT publishing.
    Contains statistical aggregates from 5×200ms measurements.

    Flattened design for optimal time-series database storage.
    All metrics follow pattern: metric_stat (e.g., v_rms_avg, P_min, etc.)
    """

    # Timestamp (start of 1-second window)
    timestamp: datetime

    # Device identification
    device_id: str

    # Voltage RMS aggregates (V)
    v_rms_avg: float
    v_rms_min: float
    v_rms_max: float
    v_rms_std: float

    # Current RMS aggregates (A)
    i_rms_avg: float
    i_rms_min: float
    i_rms_max: float
    i_rms_std: float

    # Active power aggregates (W)
    P_avg: float
    P_min: float
    P_max: float
    P_std: float

    # Reactive power aggregates (VAR)
    Q_avg: float
    Q_min: float
    Q_max: float
    Q_std: float

    # Apparent power aggregates (VA)
    S_avg: float
    S_min: float
    S_max: float
    S_std: float

    # Power factor aggregates (dimensionless, -1 to 1)
    PF_avg: float
    PF_min: float
    PF_max: float
    PF_std: float

    # Voltage THD aggregates (percentage as decimal)
    v_thd_avg: float
    v_thd_min: float
    v_thd_max: float
    v_thd_std: float

    # Current THD aggregates (percentage as decimal)
    i_thd_avg: float
    i_thd_min: float
    i_thd_max: float
    i_thd_std: float

    # Fundamental phase difference (degrees)
    phase_diff_deg_avg: float

    # Displacement power factor
    DPF_avg: float

    # CPC components (Conservative Power Components - Czarnecki's theory)
    # Complete orthogonal decomposition: I²_rms = I²_a + I²_r + I²_s + I²_g
    cpc_active_current_avg: float  # I_a - Active current (real power transfer)
    cpc_reactive_current_avg: float  # I_r - Reactive current (fundamental reactive)
    cpc_scattered_current_avg: (
        float  # I_s - Scattered current (current distortion/harmonics)
    )
    cpc_generated_current_avg: (
        float  # I_g - Generated current (voltage distortion effect)
    )

    # Frequency (Hz) - average over 1 second
    frequency_avg: float

    # Energy consumed in this 1-second interval (for time-series aggregation)
    energy_wh: float  # Active energy consumed in 1 second (Wh)
    energy_varh: float  # Reactive energy consumed in 1 second (VARh)
    energy_vah: float  # Apparent energy consumed in 1 second (VAh)

    # Harmonic pollution responsibility (IEEE 519)
    harmonics_grid_sourced_w: float  # Total harmonic power from grid (W)
    harmonics_load_sourced_w: float  # Total harmonic power from load (W)

    def _get_numeric_fields(self) -> Dict[str, float]:
        """
        Extract all numeric fields using introspection.

        Helper method to avoid code duplication between serialization methods.

        Returns:
            Dictionary mapping field names to their numeric values
        """
        numeric_fields = {}

        for field in fields(self):
            field_name = field.name
            field_value = getattr(self, field_name)

            # Skip timestamp and device_id (metadata, not metrics)
            if field_name in ("timestamp", "device_id"):
                continue

            # Add all numeric fields
            if isinstance(field_value, (int, float)):
                numeric_fields[field_name] = field_value

        return numeric_fields

    def to_mqtt_message(self) -> str:
        """
        Convert to JSON string for MQTT payload using introspection.

        Automatically serializes all numeric fields to flat JSON structure.
        This ensures consistency with the dataclass definition.

        Returns:
            JSON string formatted for MQTT publishing
        """
        payload = {
            "timestamp": self.timestamp.isoformat(),
            "device_id": self.device_id,
        }

        # Add all numeric fields automatically
        payload.update(self._get_numeric_fields())

        return json.dumps(payload)

    def to_influx_point(self) -> Dict[str, Any]:
        """
        Convert AggregateMessage to InfluxDB point format using introspection.

        Automatically converts all fields to InfluxDB format:
        - timestamp -> time (nanoseconds)
        - device_id -> tag
        - All numeric fields -> fields

        This ensures consistency: any field added to AggregateMessage
        automatically gets stored in InfluxDB.

        Returns:
            InfluxDB point dictionary
        """
        # Convert timestamp to nanoseconds (InfluxDB precision)
        timestamp_ns = int(self.timestamp.timestamp() * 1e9)

        # Build point structure
        point = {
            "measurement": "power_aggregate",
            "tags": {
                "device_id": self.device_id,
            },
            "time": timestamp_ns,
            "fields": self._get_numeric_fields(),  # Use helper method
        }

        return point

    def to_dict(self) -> dict:
        """Convert to dictionary (useful for debugging)."""
        return json.loads(self.to_mqtt_message())
