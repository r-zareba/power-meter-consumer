"""
Simulator Configuration

Define voltage and current waveform parameters for STM32 simulator.
All voltage/current values are in sensor output units (Volts at ADC input).

Sensor configuration is imported from src/config.py (global project config).

For real-world mapping:
- ZMPT101B: 230V AC mains → ~1.0V RMS at sensor output
- ACS712-05B: 2A AC current → 0.37V RMS at sensor output (0.185 V/A sensitivity)
"""

# WAVEFORM CONFIGURATION
# Voltage channel configuration (ADC1, PA0)
VOLTAGE = {
    "rms": 1.0,  # V RMS at sensor output (corresponds to ~230V mains)
    "harmonic_3": 0.0,  # 3rd harmonic amplitude (fraction of fundamental, 0.0-1.0)
    "harmonic_5": 0.0,  # 5th harmonic
    "harmonic_7": 0.0,  # 7th harmonic
    "harmonic_9": 0.0,  # 9th harmonic
    "harmonic_11": 0.0,  # 11th harmonic
    "harmonic_13": 0.0,  # 13th harmonic
    "harmonic_15": 0.0,  # 15th harmonic
    "harmonic_17": 0.0,  # 17th harmonic
}

# Current channel configuration (ADC2, PA1)
CURRENT = {
    "rms": 0.37,  # V RMS at sensor output (corresponds to ~2A at 0.185 V/A)
    "phase_shift": 0.0,  # Phase shift in degrees (negative = lag, positive = lead)
    "harmonic_3": 0.0,  # 3rd harmonic amplitude (fraction of fundamental)
    "harmonic_5": 0.0,  # 5th harmonic
    "harmonic_7": 0.0,  # 7th harmonic
    "harmonic_9": 0.0,  # 9th harmonic
    "harmonic_11": 0.0,  # 11th harmonic
    "harmonic_13": 0.0,  # 13th harmonic
    "harmonic_15": 0.0,  # 15th harmonic
    "harmonic_17": 0.0,  # 17th harmonic
}


# ============================================================================
# CONFIGURATION PRESETS (uncomment one to use)
# ============================================================================

# # PRESET 1: Resistive Load (Unity Power Factor)
# # Pure resistive load like incandescent bulb or heater
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37  # 2A at 0.185 V/A
# CURRENT["phase_shift"] = 0.0  # In phase with voltage
# # All harmonics = 0 (clean sine wave)

# # PRESET 2: Inductive Load (Lagging Power Factor)
# # Typical motor or transformer
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37  # 2A
# CURRENT["phase_shift"] = -30.0  # Current lags voltage by 30°
# # Expected PF: ~0.87

# # PRESET 3: Capacitive Load (Leading Power Factor)
# # Power factor correction capacitor
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37  # 2A
# CURRENT["phase_shift"] = 30.0  # Current leads voltage by 30°
# # Expected PF: ~0.87

# # PRESET 4: Non-linear Load (Switch-mode PSU / LED Driver)
# # Significant harmonic distortion
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.37  # 2A
# CURRENT["phase_shift"] = 0.0
# CURRENT["harmonic_3"] = 0.20  # 20% 3rd harmonic
# CURRENT["harmonic_5"] = 0.10  # 10% 5th harmonic
# # Expected THD: ~22%

# # PRESET 5: Low Power Load
# # Tests sensor resolution at low currents
# VOLTAGE["rms"] = 1.0
# CURRENT["rms"] = 0.0185  # 0.1A at 0.185 V/A
# CURRENT["phase_shift"] = 0.0

# # PRESET 6: Custom Sensor - ACS712-20A (higher current range)
# # PRESET 6: Custom Sensor - ACS712-20A (higher current range)
# # Uncomment to test with 20A sensor instead of 5A
# # NOTE: To change globally for receiver too, edit src/config.py instead
# CURRENT_SENSOR["name"] = "ACS712-20A"
# CURRENT_SENSOR["sensitivity"] = 0.100  # 100 mV/A
# CURRENT_SENSOR["max_current"] = 20.0
# CURRENT["rms"] = 0.200  # 2A at 0.100 V/A = 0.2V RMS

# # PRESET 7: Custom Sensor - ACS712-30A (even higher range)
# # NOTE: To change globally for receiver too, edit src/config.py instead
# CURRENT_SENSOR["name"] = "ACS712-30A"
# CURRENT_SENSOR["sensitivity"] = 0.066  # 66 mV/A
# CURRENT_SENSOR["max_current"] = 30.0
# CURRENT["rms"] = 0.132  # 2A at 0.066 V/A = 0.132V RMS

# # PRESET 8: Different Voltage Sensor Scaling
# # Example: custom voltage sensor with different ratio
# # NOTE: To change globally for receiver too, edit src/config.py instead
# VOLTAGE_SENSOR["scaling_factor"] = 0.01  # 2.3V output for 230V input
# VOLTAGE["rms"] = 2.3
