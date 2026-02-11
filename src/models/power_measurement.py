from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Tuple


@dataclass
class PowerMeasurement:
    """
    Represents a single 200ms power quality measurement window.
    IEC 61000-4-7 compliant (10 cycles @ 50Hz).

    This model corresponds to one row in the SQLite database.
    """

    # Timestamp
    timestamp: datetime

    # RMS values
    v_rms: float  # Voltage RMS (V)
    i_rms: float  # Current RMS (A)

    # Power components
    P: float  # Active power (W)
    Q: float  # Reactive power (VAR)
    S: float  # Apparent power (VA)
    PF: float  # Power factor (dimensionless, -1 to 1)

    # Harmonic distortion
    v_thd: float  # Voltage THD (percentage as decimal, e.g., 0.05 = 5%)
    i_thd: float  # Current THD (percentage as decimal)

    # Fundamental component analysis
    v1_amp: float  # Fundamental voltage amplitude (V)
    i1_amp: float  # Fundamental current amplitude (A)
    phase_diff_deg: float  # Phase difference between V and I (degrees)
    DPF: float  # Displacement power factor

    # Power quality indicators
    crest_factor_v: float  # Voltage crest factor (V_peak / V_rms)
    crest_factor_i: float  # Current crest factor (I_peak / I_rms)
    voltage_deviation_pct: float  # Voltage deviation from nominal (%)

    # Czarnecki's CPC current components (RMS)
    cpc_active_current: float  # Active current (A)
    cpc_reactive_current: float  # Reactive current (A)
    cpc_scattered_current: float  # Scattered current (A)
    cpc_generated_current: float  # Generated current (A)

    # CPC current ratios (lambda values)
    cpc_active_ratio: float  # Active current ratio
    cpc_reactive_ratio: float  # Reactive current ratio
    cpc_scattered_ratio: float  # Scattered current ratio
    cpc_generated_ratio: float  # Generated current ratio

    # CPC power components
    cpc_distortion_factor: float  # Distortion factor
    cpc_reactive_power: float  # Fundamental reactive power (VAR)
    cpc_scattered_power: float  # Scattered power (VA)
    cpc_generated_power: float  # Generated power (VA)

    # Frequency (Hz)
    frequency: float = 50.0  # Mains frequency

    # Harmonics data (stored as JSON in DB)
    # Format: {harmonic_number: (amplitude, phase)}
    v_harmonics: Dict[int, Tuple[float, float]] = field(default_factory=dict)
    i_harmonics: Dict[int, Tuple[float, float]] = field(default_factory=dict)

    # Harmonic power flow analysis (IEEE 519 responsibility determination)
    # Format: {harmonic_number: active_power_watts}
    # Positive: Grid sources this harmonic (power flows Grid → Load)
    # Negative: Load sources this harmonic (power flows Load → Grid)
    harmonic_power_flow: Dict[int, float] = field(default_factory=dict)

    # Metadata
    vref_mv: int = 3300  # ADC reference voltage (mV)

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "v_rms": self.v_rms,
            "i_rms": self.i_rms,
            "P": self.P,
            "Q": self.Q,
            "S": self.S,
            "PF": self.PF,
            "v_thd": self.v_thd,
            "i_thd": self.i_thd,
            "v1_amp": self.v1_amp,
            "i1_amp": self.i1_amp,
            "phase_diff_deg": self.phase_diff_deg,
            "DPF": self.DPF,
            "crest_factor_v": self.crest_factor_v,
            "crest_factor_i": self.crest_factor_i,
            "voltage_deviation_pct": self.voltage_deviation_pct,
            "cpc_distortion_factor": self.cpc_distortion_factor,
            "cpc_active_current": self.cpc_active_current,
            "cpc_reactive_current": self.cpc_reactive_current,
            "cpc_scattered_current": self.cpc_scattered_current,
            "cpc_generated_current": self.cpc_generated_current,
            "cpc_active_ratio": self.cpc_active_ratio,
            "cpc_reactive_ratio": self.cpc_reactive_ratio,
            "cpc_scattered_ratio": self.cpc_scattered_ratio,
            "cpc_generated_ratio": self.cpc_generated_ratio,
            "cpc_reactive_power": self.cpc_reactive_power,
            "cpc_scattered_power": self.cpc_scattered_power,
            "cpc_generated_power": self.cpc_generated_power,
            "frequency": self.frequency,
            "vref_mv": self.vref_mv,
        }
