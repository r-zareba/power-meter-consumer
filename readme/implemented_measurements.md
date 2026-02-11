# Implemented Power Quality Measurements

## Overview

The system performs comprehensive power quality analysis compliant with **IEC 61000-4-7**, **IEC 61000-4-30 Class A**, and **IEEE 519** standards.

---

## 200ms Measurements (PowerMeasurement)

Every 200ms window (2048 samples @ 10.24 kHz) contains:

### Basic Power Metrics
- **v_rms** - RMS voltage (V). True RMS calculated from waveform samples.
- **i_rms** - RMS current (A). True RMS calculated from waveform samples.
- **P** - Active power (W). Real power doing useful work.
- **Q** - Reactive power (VAR). Power oscillating between source and load.
- **S** - Apparent power (VA). Total power = √(P² + Q²).
- **PF** - Power factor (dimensionless). Efficiency metric = P/S, includes both displacement and distortion effects.

### Harmonic Distortion
- **v_thd** - Voltage Total Harmonic Distortion (%). Measure of voltage waveform purity.
- **i_thd** - Current Total Harmonic Distortion (%). Measure of current waveform purity.
- **v_harmonics** - Voltage harmonics 1-50 with amplitude and phase. Individual frequency components.
- **i_harmonics** - Current harmonics 1-50 with amplitude and phase. Individual frequency components.

### Fundamental Component
- **v1_amp** - Fundamental voltage amplitude (V). 50Hz component only.
- **i1_amp** - Fundamental current amplitude (A). 50Hz component only.
- **phase_diff_deg** - Phase difference between V and I (degrees). Positive = voltage leads current.
- **DPF** - Displacement Power Factor (dimensionless). Power factor due to fundamental phase shift only = cos(φ).

### Power Quality Indicators
- **frequency** - Measured frequency (Hz). Zero-crossing detection per IEC 61000-4-30.
- **crest_factor_v** - Voltage crest factor (dimensionless). V_peak / V_rms, indicates waveform peakiness.
- **crest_factor_i** - Current crest factor (dimensionless). I_peak / I_rms, high values indicate nonlinear loads.
- **voltage_deviation_pct** - Voltage deviation from nominal (%). (V_rms - 230V) / 230V × 100.

### CPC (Currents' Physical Components) - Czarnecki Theory
Advanced decomposition identifying power quality degradation causes:

- **cpc_distortion_factor** - Distortion factor DF (dimensionless). Reduction in power factor due to harmonics.
- **cpc_active_current** - Active current I_a (A). Current component delivering active power.
- **cpc_reactive_current** - Reactive current I_r (A). Current component delivering reactive power (fundamental).
- **cpc_scattered_current** - Scattered current I_s (A). Current caused by voltage harmonics (grid's fault).
- **cpc_generated_current** - Generated current I_g (A). Current caused by load nonlinearity (load's fault).
- **cpc_active_ratio** - λ_a (dimensionless). Ratio I_a/I_rms, shows active current contribution.
- **cpc_reactive_ratio** - λ_r (dimensionless). Ratio I_r/I_rms, shows reactive current contribution.
- **cpc_scattered_ratio** - λ_s (dimensionless). Ratio I_s/I_rms, shows grid pollution impact.
- **cpc_generated_ratio** - λ_g (dimensionless). Ratio I_g/I_rms, shows load pollution impact.
- **cpc_reactive_power** - Q1 (VAR). Fundamental reactive power (different from total Q which includes harmonics).
- **cpc_scattered_power** - D_s (VA). Distortion power caused by grid voltage harmonics.
- **cpc_generated_power** - D_g (VA). Distortion power caused by load current harmonics.

### IEEE 519 Harmonic Responsibility
- **harmonic_power_flow** - Per-harmonic active power (W) for h=1-50. Positive = grid sources harmonic, negative = load sources harmonic.

---

## 1-Second Aggregates (AggregateMessage)

Published via MQTT every second (5 × 200ms measurements):

### Statistical Aggregates (avg/min/max/std)
- **v_rms** - Voltage statistics over 1 second.
- **i_rms** - Current statistics over 1 second.
- **P** - Active power statistics over 1 second.
- **Q** - Reactive power statistics over 1 second.
- **S** - Apparent power statistics over 1 second.
- **PF** - Power factor statistics over 1 second.
- **v_thd** - Voltage THD statistics (avg/max only).
- **i_thd** - Current THD statistics (avg/max only).

### Averaged Single Values
- **phase_diff_deg_avg** - Average phase difference over 1 second.
- **DPF_avg** - Average displacement power factor over 1 second.
- **cpc_active_current_avg** - Average active current over 1 second.
- **cpc_reactive_current_avg** - Average reactive current over 1 second.
- **frequency_avg** - Average frequency over 1 second.

### Energy Metrics (1-Second Intervals)
- **energy_wh** - Active energy consumed in this 1-second (Wh). P_avg / 3600, for time-series accumulation.
- **energy_varh** - Reactive energy consumed in this 1-second (VARh). Q_avg / 3600, for time-series accumulation.
- **energy_vah** - Apparent energy consumed in this 1-second (VAh). S_avg / 3600, for time-series accumulation.

### Harmonic Pollution Summary
- **harmonics_grid_sourced_w** - Total harmonic power from grid (W). Sum of positive P_h for h≥2, averaged over 5 measurements.
- **harmonics_load_sourced_w** - Total harmonic power from load (W). Sum of |negative P_h| for h≥2, averaged over 5 measurements.

---

## Standards Compliance

- **IEC 61000-4-7**: Harmonic measurement methodology (200ms windows, 50 harmonics)
- **IEC 61000-4-30 Class A**: Power quality measurement (frequency, voltage, harmonics)
- **IEEE 519**: Harmonic responsibility determination (power flow direction)
- **Czarnecki CPC Theory**: Advanced power quality decomposition (scattered vs generated distortion)

---

## Data Flow

```
ADC Samples (10.24 kHz)
    ↓
200ms Window (2048 samples)
    ↓
PowerMeasurement (31 metrics + 100 harmonics)
    ↓ (stored in SQLite)
    ↓
5 × PowerMeasurement
    ↓ (aggregated)
    ↓
AggregateMessage (1 second)
    ↓ (published via MQTT)
    ↓
TimeSeries DB
```

---

