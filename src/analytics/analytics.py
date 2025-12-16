"""
Power analysis calculation functions for single-phase and three-phase systems.
IEC 61000-4-7 & IEC 61000-4-30 compliant.
"""

import numpy as np

# System parameters matching ADCReceiver and IEC 61000-4-7
SAMPLING_FREQ = 10000  # Hz
NUM_SAMPLES = 2000  # 200ms window (10 cycles at 50Hz) for IEC 61000-4-7 compliance
MAINS_FREQ = 50  # Hz


# =============================================================================
# SINGLE-PHASE FUNCTIONS
# =============================================================================


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


def analyze_harmonics(
    signal: np.ndarray,
    sampling_freq: float,
    fundamental_freq: float,
    max_harmonic: int = 50,
) -> dict[int, float]:
    """
    Analyze harmonics in a signal using FFT.
    IEC 61000-4-7 compliant: supports up to 50th harmonic.

    Args:
        signal: Time-domain signal samples
        sampling_freq: Sampling frequency (Hz)
        fundamental_freq: Fundamental frequency (Hz)
        max_harmonic: Maximum harmonic number to extract (IEC 61000-4-7: up to 50)

    Returns:
        Dictionary {harmonic_number: amplitude} for harmonics 1 to max_harmonic
    """
    # Perform FFT
    fft_result = np.fft.rfft(signal)
    fft_magnitude = np.abs(fft_result) * 2 / len(signal)

    # Frequency bins
    freqs = np.fft.rfftfreq(len(signal), 1 / sampling_freq)

    # Extract harmonic amplitudes
    harmonics = {}
    for harmonic_num in range(1, max_harmonic + 1):
        target_freq = fundamental_freq * harmonic_num
        # Find closest frequency bin
        idx = np.argmin(np.abs(freqs - target_freq))
        harmonics[harmonic_num] = fft_magnitude[idx]

    return harmonics


def analyze_harmonics_with_phase(
    signal: np.ndarray,
    sampling_freq: float,
    fundamental_freq: float,
    max_harmonic: int = 50,
) -> dict[int, tuple[float, float]]:
    """
    Analyze harmonics with phase information using FFT.

    Args:
        signal: Time-domain signal samples
        sampling_freq: Sampling frequency (Hz)
        fundamental_freq: Fundamental frequency (Hz)
        max_harmonic: Maximum harmonic number to extract

    Returns:
        Dictionary {harmonic_number: (amplitude, phase_radians)}
    """
    # Perform FFT
    fft_result = np.fft.rfft(signal)
    fft_magnitude = np.abs(fft_result) * 2 / len(signal)
    fft_phase = np.angle(fft_result)

    # Frequency bins
    freqs = np.fft.rfftfreq(len(signal), 1 / sampling_freq)

    # Extract harmonic amplitudes and phases
    harmonics = {}
    for harmonic_num in range(1, max_harmonic + 1):
        target_freq = fundamental_freq * harmonic_num
        idx = np.argmin(np.abs(freqs - target_freq))
        harmonics[harmonic_num] = (fft_magnitude[idx], fft_phase[idx])

    return harmonics


def calculate_thd(harmonics: dict[int, float]) -> float:
    """
    Calculate Total Harmonic Distortion (THD).

    Args:
        harmonics: Dictionary {harmonic_number: amplitude} from analyze_harmonics

    Returns:
        THD as a ratio (multiply by 100 for percentage)
    """
    if 1 not in harmonics or harmonics[1] == 0:
        return 0.0

    fundamental = harmonics[1]

    # Sum of squares of all harmonics except fundamental
    harmonic_sum_squared = sum(
        amp**2 for harm_num, amp in harmonics.items() if harm_num > 1
    )

    thd = np.sqrt(harmonic_sum_squared) / fundamental
    return thd


