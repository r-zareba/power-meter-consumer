"""
Statistical aggregation functions for power measurements.
Combines multiple 200ms measurements into 1-second aggregates for MQTT publishing.
"""

from typing import List

import numpy as np

from models.power_measurement import PowerMeasurement
from models.aggregate_message import AggregateMessage


def calculate_stats(values: List[float]) -> tuple[float, float, float, float]:
    """
    Calculate statistical aggregates for a metric.

    Args:
        values: List of measurements for one metric (typically 5 values for 1-second window)

    Returns:
        Tuple of (avg, min, max, std)
    """
    n = len(values)
    avg = sum(values) / n
    min_val = min(values)
    max_val = max(values)

    # Calculate standard deviation (population, not sample)
    variance = sum((x - avg) ** 2 for x in values) / n
    std = variance**0.5

    return (avg, min_val, max_val, std)


def create_aggregate_message(
    measurements: List[PowerMeasurement], device_id: str, mains_freq: float
) -> AggregateMessage:
    """
    Create 1-second aggregate message from multiple 200ms measurements.

    Args:
        measurements: List of PowerMeasurement objects (typically 5 for 1-second window)
        device_id: Device identifier for MQTT message
        mains_freq: Mains frequency (50 or 60 Hz)

    Returns:
        AggregateMessage for MQTT publishing
    """
    # Use timestamp of first measurement as window start
    timestamp = measurements[0].timestamp

    # Calculate statistical aggregates for each metric
    v_rms_avg, v_rms_min, v_rms_max, v_rms_std = calculate_stats(
        [m.v_rms for m in measurements]
    )
    i_rms_avg, i_rms_min, i_rms_max, i_rms_std = calculate_stats(
        [m.i_rms for m in measurements]
    )
    P_avg, P_min, P_max, P_std = calculate_stats([m.P for m in measurements])
    Q_avg, Q_min, Q_max, Q_std = calculate_stats([m.Q for m in measurements])
    S_avg, S_min, S_max, S_std = calculate_stats([m.S for m in measurements])
    PF_avg, PF_min, PF_max, PF_std = calculate_stats([m.PF for m in measurements])
    v_thd_avg, v_thd_min, v_thd_max, v_thd_std = calculate_stats(
        [m.v_thd for m in measurements]
    )
    i_thd_avg, i_thd_min, i_thd_max, i_thd_std = calculate_stats(
        [m.i_thd for m in measurements]
    )

    # Single-value averages
    phase_diff_deg_avg = float(np.mean([m.phase_diff_deg for m in measurements]))
    DPF_avg = float(np.mean([m.DPF for m in measurements]))
    cpc_active_current_avg = float(
        np.mean([m.cpc_active_current for m in measurements])
    )
    cpc_reactive_current_avg = float(
        np.mean([m.cpc_reactive_current for m in measurements])
    )
    cpc_scattered_current_avg = float(
        np.mean([m.cpc_scattered_current for m in measurements])
    )
    cpc_generated_current_avg = float(
        np.mean([m.cpc_generated_current for m in measurements])
    )

    # Calculate energy consumed in this 1-second interval
    # Energy = Average Power × Time = P_avg × 1 second / 3600 = P_avg / 3600 (Wh)
    energy_wh = P_avg / 3600.0
    energy_varh = Q_avg / 3600.0
    energy_vah = S_avg / 3600.0

    # Calculate harmonic pollution responsibility (average across 5 measurements)
    # Exclude fundamental (h=1), only harmonics h >= 2
    grid_total = 0.0
    load_total = 0.0
    for measurement in measurements:
        for h, p_h in measurement.harmonic_power_flow.items():
            if h == 1:  # Skip fundamental
                continue
            if p_h > 0:
                grid_total += p_h  # Grid sources this harmonic
            else:
                load_total += abs(p_h)  # Load sources this harmonic

    # Average over 5 measurements
    harmonics_grid_sourced_w = grid_total / len(measurements)
    harmonics_load_sourced_w = load_total / len(measurements)

    return AggregateMessage(
        timestamp=timestamp,
        device_id=device_id,
        # Voltage RMS
        v_rms_avg=v_rms_avg,
        v_rms_min=v_rms_min,
        v_rms_max=v_rms_max,
        v_rms_std=v_rms_std,
        # Current RMS
        i_rms_avg=i_rms_avg,
        i_rms_min=i_rms_min,
        i_rms_max=i_rms_max,
        i_rms_std=i_rms_std,
        # Active power
        P_avg=P_avg,
        P_min=P_min,
        P_max=P_max,
        P_std=P_std,
        # Reactive power
        Q_avg=Q_avg,
        Q_min=Q_min,
        Q_max=Q_max,
        Q_std=Q_std,
        # Apparent power
        S_avg=S_avg,
        S_min=S_min,
        S_max=S_max,
        S_std=S_std,
        # Power factor
        PF_avg=PF_avg,
        PF_min=PF_min,
        PF_max=PF_max,
        PF_std=PF_std,
        # Voltage THD
        v_thd_avg=v_thd_avg,
        v_thd_min=v_thd_min,
        v_thd_max=v_thd_max,
        v_thd_std=v_thd_std,
        # Current THD
        i_thd_avg=i_thd_avg,
        i_thd_min=i_thd_min,
        i_thd_max=i_thd_max,
        i_thd_std=i_thd_std,
        # Phase and DPF
        phase_diff_deg_avg=phase_diff_deg_avg,
        DPF_avg=DPF_avg,
        # CPC components
        cpc_active_current_avg=cpc_active_current_avg,
        cpc_reactive_current_avg=cpc_reactive_current_avg,
        cpc_scattered_current_avg=cpc_scattered_current_avg,
        cpc_generated_current_avg=cpc_generated_current_avg,
        # Frequency
        frequency_avg=mains_freq,
        # Energy
        energy_wh=energy_wh,
        energy_varh=energy_varh,
        energy_vah=energy_vah,
        # Harmonics
        harmonics_grid_sourced_w=harmonics_grid_sourced_w,
        harmonics_load_sourced_w=harmonics_load_sourced_w,
    )
