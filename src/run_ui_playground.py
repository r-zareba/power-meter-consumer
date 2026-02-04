"""
Interactive Streamlit application for single-phase and three-phase power analysis.
IEC 61000-4-7 & IEC 61000-4-30 compliant.
"""

import numpy as np
import streamlit as st

# Import all calculation functions from analytics module
from analytics.analytics import (
    MAINS_FREQ,
    NUM_SAMPLES,
    SAMPLING_FREQ,
    analyze_harmonics,
    analyze_harmonics_with_phase,
    calculate_cpc_components,
    calculate_sequence_components,
    calculate_thd,
    calculate_three_phase_cpc,
    calculate_three_phase_power,
    generate_sine,
    generate_thyristor_current,
    generate_triac_current,
)


def render_single_phase_tab():
    """Render single-phase analysis tab"""
    st.header("Single-Phase Power Analysis")
    st.markdown("*IEC 61000-4-7 & IEC 61000-4-30 Compliant*")

    # Sidebar controls
    st.sidebar.header("Signal Parameters")

    st.sidebar.subheader("Voltage")
    v_amp = st.sidebar.slider("Amplitude (V peak)", 10, 400, 325, 5, key="1ph_v_amp")
    v_phase_deg = st.sidebar.slider("Phase (°)", -180, 180, 0, 5, key="1ph_v_phase")

    st.sidebar.subheader("Current")
    current_waveform_type = st.sidebar.selectbox(
        "Waveform Type", 
        ["Sine", "Thyristor (SCR)", "Triac"],
        key="1ph_current_type"
    )
    
    i_amp = st.sidebar.slider(
        "Amplitude (A peak)", 0.1, 20.0, 14.14, 0.1, key="1ph_i_amp"
    )
    
    if current_waveform_type == "Sine":
        i_phase_deg = st.sidebar.slider("Phase (°)", -180, 180, 0, 5, key="1ph_i_phase")
    else:
        firing_angle_deg = st.sidebar.slider(
            "Firing Angle (°)", 0, 180, 60, 5, key="1ph_firing_angle"
        )

    st.sidebar.subheader("Harmonics")
    add_harmonics = st.sidebar.checkbox("Add Harmonics", key="1ph_harmonics")
    v_harmonics_dict = None
    i_harmonics_dict = None

    if add_harmonics:
        harmonics_tabs = st.sidebar.tabs(["Voltage Harmonics", "Current Harmonics"])

        # Voltage Harmonics
        with harmonics_tabs[0]:
            st.write("**Voltage Odd Harmonics**")
            v_harmonics_dict = {}

            for h in [3, 5, 7, 9, 11, 13, 15, 17, 19]:
                col_amp, col_phase = st.columns(2)
                with col_amp:
                    v_h_pct = st.slider(f"H{h} %", 0, 50, 0, 1, key=f"1ph_v_h{h}_pct")
                with col_phase:
                    v_h_phase = st.slider(
                        f"φ{h} °", -180, 180, 0, 15, key=f"1ph_v_h{h}_phase"
                    )

                if v_h_pct > 0:
                    v_harmonics_dict[h] = (v_h_pct / 100, np.radians(v_h_phase))

        # Current Harmonics
        with harmonics_tabs[1]:
            st.write("**Current Odd Harmonics**")
            i_harmonics_dict = {}

            for h in [3, 5, 7, 9, 11, 13, 15, 17, 19]:
                col_amp, col_phase = st.columns(2)
                with col_amp:
                    i_h_pct = st.slider(f"H{h} %", 0, 50, 0, 1, key=f"1ph_i_h{h}_pct")
                with col_phase:
                    i_h_phase = st.slider(
                        f"φ{h} °", -180, 180, 0, 15, key=f"1ph_i_h{h}_phase"
                    )

                if i_h_pct > 0:
                    i_harmonics_dict[h] = (i_h_pct / 100, np.radians(i_h_phase))

    # Generate signals
    v_phase = np.radians(v_phase_deg)

    t, v_t = generate_sine(
        v_amp, MAINS_FREQ, v_phase, SAMPLING_FREQ, NUM_SAMPLES, v_harmonics_dict
    )
    
    # Generate current based on waveform type
    if current_waveform_type == "Sine":
        i_phase = np.radians(i_phase_deg)
        _, i_t = generate_sine(
            i_amp, MAINS_FREQ, i_phase, SAMPLING_FREQ, NUM_SAMPLES, i_harmonics_dict
        )
    elif current_waveform_type == "Thyristor (SCR)":
        i_t = generate_thyristor_current(
            v_t, i_amp, firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )
    else:  # Triac
        i_t = generate_triac_current(
            v_t, i_amp, firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )

    # Calculate metrics
    v_rms = np.sqrt(np.mean(v_t**2))
    i_rms = np.sqrt(np.mean(i_t**2))
    p_t = v_t * i_t
    p = np.mean(p_t)
    s = v_rms * i_rms
    q = np.sqrt(max(0, s**2 - p**2))
    pf = p / s if s > 0 else 0.0

    # Harmonics
    v_harmonics = analyze_harmonics(v_t, SAMPLING_FREQ, MAINS_FREQ)
    i_harmonics = analyze_harmonics(i_t, SAMPLING_FREQ, MAINS_FREQ)
    v_thd = calculate_thd(v_harmonics)
    i_thd = calculate_thd(i_harmonics)

    # Display metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("V RMS (Wartość skuteczna)", f"{v_rms:.2f} V")
        st.metric("I RMS (Wartość skuteczna)", f"{i_rms:.2f} A")

    with col2:
        st.metric("Active Power (P) - Moc czynna", f"{p:.2f} W")
        st.metric("Apparent Power (S) - Moc pozorna", f"{s:.2f} VA")

    with col3:
        st.metric("Reactive Power (Q) - Moc bierna", f"{q:.2f} VAR")
        st.metric("Power Factor (Współczynnik mocy)", f"{pf:.3f}")

    with col4:
        st.metric("Voltage THD (THD napięcia)", f"{v_thd * 100:.2f}%")
        st.metric("Current THD (THD prądu)", f"{i_thd * 100:.2f}%")

    # Plots
    st.subheader("Waveforms")

    # Create plot using Streamlit's native plotly integration
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=("Voltage", "Current", "Moc czynna chwilowa p(t)"),
    )

    fig.add_trace(
        go.Scatter(
            x=t * 1000, y=v_t, mode="lines", name="Voltage", line=dict(color="blue")
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=t * 1000, y=i_t, mode="lines", name="Current", line=dict(color="red")
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=t * 1000, y=p_t, mode="lines", name="p(t)", line=dict(color="green")
        ),
        row=3,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=t * 1000,
            y=[p] * len(t),
            mode="lines",
            name=f"P_avg = {p:.2f}W",
            line=dict(color="orange", dash="dash"),
        ),
        row=3,
        col=1,
    )

    fig.update_xaxes(title_text="Time (ms)", row=3, col=1)
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=2, col=1)
    fig.update_yaxes(title_text="Power (W)", row=3, col=1)

    fig.update_layout(height=800, showlegend=True)
    st.plotly_chart(fig, width="stretch")

    # Advanced metrics section (always visible)
    st.subheader("Advanced Metrics")

    v_harmonics_phase = analyze_harmonics_with_phase(v_t, SAMPLING_FREQ, MAINS_FREQ)
    i_harmonics_phase = analyze_harmonics_with_phase(i_t, SAMPLING_FREQ, MAINS_FREQ)

    v1_amp, v1_phase = v_harmonics_phase[1]
    i1_amp, i1_phase = i_harmonics_phase[1]
    phase_diff = v1_phase - i1_phase
    dpf = np.cos(phase_diff)

    # Calculate CPC decomposition
    cpc = calculate_cpc_components(v_t, i_t, SAMPLING_FREQ, MAINS_FREQ)

    # Phase 2 Metrics
    st.subheader("Phase 2: Standard Compliance")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Power Factors (Współczynniki mocy)**")
        st.write(f"- Displacement PF (Wsp. przesunięcia): {dpf:.3f}")
        st.write(f"- Distortion Factor (Wsp. zniekształcenia): {cpc['DF']:.3f}")
        st.write(f"- Total PF = DPF × DF: {cpc['PF']:.3f}")

    with col2:
        st.write("**Waveform Quality**")
        v_crest = np.max(np.abs(v_t)) / v_rms
        i_crest = np.max(np.abs(i_t)) / i_rms
        st.write(f"- V Crest Factor: {v_crest:.3f}")
        st.write(f"- I Crest Factor: {i_crest:.3f}")
        st.write(f"- Phase Difference: {np.degrees(phase_diff):.1f}°")

    with col3:
        st.write("**Harmonics Overview**")
        st.write(f"- Voltage THD: {v_thd * 100:.2f}%")
        st.write(f"- Current THD: {i_thd * 100:.2f}%")
        st.write(f"- Fundamental: {v_harmonics[1]:.1f}V, {i_harmonics[1]:.2f}A")

    # Phase 3: Czarnecki CPC Theory
    st.subheader("Phase 3: Czarnecki CPC Decomposition")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Current Components (RMS) - Składowe prądu**")
        st.write(
            f"Active (prąd aktywny): {cpc['I_a']:.3f} A ({cpc['lambda_a'] * 100:.1f}%)"
        )
        st.write(
            f"Reactive (prąd bierny): {cpc['I_r']:.3f} A ({cpc['lambda_r'] * 100:.1f}%)"
        )
        st.write(
            f"Scattered (prąd rozrzutu): {cpc['I_s']:.3f} A ({cpc['lambda_s'] * 100:.1f}%)"
        )
        st.write(
            f"Generated (prąd generowany): {cpc['I_g']:.3f} A ({cpc['lambda_g'] * 100:.1f}%)"
        )
        st.write(f"**Total (prąd całkowity): {cpc['I_rms']:.3f} A**")

        # Orthogonality check
        i_check = np.sqrt(
            cpc["I_a"] ** 2 + cpc["I_r"] ** 2 + cpc["I_s"] ** 2 + cpc["I_g"] ** 2
        )
        st.write(f"- ✓ Verification: {i_check:.3f} A")

    with col2:
        st.write("**Power Components (Składowe mocy)**")
        st.write(f"Active Power (Moc czynna): {cpc['P']:.2f} W")
        st.write(f"Reactive Power (Moc bierna): {cpc['Q1']:.2f} VAR")
        st.write(f"Scattered Power (Moc rozrzutu): {cpc['D_s']:.2f} VA")
        st.write(f"Generated Power (Moc generowana): {cpc['D_g']:.2f} VA")
        st.write(f"**Apparent Power (Moc pozorna): {cpc['S']:.2f} VA**")
        st.write("")
        st.write("**Interpretation:**")
        st.write(f"- Load distortion: {cpc['lambda_g'] * 100:.1f}%")
        st.write(f"- Supply distortion: {cpc['lambda_s'] * 100:.1f}%")

    # Harmonic table
    st.subheader("Harmonic Analysis (Up to 19th)")
    harmonic_data = []
    for h in range(1, 20):
        v_h_amp, v_h_phase = v_harmonics_phase[h]
        i_h_amp, i_h_phase = i_harmonics_phase[h]
        harmonic_data.append(
            {
                "H": h,
                "V (V)": f"{v_h_amp:.2f}",
                "I (A)": f"{i_h_amp:.3f}",
                "V Phase (°)": f"{np.degrees(v_h_phase):.1f}",
                "I Phase (°)": f"{np.degrees(i_h_phase):.1f}",
            }
        )

    st.table(harmonic_data)