def calculate_cpc_components(
    v_t: np.ndarray,
    i_t: np.ndarray,
    sampling_freq: float,
    fundamental_freq: float,
) -> dict:
    """
    Calculate Czarnecki's CPC (Currents' Physical Components) decomposition.

    Args:
        v_t: Voltage time-domain samples
        i_t: Current time-domain samples
        sampling_freq: Sampling frequency (Hz)
        fundamental_freq: Fundamental frequency (Hz)

    Returns:
        Dictionary with CPC components and metrics
    """
    # Basic metrics
    v_rms = np.sqrt(np.mean(v_t**2))
    i_rms = np.sqrt(np.mean(i_t**2))
    p = np.mean(v_t * i_t)

    # Get harmonics with phase
    v_harmonics = analyze_harmonics_with_phase(v_t, sampling_freq, fundamental_freq)
    i_harmonics = analyze_harmonics_with_phase(i_t, sampling_freq, fundamental_freq)

    # Extract fundamental components
    v1_amp, v1_phase = v_harmonics[1]
    i1_amp, i1_phase = i_harmonics[1]

    # Fundamental RMS values
    v1_rms = v1_amp / np.sqrt(2)
    i1_rms = i1_amp / np.sqrt(2)

    # 1. Active Current Component: i_a = (P / V_rms²) × v(t)
    i_a_t = (p / (v_rms**2)) * v_t
    i_a_rms = np.sqrt(np.mean(i_a_t**2))

    # 2. Reactive Current (fundamental only, 90° shifted)
    # Q1 = V1 × I1 × sin(phase difference)
    phase_diff = v1_phase - i1_phase
    q1 = v1_rms * i1_rms * np.sin(phase_diff)

    # Reconstruct fundamental voltage for reactive current
    t = np.arange(len(v_t)) / sampling_freq
    v1_t = v1_amp * np.sin(2 * np.pi * fundamental_freq * t + v1_phase)

    # Reactive current proportional to v1 shifted by 90°
    i_r_t = (q1 / (v1_rms**2)) * v1_t
    i_r_rms = np.sqrt(np.mean(i_r_t**2)) if abs(q1) > 1e-6 else 0.0

    # 3. Scattered Current (due to voltage harmonics)
    # Reconstruct voltage harmonics (excluding fundamental)
    v_h_t = np.zeros_like(v_t)
    for h in range(2, 51):
        if h in v_harmonics:
            v_h_amp, v_h_phase = v_harmonics[h]
            v_h_t += v_h_amp * np.sin(2 * np.pi * fundamental_freq * h * t + v_h_phase)

    # Scattered current proportional to voltage distortion
    if v_rms > 0 and v1_rms > 0:
        i_s_t = (i1_rms / v1_rms) * v_h_t
    else:
        i_s_t = np.zeros_like(v_t)
    i_s_rms = np.sqrt(np.mean(i_s_t**2))

    # 4. Generated Current (residual = current harmonics beyond what voltage requires)
    i_g_t = i_t - i_a_t - i_r_t - i_s_t
    i_g_rms = np.sqrt(np.mean(i_g_t**2))

    # Power components
    s = v_rms * i_rms
    d_s = v_rms * i_s_rms  # Scattered power
    d_g = v_rms * i_g_rms  # Generated power

    # Current ratios (lambdas)
    lambda_a = i_a_rms / i_rms if i_rms > 0 else 0
    lambda_r = i_r_rms / i_rms if i_rms > 0 else 0
    lambda_s = i_s_rms / i_rms if i_rms > 0 else 0
    lambda_g = i_g_rms / i_rms if i_rms > 0 else 0

    # Displacement Power Factor (fundamental only)
    dpf = np.cos(phase_diff)

    # Distortion Factor
    df = i1_rms / i_rms if i_rms > 0 else 0

    return {
        # Current RMS components
        "I_a": i_a_rms,
        "I_r": i_r_rms,
        "I_s": i_s_rms,
        "I_g": i_g_rms,
        "I_rms": i_rms,
        # Power components
        "P": p,
        "Q1": q1,
        "D_s": d_s,
        "D_g": d_g,
        "S": s,
        # Current ratios
        "lambda_a": lambda_a,
        "lambda_r": lambda_r,
        "lambda_s": lambda_s,
        "lambda_g": lambda_g,
        # Power factors
        "PF": p / s if s > 0 else 0,
        "DPF": dpf,
        "DF": df,
        # Time-domain components (for plotting)
        "i_a_t": i_a_t,
        "i_r_t": i_r_t,
        "i_s_t": i_s_t,
        "i_g_t": i_g_t,
    }


