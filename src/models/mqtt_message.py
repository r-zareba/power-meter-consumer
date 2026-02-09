"""MQTT aggregate message model for 1-second data."""

from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class MetricStats:
    """Statistical aggregates for a single metric over 1 second (5 measurements)."""
    avg: float
    min: float
    max: float
    std: float


@dataclass
class AggregateMessage:
    """
    1-second aggregate message for MQTT publishing.
    Contains statistical aggregates from 5×200ms measurements.
    """
    
    # Timestamp (start of 1-second window)
    timestamp: datetime
    
    # Device identification
    device_id: str
    
    # RMS value aggregates
    v_rms: MetricStats
    i_rms: MetricStats
    
    # Power aggregates (critical for energy calculations)
    P: MetricStats  # Active power
    Q: MetricStats  # Reactive power
    S: MetricStats  # Apparent power
    
    # Power factor aggregates
    PF: MetricStats
    
    # THD aggregates
    v_thd: MetricStats
    i_thd: MetricStats
    
    # Fundamental phase (average only)
    phase_diff_deg_avg: float
    DPF_avg: float
    
    # CPC components (average only - less critical for real-time)
    cpc_active_current_avg: float
    cpc_reactive_current_avg: float
    
    # Frequency (average only - very stable)
    frequency_avg: float
    
    # Energy consumed in this 1-second interval (for time-series aggregation)
    energy_wh: float  # Active energy consumed in 1 second (Wh)
    energy_varh: float  # Reactive energy consumed in 1 second (VARh)
    energy_vah: float  # Apparent energy consumed in 1 second (VAh)
    
    # Harmonic pollution responsibility (IEEE 519)
    harmonics_grid_sourced_w: float  # Total harmonic power from grid (W)
    harmonics_load_sourced_w: float  # Total harmonic power from load (W)
    
    def to_json(self) -> str:
        """Convert to JSON string for MQTT payload."""
        payload = {
            "timestamp": self.timestamp.isoformat(),
            "device_id": self.device_id,
            "metrics": {
                "v_rms": {
                    "avg": self.v_rms.avg,
                    "min": self.v_rms.min,
                    "max": self.v_rms.max,
                    "std": self.v_rms.std,
                },
                "i_rms": {
                    "avg": self.i_rms.avg,
                    "min": self.i_rms.min,
                    "max": self.i_rms.max,
                    "std": self.i_rms.std,
                },
                "P": {
                    "avg": self.P.avg,
                    "min": self.P.min,
                    "max": self.P.max,
                    "std": self.P.std,
                },
                "Q": {
                    "avg": self.Q.avg,
                    "min": self.Q.min,
                    "max": self.Q.max,
                },
                "S": {
                    "avg": self.S.avg,
                    "min": self.S.min,
                    "max": self.S.max,
                },
                "PF": {
                    "avg": self.PF.avg,
                    "min": self.PF.min,
                    "max": self.PF.max,
                },
                "v_thd": {
                    "avg": self.v_thd.avg,
                    "max": self.v_thd.max,
                },
                "i_thd": {
                    "avg": self.i_thd.avg,
                    "max": self.i_thd.max,
                },
                "phase_diff_deg": self.phase_diff_deg_avg,
                "DPF": self.DPF_avg,
                "cpc_active_current": self.cpc_active_current_avg,
                "cpc_reactive_current": self.cpc_reactive_current_avg,
                "frequency": self.frequency_avg,
                "energy_wh": self.energy_wh,
                "energy_varh": self.energy_varh,
                "energy_vah": self.energy_vah,
                "harmonics_grid_sourced_w": self.harmonics_grid_sourced_w,
                "harmonics_load_sourced_w": self.harmonics_load_sourced_w,
            }
        }
        
        return json.dumps(payload)
    
    def to_dict(self) -> dict:
        """Convert to dictionary (useful for debugging)."""
        return json.loads(self.to_json())
