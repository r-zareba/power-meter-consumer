"""
Signal generation functions for power analysis simulations.
Used by STM32 simulator and UI playground for generating test waveforms.
"""

import numpy as np


def generate_sine(
    amplitude: float,
    frequency: float,
    phase: float,
    sampling_freq: float,
    num_samples: int,
    harmonics: dict[int, tuple[float, float]] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate a sinusoidal waveform with optional harmonics.

    Args:
        amplitude: Peak amplitude of fundamental frequency
        frequency: Fundamental frequency (Hz)
        phase: Phase offset (radians)
        sampling_freq: Sampling frequency (Hz)
        num_samples: Number of samples to generate
        harmonics: Dictionary of harmonics {harmonic_number: (amplitude_percentage, phase)}
                   e.g., {3: (0.2, 0.5), 5: (0.1, -0.3)} adds:
                   - 20% 3rd harmonic with 0.5 rad phase
                   - 10% 5th harmonic with -0.3 rad phase

    Returns:
        Tuple of (time_array, signal_array)
    """
    t = np.arange(num_samples) / sampling_freq
    signal = amplitude * np.sin(2 * np.pi * frequency * t + phase)

    # Add harmonics if specified
    if harmonics:
        for harmonic_num, (harmonic_amplitude, harmonic_phase) in harmonics.items():
            signal += (
                amplitude
                * harmonic_amplitude
                * np.sin(2 * np.pi * frequency * harmonic_num * t + harmonic_phase)
            )

    return t, signal


def generate_thyristor_current(
    voltage_signal: np.ndarray,
    amplitude: float,
    firing_angle_deg: float,
    sampling_freq: float,
    frequency: float,
) -> np.ndarray:
    """
    Generate thyristor (SCR) current waveform.
    Thyristor conducts only in positive half-cycles after firing angle.

    Args:
        voltage_signal: Reference voltage signal to determine zero crossings
        amplitude: Peak current amplitude when conducting
        firing_angle_deg: Firing angle in degrees (0-180)
        sampling_freq: Sampling frequency (Hz)
        frequency: Fundamental frequency (Hz)

    Returns:
        Current signal array
    """
    num_samples = len(voltage_signal)
    t = np.arange(num_samples) / sampling_freq
    current = np.zeros(num_samples)
    
    firing_angle_rad = np.radians(firing_angle_deg)
    period = 1.0 / frequency
    samples_per_period = int(sampling_freq * period)
    
    # Find positive zero crossings of voltage
    for cycle in range(int(num_samples / samples_per_period) + 1):
        start_idx = cycle * samples_per_period
        if start_idx >= num_samples:
            break
            
        # Calculate firing point in this cycle
        firing_idx = start_idx + int(firing_angle_rad / (2 * np.pi) * samples_per_period)
        
        # Find next zero crossing (end of positive half-cycle)
        end_idx = min(start_idx + samples_per_period // 2, num_samples)
        
        # Generate current from firing angle to zero crossing
        if firing_idx < end_idx:
            phase_at_firing = firing_angle_rad
            for i in range(firing_idx, end_idx):
                phase = 2 * np.pi * frequency * t[i] - phase_at_firing
                if phase >= 0:
                    current[i] = amplitude * np.sin(phase + phase_at_firing)
    
    return current


def generate_triac_current(
    voltage_signal: np.ndarray,
    amplitude: float,
    firing_angle_deg: float,
    sampling_freq: float,
    frequency: float,
) -> np.ndarray:
    """
    Generate triac current waveform.
    Triac conducts in both directions after firing angle (like back-to-back thyristors).

    Args:
        voltage_signal: Reference voltage signal to determine zero crossings
        amplitude: Peak current amplitude when conducting
        firing_angle_deg: Firing angle in degrees (0-180)
        sampling_freq: Sampling frequency (Hz)
        frequency: Fundamental frequency (Hz)

    Returns:
        Current signal array
    """
    num_samples = len(voltage_signal)
    t = np.arange(num_samples) / sampling_freq
    current = np.zeros(num_samples)
    
    firing_angle_rad = np.radians(firing_angle_deg)
    period = 1.0 / frequency
    samples_per_period = int(sampling_freq * period)
    samples_per_half = samples_per_period // 2
    
    # Process each half-cycle
    for cycle in range(int(num_samples / samples_per_half) + 1):
        start_idx = cycle * samples_per_half
        if start_idx >= num_samples:
            break
            
        # Determine if positive or negative half-cycle
        is_positive = (cycle % 2) == 0
        
        # Calculate firing point in this half-cycle
        firing_idx = start_idx + int(firing_angle_rad / np.pi * samples_per_half)
        end_idx = min(start_idx + samples_per_half, num_samples)
        
        # Generate current from firing angle to end of half-cycle
        if firing_idx < end_idx:
            for i in range(firing_idx, end_idx):
                phase = 2 * np.pi * frequency * t[i]
                if is_positive:
                    current[i] = amplitude * np.sin(phase)
                else:
                    current[i] = amplitude * np.sin(phase)
    
    return current
