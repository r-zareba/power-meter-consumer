from datetime import datetime
from typing import List

import numpy as np

from analytics.signal_analysis import (
    calculate_cpc_components,
    calculate_harmonics_with_phase,
    calculate_thd,
)
from models.power_measurement import PowerMeasurement


class PowerAnalyzer:
    """
    Power quality measurement engine for single-phase AC systems.

    Implements:
    - IEC 61000-4-7 (Harmonics measurement)
    - IEC 61000-4-30 Class A (Power quality measurement)
    - Czarnecki's CPC (Currents' Physical Components) theory

    Separated from data acquisition for:
    - Independent testing with synthetic data
    - Reusability across different hardware interfaces
    - Algorithm evolution without affecting protocol handling
    """

    def __init__(
        self,
        sampling_freq: float,
        mains_freq: float,
        adc_max_value: int,
        nominal_voltage: float,
    ):
        """
        Initialize power analyzer.

        Args:
            sampling_freq: ADC sampling frequency (Hz)
            mains_freq: Mains frequency (50 or 60 Hz)
            adc_max_value: Maximum ADC value (e.g., 65535 for 16-bit)
            nominal_voltage: Nominal voltage for deviation calculation (V)
        """
        self.sampling_freq = sampling_freq
        self.mains_freq = mains_freq
        self.adc_to_mv_scale = adc_max_value * 1000.0
        self.nominal_voltage = nominal_voltage

    def analyze_window(
        self,
        voltage_samples: List[int],
        current_samples: List[int],
        vdda_mv: int,
        timestamp: datetime,
    ) -> PowerMeasurement:
        """
        Analyze 200ms measurement window (2048 samples at 10.24 kHz).

        Args:
            voltage_samples: Raw ADC samples for voltage channel
            current_samples: Raw ADC samples for current channel
            vdda_mv: ADC reference voltage in millivolts
            timestamp: Measurement timestamp

        Returns:
            PowerMeasurement object with all calculated metrics
        """
        # Convert ADC samples to voltage (float64 for precision)
        voltage_array = np.array(voltage_samples, dtype=np.float64)
        current_array = np.array(current_samples, dtype=np.float64)

        scale_factor = vdda_mv / self.adc_to_mv_scale
        v_t = voltage_array * scale_factor
        i_t = current_array * scale_factor

        # Remove DC offset (critical for AC power measurement)
        # Sensors add DC bias (typically VCC/2 = 1.65V)
        v_t = v_t - np.mean(v_t)
        i_t = i_t - np.mean(i_t)

        # Basic RMS values (now AC-only)
        v_rms = np.sqrt(np.mean(v_t**2))
        i_rms = np.sqrt(np.mean(i_t**2))

        # Power calculations
        p_t = v_t * i_t
        p = np.mean(p_t)  # Active power
        s = v_rms * i_rms  # Apparent power
        pf = p / s if s > 0 else 0.0  # Power factor

        # Harmonic analysis with phase
        # Window function recommended for non-synchronized sampling (real hardware)
        v_harmonics = calculate_harmonics_with_phase(
            v_t, self.sampling_freq, self.mains_freq, use_window=True
        )
        i_harmonics = calculate_harmonics_with_phase(
            i_t, self.sampling_freq, self.mains_freq, use_window=True
        )

        # Extract amplitudes for THD calculation
        v_harmonics_amp = {h: amp for h, (amp, _) in v_harmonics.items()}
        i_harmonics_amp = {h: amp for h, (amp, _) in i_harmonics.items()}

        v_thd = calculate_thd(v_harmonics_amp)
        i_thd = calculate_thd(i_harmonics_amp)

        # Fundamental component phase information
        v1_amp, v1_phase = v_harmonics[1]
        i1_amp, i1_phase = i_harmonics[1]
        phase_diff = v1_phase - i1_phase
        # Normalize phase difference to [-π, π] for consistent display
        phase_diff = np.angle(np.exp(1j * phase_diff))
        dpf = np.cos(phase_diff)  # Displacement power factor

        # Reactive power calculation (fundamental component only)
        # Q = sqrt(S^2 - P^2) is ONLY valid for sinusoidal conditions
        # With harmonics: Q must be calculated from fundamental phase shift
        v1_rms = v1_amp / np.sqrt(2)
        i1_rms = i1_amp / np.sqrt(2)
        q = v1_rms * i1_rms * np.sin(phase_diff)  # IEEE 1459 compliant

        # Czarnecki's CPC decomposition
        cpc = calculate_cpc_components(v_t, i_t, self.sampling_freq, self.mains_freq)

        # Frequency measurement using zero-crossing detection (IEC 61000-4-30 method)
        # Count zero crossings in voltage signal
        zero_crossings = np.where(np.diff(np.sign(v_t)))[0]
        num_crossings = len(zero_crossings)
        if num_crossings >= 2:
            # Calculate time between first and last crossing
            duration = (zero_crossings[-1] - zero_crossings[0]) / self.sampling_freq
            # Number of complete cycles = (num_crossings - 1) / 2
            # Each cycle has 2 zero crossings (rising and falling)
            num_cycles = (num_crossings - 1) / 2.0
            measured_freq = num_cycles / duration if duration > 0 else self.mains_freq
        else:
            # Fallback to nominal if insufficient crossings (shouldn't happen in normal operation)
            measured_freq = self.mains_freq

        # Power quality indicators
        v_peak = np.max(np.abs(v_t))
        i_peak = np.max(np.abs(i_t))
        crest_factor_v = v_peak / v_rms if v_rms > 0 else 0.0
        crest_factor_i = i_peak / i_rms if i_rms > 0 else 0.0

        # Voltage deviation from nominal
        voltage_deviation_pct = (
            (v_rms - self.nominal_voltage) / self.nominal_voltage * 100.0
            if self.nominal_voltage > 0
            else 0.0
        )

        # Harmonic power flow analysis (IEEE 519 responsibility determination)
        # P_h = V_h × I_h × cos(φ_v - φ_i)
        # Positive: Grid sources harmonic (Grid → Load power flow)
        # Negative: Load sources harmonic (Load → Grid power flow)
        harmonic_power_flow = {}
        for h in range(1, 51):  # Analyze harmonics 1-50
            if h in v_harmonics and h in i_harmonics:
                v_amp, v_phase = v_harmonics[h]
                i_amp, i_phase = i_harmonics[h]
                h_phase_diff = (
                    v_phase - i_phase
                )  # Use different variable name to avoid overwriting
                # Active power for this harmonic
                p_h = v_amp * i_amp * np.cos(h_phase_diff)
                harmonic_power_flow[h] = p_h

        return PowerMeasurement(
            timestamp=timestamp,
            v_rms=v_rms,
            i_rms=i_rms,
            P=p,
            Q=q,
            S=s,
            PF=pf,
            v_thd=v_thd,
            i_thd=i_thd,
            v1_amp=v1_amp,
            i1_amp=i1_amp,
            phase_diff_deg=np.degrees(phase_diff),
            DPF=dpf,
            crest_factor_v=crest_factor_v,
            crest_factor_i=crest_factor_i,
            voltage_deviation_pct=voltage_deviation_pct,
            cpc_distortion_factor=cpc["DF"],
            cpc_active_current=cpc["I_a"],
            cpc_reactive_current=cpc["I_r"],
            cpc_scattered_current=cpc["I_s"],
            cpc_generated_current=cpc["I_g"],
            cpc_active_ratio=cpc["lambda_a"],
            cpc_reactive_ratio=cpc["lambda_r"],
            cpc_scattered_ratio=cpc["lambda_s"],
            cpc_generated_ratio=cpc["lambda_g"],
            cpc_reactive_power=cpc["Q1"],
            cpc_scattered_power=cpc["D_s"],
            cpc_generated_power=cpc["D_g"],
            frequency=measured_freq,
            v_harmonics=v_harmonics,
            i_harmonics=i_harmonics,
            harmonic_power_flow=harmonic_power_flow,
            vref_mv=vdda_mv,
        )