# =============================================================================
# THREE-PHASE FUNCTIONS
# =============================================================================


def calculate_three_phase_power(
    v1_t: np.ndarray,
    v2_t: np.ndarray,
    v3_t: np.ndarray,
    i1_t: np.ndarray,
    i2_t: np.ndarray,
    i3_t: np.ndarray,
) -> dict:
    """
    Calculate three-phase power metrics.

    Args:
        v1_t, v2_t, v3_t: Voltage time-domain samples for phases 1, 2, 3
        i1_t, i2_t, i3_t: Current time-domain samples for phases 1, 2, 3

    Returns:
        Dictionary with three-phase power metrics
    """
    # Per-phase RMS
    v1_rms = np.sqrt(np.mean(v1_t**2))
    v2_rms = np.sqrt(np.mean(v2_t**2))
    v3_rms = np.sqrt(np.mean(v3_t**2))

    i1_rms = np.sqrt(np.mean(i1_t**2))
    i2_rms = np.sqrt(np.mean(i2_t**2))
    i3_rms = np.sqrt(np.mean(i3_t**2))

    # Per-phase instantaneous power
    p1_t = v1_t * i1_t
    p2_t = v2_t * i2_t
    p3_t = v3_t * i3_t

    # Per-phase active power
    p1 = np.mean(p1_t)
    p2 = np.mean(p2_t)
    p3 = np.mean(p3_t)

    # Total active power
    p_total = p1 + p2 + p3

    # Per-phase apparent power
    s1 = v1_rms * i1_rms
    s2 = v2_rms * i2_rms
    s3 = v3_rms * i3_rms

    # Total apparent power (arithmetic sum for unbalanced systems)
    s_total = s1 + s2 + s3

    # Per-phase reactive power
    q1 = np.sqrt(max(0, s1**2 - p1**2))
    q2 = np.sqrt(max(0, s2**2 - p2**2))
    q3 = np.sqrt(max(0, s3**2 - p3**2))

    # Total reactive power
    q_total = q1 + q2 + q3

    # Three-phase power factor
    pf_3ph = p_total / s_total if s_total > 0 else 0

    # Balance indicators
    v_avg = (v1_rms + v2_rms + v3_rms) / 3
    i_avg = (i1_rms + i2_rms + i3_rms) / 3

    v_unbalance = (
        max(abs(v1_rms - v_avg), abs(v2_rms - v_avg), abs(v3_rms - v_avg)) / v_avg
        if v_avg > 0
        else 0
    )

    i_unbalance = (
        max(abs(i1_rms - i_avg), abs(i2_rms - i_avg), abs(i3_rms - i_avg)) / i_avg
        if i_avg > 0
        else 0
    )

    return {
        # Per-phase RMS
        "V1_rms": v1_rms,
        "V2_rms": v2_rms,
        "V3_rms": v3_rms,
        "I1_rms": i1_rms,
        "I2_rms": i2_rms,
        "I3_rms": i3_rms,
        # Per-phase power
        "P1": p1,
        "P2": p2,
        "P3": p3,
        "Q1": q1,
        "Q2": q2,
        "Q3": q3,
        "S1": s1,
        "S2": s2,
        "S3": s3,
        # Total power
        "P_total": p_total,
        "Q_total": q_total,
        "S_total": s_total,
        "PF_3ph": pf_3ph,
        # Balance indicators
        "V_unbalance": v_unbalance,
        "I_unbalance": i_unbalance,
        # Instantaneous power
        "p1_t": p1_t,
        "p2_t": p2_t,
        "p3_t": p3_t,
    }


