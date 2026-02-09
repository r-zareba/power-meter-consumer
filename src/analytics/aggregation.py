"""
Statistical aggregation functions for power measurements.
Combines multiple 200ms measurements into 1-second aggregates for MQTT publishing.
"""

from typing import List

import numpy as np

from models.power_measurement import PowerMeasurement
from models.mqtt_message import AggregateMessage, MetricStats


def calculate_metric_stats(values: List[float]) -> MetricStats:
    """
    Calculate statistical aggregates for a metric.
    Uses pure Python for better performance on small datasets (5 values).
    
    Args:
        values: List of measurements for one metric (typically 5 values for 1-second window)
        
    Returns:
        MetricStats with avg, min, max, std
    """
    n = len(values)
    avg = sum(values) / n
    min_val = min(values)
    max_val = max(values)
    
    # Calculate standard deviation (population, not sample)
    variance = sum((x - avg) ** 2 for x in values) / n
    std = variance ** 0.5
    
    return MetricStats(avg=avg, min=min_val, max=max_val, std=std)


def create_aggregate_message(
    measurements: List[PowerMeasurement],
    device_id: str,
    mains_freq: float
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
    # Extract values for each metric
    v_rms_values = [m.v_rms for m in measurements]
    i_rms_values = [m.i_rms for m in measurements]
    P_values = [m.P for m in measurements]
    Q_values = [m.Q for m in measurements]
    S_values = [m.S for m in measurements]
    PF_values = [m.PF for m in measurements]
    v_thd_values = [m.v_thd for m in measurements]
    i_thd_values = [m.i_thd for m in measurements]
    
    # Single-value averages
    phase_diff_avg = float(np.mean([m.phase_diff_deg for m in measurements]))
    DPF_avg = float(np.mean([m.DPF for m in measurements]))
    cpc_active_current_avg = float(np.mean([m.cpc_active_current for m in measurements]))
    cpc_reactive_current_avg = float(np.mean([m.cpc_reactive_current for m in measurements]))
    
    # Use timestamp of first measurement as window start
    timestamp = measurements[0].timestamp
    
    # Calculate statistical aggregates
    v_rms = calculate_metric_stats(v_rms_values)
    i_rms = calculate_metric_stats(i_rms_values)
    P = calculate_metric_stats(P_values)
    Q = calculate_metric_stats(Q_values)
    S = calculate_metric_stats(S_values)
    
    # Calculate energy consumed in this 1-second interval
    # Energy = Average Power × Time = P_avg × 1 second / 3600 = P_avg / 3600 (Wh)
    energy_wh = P.avg / 3600.0
    energy_varh = Q.avg / 3600.0
    energy_vah = S.avg / 3600.0
    
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
        v_rms=v_rms,
        i_rms=i_rms,
        P=P,
        Q=Q,
        S=S,
        PF=calculate_metric_stats(PF_values),
        v_thd=calculate_metric_stats(v_thd_values),
        i_thd=calculate_metric_stats(i_thd_values),
        phase_diff_deg_avg=phase_diff_avg,
        DPF_avg=DPF_avg,
        cpc_active_current_avg=cpc_active_current_avg,
        cpc_reactive_current_avg=cpc_reactive_current_avg,
        frequency_avg=mains_freq,
        energy_wh=energy_wh,
        energy_varh=energy_varh,
        energy_vah=energy_vah,
        harmonics_grid_sourced_w=harmonics_grid_sourced_w,
        harmonics_load_sourced_w=harmonics_load_sourced_w,
    )
