"""
Simulator Configuration

Define voltage and current waveform parameters for STM32 simulator.
All values are in Volts at ADC input (0-3.3V range).

DC bias for both channels: 1.65V (VCC/2)
"""

# DC bias for AC signals (VCC/2)
DC_BIAS = 1.65  # V

# WAVEFORM CONFIGURATION
# Voltage channel configuration (ADC1, PA0)
VOLTAGE = {
    "rms": 1.0,  # V RMS at ADC input
    # Harmonic amplitudes (fraction of fundamental, 0.0-1.0)
    "harmonic_3": 0.1,
    "harmonic_5": 0.05,
    "harmonic_7": 0.01,
    "harmonic_9": 0.0,
    "harmonic_11": 0.0,
    "harmonic_13": 0.0,
    "harmonic_15": 0.0,
    "harmonic_17": 0.0,
    # Harmonic phase shifts in degrees (relative to fundamental)
    "harmonic_3_phase": 0.0,
    "harmonic_5_phase": 0.0,
    "harmonic_7_phase": 0.0,
    "harmonic_9_phase": 0.0,
    "harmonic_11_phase": 0.0,
    "harmonic_13_phase": 0.0,
    "harmonic_15_phase": 0.0,
    "harmonic_17_phase": 0.0,
}

# Current channel configuration (ADC2, PC0)
CURRENT = {
    "rms": 0.50,  # V RMS at ADC input
    "phase_shift": 0.0,  # Fundamental phase shift in degrees (negative = lag, positive = lead)
    # Harmonic amplitudes (fraction of fundamental, 0.0-1.0)
    "harmonic_3": 0.3,
    "harmonic_5": 0.1,
    "harmonic_7": 0.0,
    "harmonic_9": 0.0,
    "harmonic_11": 0.0,
    "harmonic_13": 0.0,
    "harmonic_15": 0.0,
    "harmonic_17": 0.0,
    # Harmonic phase shifts in degrees (relative to current fundamental)
    "harmonic_3_phase": -30.0,
    "harmonic_5_phase": 0.0,
    "harmonic_7_phase": 0.0,
    "harmonic_9_phase": 0.0,
    "harmonic_11_phase": 0.0,
    "harmonic_13_phase": 0.0,
    "harmonic_15_phase": 0.0,
    "harmonic_17_phase": 0.0,
}


# ============================================================================
# CONFIGURATION PRESETS (uncomment one to use)
# ============================================================================

# # PRESET 1: Resistive Load (Unity Power Factor)
# # Pure resistive load like incandescent bulb or heater
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37
# CURRENT["phase_shift"] = 0.0  # In phase with voltage
# # All harmonics = 0 (clean sine wave)

# # PRESET 2: Inductive Load (Lagging Power Factor)
# # Typical motor or transformer
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37
# CURRENT["phase_shift"] = -30.0  # Current lags voltage by 30°
# # Expected PF: ~0.87

# # PRESET 3: Capacitive Load (Leading Power Factor)
# # Power factor correction capacitor
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37
# CURRENT["phase_shift"] = 30.0  # Current leads voltage by 30°
# # Expected PF: ~0.87

# # PRESET 4: Non-linear Load (Switch-mode PSU / LED Driver)
# # Significant harmonic distortion
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37
# CURRENT["phase_shift"] = 0.0
# CURRENT["harmonic_3"] = 0.20  # 20% 3rd harmonic
# CURRENT["harmonic_5"] = 0.10  # 10% 5th harmonic
# CURRENT["harmonic_3_phase"] = 45.0  # 3rd harmonic leads by 45°
# CURRENT["harmonic_5_phase"] = -30.0  # 5th harmonic lags by 30°
# # Expected THD: ~22%

# # PRESET 5: Low Power Load
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.05
# CURRENT["phase_shift"] = 0.0

# # PRESET 6: Complex Harmonic Distortion (Real-world scenario)
# # Represents realistic power converter with phase-shifted harmonics
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37
# CURRENT["phase_shift"] = -15.0  # Slightly inductive
# CURRENT["harmonic_3"] = 0.15
# CURRENT["harmonic_3_phase"] = 60.0
# CURRENT["harmonic_5"] = 0.08
# CURRENT["harmonic_5_phase"] = -45.0
# CURRENT["harmonic_7"] = 0.05
# CURRENT["harmonic_7_phase"] = 90.0