def calculate_sequence_components(
    v1_rms: float,
    v2_rms: float,
    v3_rms: float,
    v1_phase: float,
    v2_phase: float,
    v3_phase: float,
) -> dict:
    """
    Calculate symmetrical components (positive, negative, zero sequence).

    Args:
        v1_rms, v2_rms, v3_rms: RMS values of phases 1, 2, 3
        v1_phase, v2_phase, v3_phase: Phase angles in radians

    Returns:
        Dictionary with sequence components
    """
    # Convert to complex phasors
    v1_complex = v1_rms * np.exp(1j * v1_phase)
    v2_complex = v2_rms * np.exp(1j * v2_phase)
    v3_complex = v3_rms * np.exp(1j * v3_phase)

    # Operator a = e^(j*120°)
    a = np.exp(1j * np.radians(120))
    a2 = np.exp(1j * np.radians(240))

    # Sequence components
    v0 = (v1_complex + v2_complex + v3_complex) / 3  # Zero sequence
    v_pos = (v1_complex + a * v2_complex + a2 * v3_complex) / 3  # Positive sequence
    v_neg = (v1_complex + a2 * v2_complex + a * v3_complex) / 3  # Negative sequence

    # Magnitudes
    v0_mag = np.abs(v0)
    v_pos_mag = np.abs(v_pos)
    v_neg_mag = np.abs(v_neg)

    # Unbalance factors
    vuf = v_neg_mag / v_pos_mag if v_pos_mag > 0 else 0  # Voltage Unbalance Factor
    v0_factor = v0_mag / v_pos_mag if v_pos_mag > 0 else 0

    return {
        "V0": v0_mag,
        "V_pos": v_pos_mag,
        "V_neg": v_neg_mag,
        "VUF": vuf,
        "V0_factor": v0_factor,
        "V0_phase": np.angle(v0),
        "V_pos_phase": np.angle(v_pos),
        "V_neg_phase": np.angle(v_neg),
    }