def render_three_phase_tab():
    """Render three-phase analysis tab"""
    st.header("Three-Phase Power Analysis")
    st.markdown("*IEC 61000-4-7 & IEC 61000-4-30 Compliant*")

    # Sidebar controls for three phases
    st.sidebar.header("Three-Phase Parameters")

    # Phase 1
    st.sidebar.subheader("Phase 1 - Voltage")
    v1_amp = st.sidebar.slider("Amplitude (V peak)", 10, 400, 325, 5, key="3ph_v1_amp")
    v1_phase_deg = st.sidebar.slider("Phase (°)", -180, 180, 0, 5, key="3ph_v1_phase")

    st.sidebar.subheader("Phase 1 - Current")
    i1_waveform_type = st.sidebar.selectbox(
        "Waveform Type", 
        ["Sine", "Thyristor (SCR)", "Triac"],
        key="3ph_i1_type"
    )
    i1_amp = st.sidebar.slider(
        "Amplitude (A peak)", 0.1, 20.0, 14.14, 0.1, key="3ph_i1_amp"
    )
    if i1_waveform_type == "Sine":
        i1_phase_deg = st.sidebar.slider("Phase (°)", -180, 180, 0, 5, key="3ph_i1_phase")
    else:
        i1_firing_angle_deg = st.sidebar.slider(
            "Firing Angle (°)", 0, 180, 60, 5, key="3ph_i1_firing"
        )

    # Phase 2
    st.sidebar.subheader("Phase 2 - Voltage")
    v2_amp = st.sidebar.slider("Amplitude (V peak)", 10, 400, 325, 5, key="3ph_v2_amp")
    v2_phase_deg = st.sidebar.slider(
        "Phase (°)", -180, 180, -120, 5, key="3ph_v2_phase"
    )

    st.sidebar.subheader("Phase 2 - Current")
    i2_waveform_type = st.sidebar.selectbox(
        "Waveform Type", 
        ["Sine", "Thyristor (SCR)", "Triac"],
        key="3ph_i2_type"
    )
    i2_amp = st.sidebar.slider(
        "Amplitude (A peak)", 0.1, 20.0, 14.14, 0.1, key="3ph_i2_amp"
    )
    if i2_waveform_type == "Sine":
        i2_phase_deg = st.sidebar.slider(
            "Phase (°)", -180, 180, -120, 5, key="3ph_i2_phase"
        )
    else:
        i2_firing_angle_deg = st.sidebar.slider(
            "Firing Angle (°)", 0, 180, 60, 5, key="3ph_i2_firing"
        )

    # Phase 3
    st.sidebar.subheader("Phase 3 - Voltage")
    v3_amp = st.sidebar.slider("Amplitude (V peak)", 10, 400, 325, 5, key="3ph_v3_amp")
    v3_phase_deg = st.sidebar.slider("Phase (°)", -180, 180, 120, 5, key="3ph_v3_phase")

    st.sidebar.subheader("Phase 3 - Current")
    i3_waveform_type = st.sidebar.selectbox(
        "Waveform Type", 
        ["Sine", "Thyristor (SCR)", "Triac"],
        key="3ph_i3_type"
    )
    i3_amp = st.sidebar.slider(
        "Amplitude (A peak)", 0.1, 20.0, 14.14, 0.1, key="3ph_i3_amp"
    )
    if i3_waveform_type == "Sine":
        i3_phase_deg = st.sidebar.slider("Phase (°)", -180, 180, 120, 5, key="3ph_i3_phase")
    else:
        i3_firing_angle_deg = st.sidebar.slider(
            "Firing Angle (°)", 0, 180, 60, 5, key="3ph_i3_firing"
        )

    # Harmonics for three-phase
    st.sidebar.subheader("Harmonics")
    add_3ph_harmonics = st.sidebar.checkbox("Add Harmonics", key="3ph_harmonics")

    v1_harmonics_dict = None
    i1_harmonics_dict = None
    v2_harmonics_dict = None
    i2_harmonics_dict = None
    v3_harmonics_dict = None
    i3_harmonics_dict = None

    if add_3ph_harmonics:
        with st.sidebar.expander("Phase 1 Harmonics"):
            st.write("**Voltage Harmonics**")
            v1_harmonics_dict = {}
            for h in [3, 5, 7]:
                col1, col2 = st.columns(2)
                with col1:
                    v_h_pct = st.slider(f"V-H{h}%", 0, 30, 0, 1, key=f"3ph_v1_h{h}_pct")
                with col2:
                    v_h_phase = st.slider(
                        f"φ{h}°", -180, 180, 0, 15, key=f"3ph_v1_h{h}_ph"
                    )
                if v_h_pct > 0:
                    v1_harmonics_dict[h] = (v_h_pct / 100, np.radians(v_h_phase))

            st.write("**Current Harmonics**")
            i1_harmonics_dict = {}
            for h in [3, 5, 7]:
                col1, col2 = st.columns(2)
                with col1:
                    i_h_pct = st.slider(f"I-H{h}%", 0, 30, 0, 1, key=f"3ph_i1_h{h}_pct")
                with col2:
                    i_h_phase = st.slider(
                        f"φ{h}°", -180, 180, 0, 15, key=f"3ph_i1_h{h}_ph"
                    )
                if i_h_pct > 0:
                    i1_harmonics_dict[h] = (i_h_pct / 100, np.radians(i_h_phase))

        with st.sidebar.expander("Phase 2 Harmonics"):
            st.write("**Voltage Harmonics**")
            v2_harmonics_dict = {}
            for h in [3, 5, 7]:
                col1, col2 = st.columns(2)
                with col1:
                    v_h_pct = st.slider(f"V-H{h}%", 0, 30, 0, 1, key=f"3ph_v2_h{h}_pct")
                with col2:
                    v_h_phase = st.slider(
                        f"φ{h}°", -180, 180, 0, 15, key=f"3ph_v2_h{h}_ph"
                    )
                if v_h_pct > 0:
                    v2_harmonics_dict[h] = (v_h_pct / 100, np.radians(v_h_phase))

            st.write("**Current Harmonics**")
            i2_harmonics_dict = {}
            for h in [3, 5, 7]:
                col1, col2 = st.columns(2)
                with col1:
                    i_h_pct = st.slider(f"I-H{h}%", 0, 30, 0, 1, key=f"3ph_i2_h{h}_pct")
                with col2:
                    i_h_phase = st.slider(
                        f"φ{h}°", -180, 180, 0, 15, key=f"3ph_i2_h{h}_ph"
                    )
                if i_h_pct > 0:
                    i2_harmonics_dict[h] = (i_h_pct / 100, np.radians(i_h_phase))

        with st.sidebar.expander("Phase 3 Harmonics"):
            st.write("**Voltage Harmonics**")
            v3_harmonics_dict = {}
            for h in [3, 5, 7]:
                col1, col2 = st.columns(2)
                with col1:
                    v_h_pct = st.slider(f"V-H{h}%", 0, 30, 0, 1, key=f"3ph_v3_h{h}_pct")
                with col2:
                    v_h_phase = st.slider(
                        f"φ{h}°", -180, 180, 0, 15, key=f"3ph_v3_h{h}_ph"
                    )
                if v_h_pct > 0:
                    v3_harmonics_dict[h] = (v_h_pct / 100, np.radians(v_h_phase))

            st.write("**Current Harmonics**")
            i3_harmonics_dict = {}
            for h in [3, 5, 7]:
                col1, col2 = st.columns(2)
                with col1:
                    i_h_pct = st.slider(f"I-H{h}%", 0, 30, 0, 1, key=f"3ph_i3_h{h}_pct")
                with col2:
                    i_h_phase = st.slider(
                        f"φ{h}°", -180, 180, 0, 15, key=f"3ph_i3_h{h}_ph"
                    )
                if i_h_pct > 0:
                    i3_harmonics_dict[h] = (i_h_pct / 100, np.radians(i_h_phase))

    # Generate three-phase voltage signals
    t, v1_t = generate_sine(
        v1_amp,
        MAINS_FREQ,
        np.radians(v1_phase_deg),
        SAMPLING_FREQ,
        NUM_SAMPLES,
        v1_harmonics_dict,
    )
    _, v2_t = generate_sine(
        v2_amp,
        MAINS_FREQ,
        np.radians(v2_phase_deg),
        SAMPLING_FREQ,
        NUM_SAMPLES,
        v2_harmonics_dict,
    )
    _, v3_t = generate_sine(
        v3_amp,
        MAINS_FREQ,
        np.radians(v3_phase_deg),
        SAMPLING_FREQ,
        NUM_SAMPLES,
        v3_harmonics_dict,
    )

    # Generate three-phase current signals based on waveform type
    if i1_waveform_type == "Sine":
        _, i1_t = generate_sine(
            i1_amp,
            MAINS_FREQ,
            np.radians(i1_phase_deg),
            SAMPLING_FREQ,
            NUM_SAMPLES,
            i1_harmonics_dict,
        )
    elif i1_waveform_type == "Thyristor (SCR)":
        i1_t = generate_thyristor_current(
            v1_t, i1_amp, i1_firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )
    else:  # Triac
        i1_t = generate_triac_current(
            v1_t, i1_amp, i1_firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )
    
    if i2_waveform_type == "Sine":
        _, i2_t = generate_sine(
            i2_amp,
            MAINS_FREQ,
            np.radians(i2_phase_deg),
            SAMPLING_FREQ,
            NUM_SAMPLES,
            i2_harmonics_dict,
        )
    elif i2_waveform_type == "Thyristor (SCR)":
        i2_t = generate_thyristor_current(
            v2_t, i2_amp, i2_firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )
    else:  # Triac
        i2_t = generate_triac_current(
            v2_t, i2_amp, i2_firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )
    
    if i3_waveform_type == "Sine":
        _, i3_t = generate_sine(
            i3_amp,
            MAINS_FREQ,
            np.radians(i3_phase_deg),
            SAMPLING_FREQ,
            NUM_SAMPLES,
            i3_harmonics_dict,
        )
    elif i3_waveform_type == "Thyristor (SCR)":
        i3_t = generate_thyristor_current(
            v3_t, i3_amp, i3_firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )
    else:  # Triac
        i3_t = generate_triac_current(
            v3_t, i3_amp, i3_firing_angle_deg, SAMPLING_FREQ, MAINS_FREQ
        )

    # Calculate three-phase power metrics
    power_3ph = calculate_three_phase_power(v1_t, v2_t, v3_t, i1_t, i2_t, i3_t)

    # Display main metrics
    st.subheader("Three-Phase Power Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Active Power (Całk. moc czynna)", f"{power_3ph['P_total']:.2f} W"
        )
        st.metric("Phase 1 Power (Moc fazy 1)", f"{power_3ph['P1']:.2f} W")

    with col2:
        st.metric(
            "Total Apparent Power (Całk. moc pozorna)", f"{power_3ph['S_total']:.2f} VA"
        )
        st.metric("Phase 2 Power (Moc fazy 2)", f"{power_3ph['P2']:.2f} W")

    with col3:
        st.metric(
            "Total Reactive Power (Całk. moc bierna)", f"{power_3ph['Q_total']:.2f} VAR"
        )
        st.metric("Phase 3 Power (Moc fazy 3)", f"{power_3ph['P3']:.2f} W")

    with col4:
        st.metric("3-Phase PF", f"{power_3ph['PF_3ph']:.3f}")
        st.metric("Voltage Unbalance", f"{power_3ph['V_unbalance'] * 100:.2f}%")

    # Per-phase RMS values
    st.subheader("Per-Phase RMS Values (Wartości skuteczne na fazę)")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Phase 1 (Faza 1)**")
        st.write(f"- Voltage (Napięcie): {power_3ph['V1_rms']:.2f} V")
        st.write(f"- Current (Prąd): {power_3ph['I1_rms']:.2f} A")

    with col2:
        st.write("**Phase 2 (Faza 2)**")
        st.write(f"- Voltage (Napięcie): {power_3ph['V2_rms']:.2f} V")
        st.write(f"- Current (Prąd): {power_3ph['I2_rms']:.2f} A")

    with col3:
        st.write("**Phase 3 (Faza 3)**")
        st.write(f"- Voltage (Napięcie): {power_3ph['V3_rms']:.2f} V")
        st.write(f"- Current (Prąd): {power_3ph['I3_rms']:.2f} A")

    # Waveform plots
    st.subheader("Three-Phase Waveforms")

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            "Three-Phase Voltages",
            "Three-Phase Currents",
            "Instantaneous Power per Phase",
        ),
    )

    # Voltages
    colors_v = ["blue", "green", "red"]
    for v, name, color in zip([v1_t, v2_t, v3_t], ["V1", "V2", "V3"], colors_v):
        fig.add_trace(
            go.Scatter(
                x=t * 1000, y=v, mode="lines", name=name, line=dict(color=color)
            ),
            row=1,
            col=1,
        )

    # Currents
    colors_i = ["darkblue", "darkgreen", "darkred"]
    for i, name, color in zip([i1_t, i2_t, i3_t], ["I1", "I2", "I3"], colors_i):
        fig.add_trace(
            go.Scatter(
                x=t * 1000, y=i, mode="lines", name=name, line=dict(color=color)
            ),
            row=2,
            col=1,
        )

    # Instantaneous Power
    colors_p = ["cyan", "lime", "orange"]
    for p, name, color in zip(
        [power_3ph["p1_t"], power_3ph["p2_t"], power_3ph["p3_t"]],
        ["P1(t)", "P2(t)", "P3(t)"],
        colors_p,
    ):
        fig.add_trace(
            go.Scatter(
                x=t * 1000, y=p, mode="lines", name=name, line=dict(color=color)
            ),
            row=3,
            col=1,
        )

    # Total average power line
    fig.add_trace(
        go.Scatter(
            x=t * 1000,
            y=[power_3ph["P_total"]] * len(t),
            mode="lines",
            name=f"P_total_avg = {power_3ph['P_total']:.2f}W",
            line=dict(color="black", dash="dash", width=2),
        ),
        row=3,
        col=1,
    )

    fig.update_xaxes(title_text="Time (ms)", row=3, col=1)
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=2, col=1)
    fig.update_yaxes(title_text="Power (W)", row=3, col=1)

    fig.update_layout(height=800, showlegend=True)
    st.plotly_chart(fig, width="stretch")

    # Advanced metrics
    st.subheader("📊 Advanced Three-Phase Metrics")

    # Sequence components
    v1_harmonics_phase = analyze_harmonics_with_phase(v1_t, SAMPLING_FREQ, MAINS_FREQ)
    v2_harmonics_phase = analyze_harmonics_with_phase(v2_t, SAMPLING_FREQ, MAINS_FREQ)
    v3_harmonics_phase = analyze_harmonics_with_phase(v3_t, SAMPLING_FREQ, MAINS_FREQ)

    v1_1_amp, v1_1_phase = v1_harmonics_phase[1]
    v2_1_amp, v2_1_phase = v2_harmonics_phase[1]
    v3_1_amp, v3_1_phase = v3_harmonics_phase[1]

    v1_1_rms = v1_1_amp / np.sqrt(2)
    v2_1_rms = v2_1_amp / np.sqrt(2)
    v3_1_rms = v3_1_amp / np.sqrt(2)

    seq = calculate_sequence_components(
        v1_1_rms, v2_1_rms, v3_1_rms, v1_1_phase, v2_1_phase, v3_1_phase
    )

    st.subheader("Symmetrical Components (Składowe symetryczne) - Fundamental")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Sequence Magnitudes (Wielkości składowych)**")
        st.write(f"- Positive (Zgodna): {seq['V_pos']:.2f} V")
        st.write(f"- Negative (Przeciwna): {seq['V_neg']:.2f} V")
        st.write(f"- Zero (Zerowa): {seq['V0']:.2f} V")

    with col2:
        st.write("**Unbalance Factors (Wsp. niezrównoważenia)**")
        st.write(f"- VUF (V-/V+): {seq['VUF'] * 100:.2f}%")
        st.write(f"- V0/V+: {seq['V0_factor'] * 100:.2f}%")

    with col3:
        st.write("**System Status (Stan systemu)**")
        if seq["VUF"] < 0.02:
            st.write("✅ Well balanced (Dobrze zrównoważony)")
        elif seq["VUF"] < 0.05:
            st.write("⚠️ Acceptable unbalance (Dopuszczalne)")
        else:
            st.write("❌ Excessive unbalance (Nadmierne)")

    # Three-phase CPC decomposition
    st.subheader("Three-Phase Czarnecki CPC Decomposition (Dekompozycja CPC 3-fazowa)")

    cpc_3ph = calculate_three_phase_cpc(
        v1_t, v2_t, v3_t, i1_t, i2_t, i3_t, SAMPLING_FREQ, MAINS_FREQ
    )

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Total Current Components (RMS) - Całkowite składowe prądu**")
        st.write(
            f"Active (Czynny): {cpc_3ph['I_a_total']:.3f} A ({cpc_3ph['lambda_a'] * 100:.1f}%)"
        )
        st.write(
            f"Reactive (Bierny): {cpc_3ph['I_r_total']:.3f} A ({cpc_3ph['lambda_r'] * 100:.1f}%)"
        )
        st.write(
            f"Scattered (Rozrzutu): {cpc_3ph['I_s_total']:.3f} A ({cpc_3ph['lambda_s'] * 100:.1f}%)"
        )
        st.write(
            f"Unbalance (Niezrównoważenia): {cpc_3ph['I_u_total']:.3f} A ({cpc_3ph['lambda_u'] * 100:.1f}%)"
        )
        st.write(
            f"Generated (Generowany): {cpc_3ph['I_g_total']:.3f} A ({cpc_3ph['lambda_g'] * 100:.1f}%)"
        )
        st.write(f"**Total (Całkowity): {cpc_3ph['I_rms_total']:.3f} A**")

    with col2:
        st.write("**Total Power Components (Całkowite składowe mocy)**")
        st.write(f"Active Power (Moc czynna): {cpc_3ph['P_total']:.2f} W")
        st.write(f"Reactive Power (Moc bierna): {cpc_3ph['Q1_total']:.2f} VAR")
        st.write(f"Scattered Power (Moc rozrzutu): {cpc_3ph['D_s_total']:.2f} VA")
        st.write(
            f"Unbalance Power (Moc niezrównoważenia): {cpc_3ph['D_u_total']:.2f} VA"
        )
        st.write(f"Generated Power (Moc generowana): {cpc_3ph['D_g_total']:.2f} VA")
        st.write(f"**Apparent Power (Moc pozorna): {cpc_3ph['S_total']:.2f} VA**")

    # Per-phase CPC breakdown
    with st.expander("Per-Phase CPC Breakdown"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**Phase 1 CPC**")
            cpc_1 = cpc_3ph["cpc_1"]
            st.write(f"- I_a: {cpc_1['I_a']:.3f} A")
            st.write(f"- I_r: {cpc_1['I_r']:.3f} A")
            st.write(f"- I_s: {cpc_1['I_s']:.3f} A")
            st.write(f"- I_g: {cpc_1['I_g']:.3f} A")

        with col2:
            st.write("**Phase 2 CPC**")
            cpc_2 = cpc_3ph["cpc_2"]
            st.write(f"- I_a: {cpc_2['I_a']:.3f} A")
            st.write(f"- I_r: {cpc_2['I_r']:.3f} A")
            st.write(f"- I_s: {cpc_2['I_s']:.3f} A")
            st.write(f"- I_g: {cpc_2['I_g']:.3f} A")

        with col3:
            st.write("**Phase 3 CPC**")
            cpc_3 = cpc_3ph["cpc_3"]
            st.write(f"- I_a: {cpc_3['I_a']:.3f} A")
            st.write(f"- I_r: {cpc_3['I_r']:.3f} A")
            st.write(f"- I_s: {cpc_3['I_s']:.3f} A")
            st.write(f"- I_g: {cpc_3['I_g']:.3f} A")

    # Harmonic analysis per phase
    st.subheader("Per-Phase Harmonic Analysis (First 10)")

    i1_harmonics = analyze_harmonics(i1_t, SAMPLING_FREQ, MAINS_FREQ)
    i2_harmonics = analyze_harmonics(i2_t, SAMPLING_FREQ, MAINS_FREQ)
    i3_harmonics = analyze_harmonics(i3_t, SAMPLING_FREQ, MAINS_FREQ)

    harmonic_data = []
    for h in range(1, 11):
        harmonic_data.append(
            {
                "H": h,
                "V1 (V)": f"{v1_harmonics_phase[h][0]:.2f}",
                "V2 (V)": f"{v2_harmonics_phase[h][0]:.2f}",
                "V3 (V)": f"{v3_harmonics_phase[h][0]:.2f}",
                "I1 (A)": f"{i1_harmonics[h]:.3f}",
                "I2 (A)": f"{i2_harmonics[h]:.3f}",
                "I3 (A)": f"{i3_harmonics[h]:.3f}",
            }
        )

    st.table(harmonic_data)


def main():
    """Main Streamlit application"""
    st.set_page_config(page_title="Power Analysis Playground", layout="wide")
    st.title("Power Analysis Playground")

    # Use session state to track active tab
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Single Phase"

    # Tab selection
    selected_tab = st.radio(
        "Select Analysis Mode:",
        ["Single Phase", "Three Phase"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.session_state.active_tab = selected_tab

    # Render appropriate tab
    if selected_tab == "Single Phase":
        render_single_phase_tab()
    else:
        render_three_phase_tab()


if __name__ == "__main__":
    main()
