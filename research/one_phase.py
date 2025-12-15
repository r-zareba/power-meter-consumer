import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# System parameters matching ADCReceiver and IEC 61000-4-7
# Fundamental Power Measurements (IEC 61000-4-30 Class A/S)
SAMPLING_FREQ = 10000  # Hz
NUM_SAMPLES = 2000  # 200ms window (10 cycles at 50Hz) for IEC 61000-4-7 compliance
MAINS_FREQ = 50  # Hz


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


def plot_power_analysis(
    time: np.ndarray,
    voltage: np.ndarray,
    current: np.ndarray,
    power: np.ndarray,
    p_avg: float,
    title: str = "Power Analysis",
):
    """
    Plot voltage, current, and instantaneous power.

    Args:
        time: Time array (s)
        voltage: Voltage samples (V)
        current: Current samples (A)
        power: Instantaneous power p(t) (W)
        p_avg: Average active power (W)
        title: Plot title
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=("Voltage", "Current", "Instantaneous Power p(t)"),
    )

    # Voltage
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=voltage,
            mode="lines",
            name="Voltage",
            line=dict(color="blue"),
        ),
        row=1,
        col=1,
    )

    # Current
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=current,
            mode="lines",
            name="Current",
            line=dict(color="red"),
        ),
        row=2,
        col=1,
    )

    # Instantaneous Power
    fig.add_trace(
        go.Scatter(
            x=time * 1000, y=power, mode="lines", name="p(t)", line=dict(color="green")
        ),
        row=3,
        col=1,
    )

    # Average Power line
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=[p_avg] * len(time),
            mode="lines",
            name=f"P_avg = {p_avg:.2f}W",
            line=dict(color="orange", dash="dash"),
        ),
        row=3,
        col=1,
    )

    fig.update_xaxes(title_text="Time (ms)", row=3, col=1)
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=2, col=1)
    fig.update_yaxes(title_text="Power (W)", row=3, col=1)

    fig.update_layout(title_text=title, height=1000, showlegend=True)

    fig.show()


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


if __name__ == "__main__":
    # Example usage - generate time-domain signals
    vt, v_t = generate_sine(
        amplitude=325,
        frequency=MAINS_FREQ,
        phase=0,
        sampling_freq=SAMPLING_FREQ,
        num_samples=NUM_SAMPLES,
        harmonics=None,
    )  # 230V RMS → ~325V peak
    it, i_t = generate_sine(
        amplitude=2,
        frequency=MAINS_FREQ,
        phase=np.radians(-30),  # 30° lagging
        sampling_freq=SAMPLING_FREQ,
        num_samples=NUM_SAMPLES,
        harmonics=None,
    )

    # Step 1: Calculate RMS values (Foundation - works with all harmonics and distortions)
    v_rms = np.sqrt(np.mean(v_t**2))
    i_rms = np.sqrt(np.mean(i_t**2))

    print("=== Step 1: RMS Values ===")
    print(f"Voltage RMS: {v_rms:.2f} V")
    print(f"Current RMS: {i_rms:.2f} A")
    print()

    # Step 2: Calculate Instantaneous Power and Active Power
    # p(t) = v(t) × i(t) at each sample (oscillates at 2× grid frequency)
    p_t = v_t * i_t

    # Active Power P = time average of p(t) (removes oscillations, gives steady-state delivery)
    p = np.mean(p_t)

    print("=== Step 2: Active Power ===")
    print(f"Instantaneous Power p(t): {len(p_t)} samples (oscillating)")
    print(f"Active Power (P): {p:.2f} W (time-averaged)")
    print()

    # Step 3: Calculate Apparent Power (Total power capacity of system)
    # S = V_rms × I_rms (product of RMS values, includes active + reactive)
    s = v_rms * i_rms

    print("=== Step 3: Apparent Power ===")
    print(f"Apparent Power (S): {s:.2f} VA")
    print()

    # Step 4: Calculate Reactive Power (Non-working power that oscillates)
    # Q = √(S² - P²) - classical/IEC definition
    q = np.sqrt(max(0, s**2 - p**2))

    print("=== Step 4: Reactive Power ===")
    print(f"Reactive Power (Q): {q:.2f} VAR")
    print()

    # Step 5: Calculate Power Factor (Efficiency metric)
    # PF = P / S - ratio of useful to total power
    pf = p / s if s > 0 else 0.0

    print("=== Step 5: Power Factor ===")
    print(f"Power Factor (PF): {pf:.3f}")
    print(f"PF percentage: {pf * 100:.1f}%")
    print()

    # Step 6a: Harmonic Analysis - Amplitudes (Frequency domain decomposition)
    # Extract individual harmonic amplitudes H1-H50 using FFT
    v_harmonics = analyze_harmonics(v_t, SAMPLING_FREQ, MAINS_FREQ)
    i_harmonics = analyze_harmonics(i_t, SAMPLING_FREQ, MAINS_FREQ)

    print("=== Step 6a: Harmonic Amplitudes ===")
    print(f"Voltage Harmonics (first 5):")
    for h in range(1, 6):
        print(f"  H{h}: {v_harmonics[h]:.2f} V")

    print(f"\nCurrent Harmonics (first 5):")
    for h in range(1, 6):
        print(f"  H{h}: {i_harmonics[h]:.2f} A")
    print()

    # Step 6b: Harmonic Analysis with Phase (Advanced)
    # Extract amplitude AND phase for each harmonic (needed for per-harmonic power, DPF, CPC)
    v_harmonics_phase = analyze_harmonics_with_phase(v_t, SAMPLING_FREQ, MAINS_FREQ)
    i_harmonics_phase = analyze_harmonics_with_phase(i_t, SAMPLING_FREQ, MAINS_FREQ)

    print("=== Step 6b: Harmonic Phases (Fundamental) ===")
    v1_amp, v1_phase = v_harmonics_phase[1]
    i1_amp, i1_phase = i_harmonics_phase[1]
    phase_diff = v1_phase - i1_phase

    print(f"Voltage H1 phase: {np.degrees(v1_phase):.1f}°")
    print(f"Current H1 phase: {np.degrees(i1_phase):.1f}°")
    print(f"Phase difference: {np.degrees(phase_diff):.1f}°")
    print(f"Displacement PF (cos φ): {np.cos(phase_diff):.3f}")
    print()

    # Step 7: Calculate THD (Total Harmonic Distortion)
    # THD = √(H2² + H3² + ... + H50²) / H1
    v_thd = calculate_thd(v_harmonics)
    i_thd = calculate_thd(i_harmonics)

    print("=== Step 7: Total Harmonic Distortion ===")
    print(f"Voltage THD: {v_thd * 100:.2f}%")
    print(f"Current THD: {i_thd * 100:.2f}%")
    print()

    print("=" * 50)
    print("PHASE 2: Standard Compliance Metrics")
    print("=" * 50)
    print()

    # Step 8: Frequency Tracking (Grid frequency measurement)
    # Use fundamental harmonic bin location to estimate actual frequency
    v1_amp, v1_phase = v_harmonics_phase[1]
    # In real system: track zero crossings or use PLL, here we assume exact 50Hz
    measured_freq = (
        MAINS_FREQ  # Placeholder - actual freq tracking needs zero-crossing detection
    )

    print("=== Step 8: Frequency Tracking ===")
    print(f"Grid Frequency: {measured_freq:.3f} Hz")
    print(f"Deviation: {(measured_freq - MAINS_FREQ) * 1000:.1f} mHz")
    print()

    # Step 9: Crest Factor (Peak-to-RMS ratio)
    # Indicates waveform "peakiness" - √2 for pure sine, higher for distorted
    v_peak = np.max(np.abs(v_t))
    i_peak = np.max(np.abs(i_t))
    v_crest = v_peak / v_rms
    i_crest = i_peak / i_rms

    print("=== Step 9: Crest Factor ===")
    print(f"Voltage Crest Factor: {v_crest:.3f} (ideal: {np.sqrt(2):.3f})")
    print(f"Current Crest Factor: {i_crest:.3f}")
    print()

    # Step 10: TDD (Total Demand Distortion) - IEEE 519 requirement
    # Similar to THD but normalized to rated/demand current instead of fundamental
    i_rated = 10.0  # Assume 10A rated current for this example
    i_harmonic_rms = np.sqrt(sum(i_harmonics[h] ** 2 for h in range(2, 51))) / np.sqrt(
        2
    )
    tdd = i_harmonic_rms / i_rated

    print("=== Step 10: TDD (IEEE 519) ===")
    print(f"Rated Current: {i_rated:.2f} A")
    print(f"Harmonic Current RMS: {i_harmonic_rms:.2f} A")
    print(f"TDD: {tdd * 100:.2f}%")
    print()

    # Step 11: Voltage Event Detection (Sag/Swell)
    # Check if voltage deviates >10% from nominal
    v_nominal = 230.0  # 230V RMS nominal
    v_deviation = (v_rms - v_nominal) / v_nominal

    print("=== Step 11: Voltage Event Detection ===")
    print(f"Nominal Voltage: {v_nominal:.1f} V")
    print(f"Measured Voltage: {v_rms:.2f} V")
    print(f"Deviation: {v_deviation * 100:.2f}%")

    if v_deviation < -0.10:
        print(f"⚠️  VOLTAGE SAG detected ({abs(v_deviation) * 100:.1f}% drop)")
    elif v_deviation > 0.10:
        print(f"⚠️  VOLTAGE SWELL detected ({v_deviation * 100:.1f}% rise)")
    else:
        print("✓ Voltage within normal range")
    print()

    # Step 12: Summary of all Phase 2 metrics
    print("=== Phase 2 Summary ===")
    print(f"Frequency: {measured_freq:.3f} Hz")
    print(f"Crest Factors: V={v_crest:.3f}, I={i_crest:.3f}")
    print(f"TDD: {tdd * 100:.2f}%")
    print(f"DPF (cos φ₁): {np.cos(phase_diff):.3f}")
    print()

    print("=" * 50)
    print("PHASE 3: Advanced Features")
    print("=" * 50)
    print()

    # Step 13: Per-Harmonic Power (Power contribution from each harmonic)
    # P_h = V_h × I_h × cos(θ_v,h - θ_i,h)
    print("=== Step 13: Per-Harmonic Power ===")
    per_harmonic_power = {}
    total_harmonic_power = 0

    for h in range(1, 11):  # Show first 10 harmonics
        v_h_amp, v_h_phase = v_harmonics_phase[h]
        i_h_amp, i_h_phase = i_harmonics_phase[h]

        # Convert peak to RMS
        v_h_rms = v_h_amp / np.sqrt(2)
        i_h_rms = i_h_amp / np.sqrt(2)

        # Phase difference for this harmonic
        phase_h = v_h_phase - i_h_phase

        # Power at this harmonic
        p_h = v_h_rms * i_h_rms * np.cos(phase_h)
        per_harmonic_power[h] = p_h
        total_harmonic_power += p_h

        if h <= 5:  # Print first 5
            print(
                f"  H{h} Power: {p_h:.2f} W (V={v_h_rms:.1f}V, I={i_h_rms:.2f}A, φ={np.degrees(phase_h):.1f}°)"
            )

    print(f"\nTotal Power (sum of harmonics): {total_harmonic_power:.2f} W")
    print(f"Direct calculation P: {p:.2f} W")
    print(f"Difference: {abs(total_harmonic_power - p):.2f} W")
    print()

    # Step 14: K-Factor (Transformer derating due to harmonics)
    # K = Σ(I_h² × h²) / I_rms² - measures heating effect
    k_factor_sum = 0
    for h in range(1, 51):
        i_h_amp, _ = i_harmonics_phase[h]
        i_h_rms = i_h_amp / np.sqrt(2)
        k_factor_sum += (i_h_rms**2) * (h**2)

    k_factor = k_factor_sum / (i_rms**2) if i_rms > 0 else 1.0

    print("=== Step 14: K-Factor (Transformer Derating) ===")
    print(f"K-Factor: {k_factor:.2f}")
    print(f"Interpretation:")
    if k_factor < 4:
        print("  ✓ Standard transformer (K-1) is adequate")
    elif k_factor < 13:
        print(f"  ⚠️  Requires K-{int(np.ceil(k_factor / 4) * 4)} rated transformer")
    else:
        print(f"  ⚠️  Requires K-13 or higher transformer")
    print()

    # Step 15: CPC Decomposition (Czarnecki's Theory)
    # Decompose current into physical components: i_a, i_r, i_s, i_g
    print("=== Step 15: CPC Decomposition (Czarnecki) ===")
    cpc = calculate_cpc_components(v_t, i_t, SAMPLING_FREQ, MAINS_FREQ)

    print("Current Components (RMS):")
    print(
        f"  Active Current (I_a):     {cpc['I_a']:.3f} A ({cpc['lambda_a'] * 100:.1f}%)"
    )
    print(
        f"  Reactive Current (I_r):   {cpc['I_r']:.3f} A ({cpc['lambda_r'] * 100:.1f}%)"
    )
    print(
        f"  Scattered Current (I_s):  {cpc['I_s']:.3f} A ({cpc['lambda_s'] * 100:.1f}%)"
    )
    print(
        f"  Generated Current (I_g):  {cpc['I_g']:.3f} A ({cpc['lambda_g'] * 100:.1f}%)"
    )
    print(f"  Total Current (I_rms):    {cpc['I_rms']:.3f} A")

    # Verify orthogonality
    i_check = np.sqrt(
        cpc["I_a"] ** 2 + cpc["I_r"] ** 2 + cpc["I_s"] ** 2 + cpc["I_g"] ** 2
    )
    print(f"  Verification: √(Σ I²) =   {i_check:.3f} A")

    print("\nPower Components:")
    print(f"  Active Power (P):      {cpc['P']:.2f} W")
    print(f"  Reactive Power (Q₁):   {cpc['Q1']:.2f} VAR")
    print(f"  Scattered Power (D_s): {cpc['D_s']:.2f} VA")
    print(f"  Generated Power (D_g): {cpc['D_g']:.2f} VA")
    print(f"  Apparent Power (S):    {cpc['S']:.2f} VA")

    print("\nPower Factors:")
    print(f"  Total PF:           {cpc['PF']:.3f}")
    print(f"  Displacement PF:    {cpc['DPF']:.3f}")
    print(f"  Distortion Factor:  {cpc['DF']:.3f}")
    print(f"  Relationship: PF = DPF × DF = {cpc['DPF'] * cpc['DF']:.3f}")
    print()

    # Step 16: Phase 3 Summary
    print("=== Phase 3 Summary ===")
    print(f"Per-harmonic analysis: {len(per_harmonic_power)} harmonics calculated")
    print(f"K-Factor: {k_factor:.2f} (transformer derating)")
    print(f"CPC decomposition complete:")
    print(f"  - Load generates {cpc['lambda_g'] * 100:.1f}% harmonic current (I_g)")
    print(
        f"  - Supply contributes {cpc['lambda_s'] * 100:.1f}% scattered current (I_s)"
    )
    print(f"  - Traditional reactive {cpc['lambda_r'] * 100:.1f}% (I_r)")
    print()

    # Visualization
    print("Generating plots...")
    plot_power_analysis(vt, v_t, i_t, p_t, p, title="Single-Phase Power Analysis")