def calculate_three_phase_cpc(
    v1_t: np.ndarray,
    v2_t: np.ndarray,
    v3_t: np.ndarray,
    i1_t: np.ndarray,
    i2_t: np.ndarray,
    i3_t: np.ndarray,
    sampling_freq: float,
    fundamental_freq: float,
) -> dict:
    """
    Calculate Czarnecki's CPC decomposition for three-phase system.

    Args:
        v1_t, v2_t, v3_t: Voltage time-domain samples for phases 1, 2, 3
        i1_t, i2_t, i3_t: Current time-domain samples for phases 1, 2, 3
        sampling_freq: Sampling frequency (Hz)
        fundamental_freq: Fundamental frequency (Hz)

    Returns:
        Dictionary with three-phase CPC components
    """
    # Calculate per-phase CPC components
    cpc_1 = calculate_cpc_components(v1_t, i1_t, sampling_freq, fundamental_freq)
    cpc_2 = calculate_cpc_components(v2_t, i2_t, sampling_freq, fundamental_freq)
    cpc_3 = calculate_cpc_components(v3_t, i3_t, sampling_freq, fundamental_freq)

    # Aggregate three-phase CPC components
    i_a_rms_total = np.sqrt(cpc_1["I_a"] ** 2 + cpc_2["I_a"] ** 2 + cpc_3["I_a"] ** 2)
    i_r_rms_total = np.sqrt(cpc_1["I_r"] ** 2 + cpc_2["I_r"] ** 2 + cpc_3["I_r"] ** 2)
    i_s_rms_total = np.sqrt(cpc_1["I_s"] ** 2 + cpc_2["I_s"] ** 2 + cpc_3["I_s"] ** 2)
    i_g_rms_total = np.sqrt(cpc_1["I_g"] ** 2 + cpc_2["I_g"] ** 2 + cpc_3["I_g"] ** 2)
    i_rms_total = np.sqrt(
        cpc_1["I_rms"] ** 2 + cpc_2["I_rms"] ** 2 + cpc_3["I_rms"] ** 2
    )

    # Calculate unbalance current (due to voltage asymmetry between phases)
    # RMS values for fundamental components
    v1_rms = np.sqrt(np.mean(v1_t**2))
    v2_rms = np.sqrt(np.mean(v2_t**2))
    v3_rms = np.sqrt(np.mean(v3_t**2))
    i1_rms = cpc_1["I_rms"]
    i2_rms = cpc_2["I_rms"]
    i3_rms = cpc_3["I_rms"]

    # Average equivalent conductance per phase
    g_avg = (
        (i1_rms / v1_rms + i2_rms / v2_rms + i3_rms / v3_rms) / 3
        if min(v1_rms, v2_rms, v3_rms) > 0
        else 0
    )

    # Unbalance current components per phase (difference from balanced equivalent)
    i_u1 = abs(i1_rms - g_avg * v1_rms) if v1_rms > 0 else 0
    i_u2 = abs(i2_rms - g_avg * v2_rms) if v2_rms > 0 else 0
    i_u3 = abs(i3_rms - g_avg * v3_rms) if v3_rms > 0 else 0

    # Total unbalance current (RMS sum)
    i_u_rms_total = np.sqrt(i_u1**2 + i_u2**2 + i_u3**2)

    # Unbalance power
    d_u_total = np.sqrt(
        (v1_rms * i_u1) ** 2 + (v2_rms * i_u2) ** 2 + (v3_rms * i_u3) ** 2
    )

    # Total power components
    p_total = cpc_1["P"] + cpc_2["P"] + cpc_3["P"]
    q1_total = cpc_1["Q1"] + cpc_2["Q1"] + cpc_3["Q1"]
    d_s_total = np.sqrt(cpc_1["D_s"] ** 2 + cpc_2["D_s"] ** 2 + cpc_3["D_s"] ** 2)
    d_g_total = np.sqrt(cpc_1["D_g"] ** 2 + cpc_2["D_g"] ** 2 + cpc_3["D_g"] ** 2)
    s_total = cpc_1["S"] + cpc_2["S"] + cpc_3["S"]

    # Current ratios
    lambda_a = i_a_rms_total / i_rms_total if i_rms_total > 0 else 0
    lambda_r = i_r_rms_total / i_rms_total if i_rms_total > 0 else 0
    lambda_s = i_s_rms_total / i_rms_total if i_rms_total > 0 else 0
    lambda_u = i_u_rms_total / i_rms_total if i_rms_total > 0 else 0
    lambda_g = i_g_rms_total / i_rms_total if i_rms_total > 0 else 0

    return {
        # Per-phase CPC
        "cpc_1": cpc_1,
        "cpc_2": cpc_2,
        "cpc_3": cpc_3,
        # Total CPC components
        "I_a_total": i_a_rms_total,
        "I_r_total": i_r_rms_total,
        "I_s_total": i_s_rms_total,
        "I_u_total": i_u_rms_total,  # Unbalance current
        "I_g_total": i_g_rms_total,
        "I_rms_total": i_rms_total,
        # Total power components
        "P_total": p_total,
        "Q1_total": q1_total,
        "D_s_total": d_s_total,
        "D_u_total": d_u_total,  # Unbalance power
        "D_g_total": d_g_total,
        "S_total": s_total,
        # Current ratios
        "lambda_a": lambda_a,
        "lambda_r": lambda_r,
        "lambda_s": lambda_s,
        "lambda_u": lambda_u,  # Unbalance ratio
        "lambda_g": lambda_g,
        # Power factors
        "PF": p_total / s_total if s_total > 0 else 0,
        "DPF": np.mean([cpc_1["DPF"], cpc_2["DPF"], cpc_3["DPF"]]),
        "DF": np.mean([cpc_1["DF"], cpc_2["DF"], cpc_3["DF"]]),
    }
