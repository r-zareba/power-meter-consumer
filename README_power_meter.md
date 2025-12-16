# Power Meter - Industry Standard Specifications

## Overview
This document outlines the measurements, metrics, and standards for building an accurate, industry-standard power analyzer comparable to commercial units like Fluke 435, Hioki PW3198, or Dranetz HDPQ. It covers both single-phase and three-phase measurement scenarios with IEC and IEEE compliance requirements.

---

## 1. Single-Phase Power Measurements

### 1.1 Basic Electrical Measurements (IEC 61000-4-30 Class A/S)

**RMS Values:**
- Voltage RMS (V_rms) - True RMS calculation, 200ms windows
- Current RMS (I_rms) - True RMS calculation, 200ms windows
- Continuous measurement with 10-minute aggregation periods

**Power Components:**
- Active Power (P) - Real power in Watts (W) - actual energy consumption
- Reactive Power (Q) - Reactive power in Volt-Amperes Reactive (VAR) - oscillating energy
- Apparent Power (S) - Total power in Volt-Amperes (VA) - vector sum of P and Q
- Complex Power decomposition showing relationship between components

**Frequency Tracking:**
- Grid frequency measurement (nominal 50Hz or 60Hz)
- Continuous monitoring with ±0.01 Hz accuracy
- Frequency deviation detection and logging

### 1.2 Power Quality Indices

**Power Factor Metrics:**
- Total Power Factor (PF) - Overall efficiency ratio P/S
- Displacement Power Factor (DPF) - Fundamental frequency phase shift only, cos(φ₁)
- Distortion Factor (DF) - Impact of harmonics on current waveform
- Relationship: PF = DPF × DF

**Waveform Quality:**
- Crest Factor for voltage - Peak/RMS ratio indicating waveform peaking
- Crest Factor for current - Detects non-linear load characteristics
- Form Factor - RMS/Average ratio for waveform distortion assessment

**Advanced Quality Metrics:**
- K-Factor - Transformer derating factor for harmonic heating
- Total Demand Distortion (TDD) - IEEE 519 compliance metric
- Short-term flicker severity (Pst) - IEC 61000-4-15
- Long-term flicker severity (Plt) - 2-hour sliding window

### 1.3 Harmonic Analysis (IEC 61000-4-7)

**Measurement Window:**
- 200ms duration (10 cycles at 50Hz, 12 cycles at 60Hz)
- Ensures stable frequency resolution
- IEC 61000-4-7 compliant rectangular window

**Individual Harmonics (H1-H50):**
- Voltage harmonic amplitudes - magnitude in Volts or % of fundamental
- Current harmonic amplitudes - magnitude in Amperes or % of fundamental
- Phase angles for each harmonic - advanced diagnostic capability
- Harmonic power contribution - active and reactive power per harmonic

**Total Harmonic Distortion:**
- THD-V (Voltage) - Measure of voltage waveform distortion
- THD-I (Current) - Measure of current waveform distortion
- Subgroup harmonics (optional) - IEC 61000-4-7 interharmonics
- Even harmonics tracking - indicates DC component or asymmetry

**Harmonic Compliance:**
- IEEE 519 individual harmonic limits verification
- IEC 61000-3-2 compliance for equipment < 16A per phase
- Harmonic spectrum visualization up to 50th order

### 1.4 Czarnecki Current Physical Components (CPC Theory)

**Current Decomposition:**
- Active Current (I_a) - Contributes to real power transfer
- Reactive Current (I_r) - Fundamental frequency reactive component
- Scattered Current (I_s) - Caused by voltage harmonics (supply distortion)
- Generated Current (I_g) - Caused by current harmonics (load distortion)

**Power Decomposition:**
- Active Power (P) - Useful power
- Fundamental Reactive Power (Q₁) - Traditional reactive power
- Scattered Distortion Power (D_s) - Due to supply voltage distortion
- Generated Distortion Power (D_g) - Due to load current distortion

**Diagnostic Applications:**
- Identify responsibility for power quality issues (supply vs. load)
- Design appropriate compensation strategies
- Advanced power quality assessment beyond traditional metrics

### 1.5 Voltage Events and Transients

**Voltage Variations:**
- Sag events - RMS voltage drop >10% for 0.5 cycle to 1 minute
- Swell events - RMS voltage rise >10% for 0.5 cycle to 1 minute
- Interruption - Complete voltage loss >90% reduction
- Undervoltage - Long-duration voltage below 90% nominal
- Overvoltage - Long-duration voltage above 110% nominal

**Event Characterization:**
- Event magnitude in % or Volts
- Event duration with cycle-level precision
- Time and date stamping
- Pre-event and post-event waveform capture
- Residual voltage during sags

**Transient Detection:**
- High-speed sampling for transient capture
- Voltage spike detection
- Oscillatory transient detection
- Impulsive transient detection

### 1.6 Energy Accumulation

**Cumulative Energy:**
- Active Energy Import (kWh) - Energy consumed from grid
- Active Energy Export (kWh) - Energy delivered to grid (if applicable)
- Reactive Energy Import (kVArh) - Inductive reactive energy
- Reactive Energy Export (kVArh) - Capacitive reactive energy
- Apparent Energy (kVAh) - Total energy demand

**Energy Tariffs:**
- Time-of-use energy tracking
- Peak, off-peak, and shoulder period accumulation
- Demand interval energy (typically 15-minute blocks)
- Maximum demand tracking with timestamp

---

## 2. Three-Phase Power Measurements

### 2.1 Per-Phase Measurements

**Individual Phase Monitoring:**
- Phase 1 (L1), Phase 2 (L2), Phase 3 (L3) voltage RMS
- Phase 1, Phase 2, Phase 3 current RMS
- Active, reactive, and apparent power per phase
- Power factor per phase
- THD-V and THD-I per phase
- Harmonic spectrum (H1-H50) per phase

**Phase Relationships:**
- Phase-to-phase voltages (V12, V23, V31)
- Phase-to-neutral voltages (V1N, V2N, V3N)
- Neutral current magnitude and distortion
- Phase angle between voltage and current per phase

### 2.2 System-Wide Three-Phase Metrics

**Total Power:**
- Total Active Power (P_total) - Sum of all three phases
- Total Reactive Power (Q_total) - Vector or arithmetic sum
- Total Apparent Power (S_total) - Correct three-phase apparent power
- Three-phase Power Factor - Overall system efficiency

**System Configuration:**
- Wye (Star) or Delta connection detection
- Four-wire (3P+N) or three-wire (3P) system
- Neutral-to-ground voltage monitoring
- Ground fault detection capability

### 2.3 Symmetrical Components (Fortescue Analysis)

**Sequence Components:**
- Positive Sequence Voltage (V₊) - Balanced forward-rotating component
- Negative Sequence Voltage (V₋) - Unbalance backward-rotating component
- Zero Sequence Voltage (V₀) - Common-mode component
- Positive, negative, zero sequence currents (I₊, I₋, I₀)

**Unbalance Factors:**
- Voltage Unbalance Factor (VUF) - Ratio V₋/V₊, typically as percentage
- Current Unbalance Factor - Ratio I₋/I₊
- IEC/NEMA unbalance definition compliance
- Zero sequence percentage indicating neutral current issues

**Unbalance Effects:**
- Equipment derating factors
- Motor overheating risk assessment
- Transformer neutral overload detection
- Cable sizing verification for neutral conductor

### 2.4 Three-Phase Czarnecki CPC Theory

**Per-Phase Current Components:**
- Active, reactive, scattered, and generated currents calculated per phase
- Aggregated three-phase current components using vector summation

**Unbalance Current Component (I_u):**
- Additional current component unique to three-phase systems
- Represents current due to voltage asymmetry between phases
- Distinct from other harmonic or reactive components
- Critical for identifying supply-side unbalance issues

**Three-Phase Power Decomposition:**
- Total active power across all phases
- Fundamental reactive power (traditional Q)
- Scattered distortion power (voltage harmonics effect)
- Unbalance distortion power (unique to 3-phase)
- Generated distortion power (load-generated harmonics)

**Diagnostic Capabilities:**
- Identify phase-specific vs. system-wide issues
- Determine if problems originate from supply or loads
- Design phase-specific or system compensation
- Assess neutral conductor loading

### 2.5 Three-Phase Harmonic Analysis

**Per-Phase Harmonics:**
- Individual harmonic magnitudes and phases for each phase
- THD per phase for voltage and current
- Phase-specific harmonic compliance verification

**Triplen Harmonics:**
- 3rd, 9th, 15th, 21st harmonic monitoring
- Neutral current contribution from triplen harmonics
- Zero-sequence harmonic magnitudes
- Neutral-to-ground voltage harmonics

**Interharmonic Analysis:**
- Non-integer harmonics between fundamental harmonics
- Caused by variable frequency drives, arc furnaces
- IEC 61000-4-7 subgroup and interharmonic measurement

### 2.6 Three-Phase Energy and Demand

**Three-Phase Energy:**
- Total import/export active energy across all phases
- Per-phase energy tracking for unbalanced loads
- Four-quadrant energy metering (import/export, inductive/capacitive)
- Neutral current energy losses

**Demand Measurement:**
- Peak demand tracking (typically 15-minute intervals)
- Average demand over billing period
- Predictive demand monitoring
- Load profile recording

---

## 3. Time-Domain Statistics and Trending

### Statistical Analysis

**Per Measurement Window (200ms):**
- Minimum, maximum, and average values
- Standard deviation for stability assessment
- Peak-to-peak variation

**Aggregated Statistics (10-minute intervals):**
- 95th percentile values - IEC 61000-4-30 requirement
- 99th percentile for extreme value analysis
- Mean and median values
- Statistical probability distributions

**Trending Capabilities:**
- Hour-by-hour daily profiles
- Day-by-day weekly profiles
- Week-by-week monthly profiles
- Long-term trending for seasonal analysis
- Load curve generation

---

## 4. Data Logging and Time Windows

### Measurement Time Bases

**Real-Time Measurements:**
- 200ms windows (IEC 61000-4-7 and IEC 61000-4-30 compliant)
- Cycle-by-cycle analysis for fast transients
- High-resolution waveform capture during events

**Short-Term Aggregation:**
- 3-second intervals (15 × 200ms windows)
- 10-second intervals for rapid monitoring
- 1-minute averages for trending

**Standard Logging Intervals:**
- 10-minute aggregation (IEC 61000-4-30 standard)
- 15-minute demand intervals (billing standard)
- Hourly summaries
- Daily, weekly, monthly reports

### Event Logging

**Event Triggers:**
- Voltage threshold violations (sag/swell/interruption)
- Current threshold violations (overload)
- THD limit exceedance
- Frequency deviation
- Power factor below threshold
- Unbalance exceeding limits

**Event Data Capture:**
- Pre-trigger waveform capture
- Event waveform recording
- Post-trigger waveform capture
- Event characterization (magnitude, duration)
- Time and date stamping with millisecond precision
- Event counter and statistics

---

## 5. Implementation Priority for Power Analyzer

### Tier 1: Essential Measurements (Basic Compliance)

**Single-Phase:**
- RMS voltage and current
- Active power (P), reactive power (Q), apparent power (S)
- Power factor (PF)
- Frequency tracking
- Energy accumulation (kWh, kVArh)

**Three-Phase:**
- Per-phase RMS voltage and current
- Per-phase and total power (P, Q, S)
- Three-phase power factor
- Phase sequence detection
- Three-phase energy accumulation

### Tier 2: Power Quality Standards (IEC/IEEE Compliance)

**Single-Phase:**
- THD-V and THD-I
- Individual harmonics H1-H50 (magnitude)
- Crest factor
- Voltage event detection (sag/swell/interruption)
- 10-minute aggregation

**Three-Phase:**
- Per-phase THD and harmonics
- Symmetrical components (V₊, V₋, V₀)
- Voltage unbalance factor (VUF)
- Neutral current monitoring
- Three-phase voltage events

### Tier 3: Advanced Diagnostics (Professional Features)

**Single-Phase:**
- Harmonic phase angles
- Czarnecki CPC decomposition (I_a, I_r, I_s, I_g)
- Displacement and distortion power factors
- K-factor calculation
- TDD calculation
- Per-harmonic power analysis

**Three-Phase:**
- Current unbalance factor
- Czarnecki three-phase CPC with unbalance current (I_u)
- Per-phase CPC decomposition
- Triplen harmonic analysis
- Interharmonic measurement
- Sequence impedance calculation

### Tier 4: Research and Special Applications

**Advanced Features:**
- Flicker severity (Pst, Plt)
- Transient capture and analysis
- Sub-cycle analysis
- Custom harmonic groupings
- Load signature analysis
- Predictive analytics

---

## 6. Applicable International Standards

### IEC 61000-4-7: Harmonic and Interharmonic Measurements
**Scope:**
- Testing and measurement techniques for harmonics and interharmonics
- 200ms measurement window (10 cycles at 50Hz, 12 cycles at 60Hz)
- Rectangular window FFT processing
- Harmonic grouping and subgrouping definitions
- Up to 50th harmonic measurement
- Interharmonic measurement requirements

**Key Requirements:**
- 5Hz frequency resolution minimum
- Class I and Class II instrument specifications
- Measurement bandwidth and accuracy specifications
- Aggregation algorithms for time-varying harmonics

### IEC 61000-4-30: Power Quality Measurement Methods
**Class A (Highest Accuracy):**
- Precision instruments for legal/contractual applications
- Stringent accuracy requirements for all parameters
- Mandatory 10-minute aggregation periods
- 95th percentile statistical analysis
- Time synchronization requirements

**Class S (Survey/Statistical):**
- Simplified measurements for surveys
- Less stringent accuracy requirements
- Suitable for statistical analysis and trending

**Measured Parameters:**
- Voltage magnitude and frequency
- Flicker severity (Pst, Plt)
- Voltage dips, swells, and interruptions
- Voltage unbalance
- Harmonic and interharmonic voltages
- Mains signaling voltages

### IEEE 519: Harmonic Control in Electrical Power Systems
**Scope:**
- Limits for harmonic voltage and current distortion
- Point of Common Coupling (PCC) requirements
- Customer and utility responsibilities

**Key Limits:**
- Total Demand Distortion (TDD) limits
- Individual harmonic current limits
- Voltage distortion limits at PCC
- Short-circuit ratio (SCR) considerations

**Application:**
- System planning and design
- Harmonic filter design verification
- Compliance verification and documentation

### IEC 61000-3-2: Harmonic Current Emission Limits
**Equipment Coverage:**
- Equipment with input current ≤16A per phase
- Four equipment classes (A, B, C, D)
- Class A: Balanced three-phase equipment and other equipment
- Class B: Portable tools
- Class C: Lighting equipment
- Class D: Personal computers and monitors

### IEC 61000-3-12: Harmonic Current Emissions (>16A, ≤75A)
**Requirements:**
- Equipment drawing >16A up to 75A per phase
- Stage 1, Stage 2, and Stage 3 limits
- Connection type considerations

### IEC 61000-4-15: Flicker Measurement
**Flicker Severity:**
- Short-term flicker severity (Pst) - 10-minute intervals
- Long-term flicker severity (Plt) - 2-hour sliding window
- Flickermeter implementation requirements
- Perception-based weighting functions

### IEEE 1159: Monitoring Electric Power Quality
**Event Categories:**
- Transients (impulsive and oscillatory)
- Short-duration variations (instantaneous, momentary, temporary)
- Long-duration variations (sustained interruptions, under/overvoltages)
- Waveform distortion (DC offset, harmonics, interharmonics, notching, noise)

### EN 50160: Voltage Characteristics in Public Distribution Systems
**European Standard:**
- Voltage magnitude variations (±10% for 95% of week)
- Frequency variations (50Hz ±1% for 95% of year, +4%/-6% extreme)
- Flicker severity limits (Plt ≤ 1 for 95% of week)
- Harmonic voltage limits
- Voltage unbalance (≤2% for 95% of week, 3% maximum)

---

## 7. Comparison: Single-Phase vs Three-Phase Measurement Complexity

### Measurement Scope Comparison

| Measurement Type | Single-Phase | Three-Phase |
|-----------------|--------------|-------------|
| **Basic Power** | 1 set of P, Q, S | 3 sets per-phase + totals |
| **RMS Values** | 1 voltage, 1 current | 3 voltages, 3 currents + neutral |
| **Harmonics** | 1 voltage spectrum, 1 current spectrum | 3 voltage spectra, 3 current spectra |
| **Power Factor** | 1 value (PF, DPF, DF) | Per-phase + system totals |
| **Energy** | 2 directions (import/export) | 4 quadrants × 3 phases |
| **CPC Components** | 4 current components | 5 current components × 3 phases |
| **Additional Metrics** | N/A | Symmetrical components, unbalance factors, neutral current |

### Computational Complexity

**Single-Phase:**
- One FFT calculation per measurement window
- One set of power calculations
- Straightforward energy accumulation
- Simple threshold monitoring

**Three-Phase:**
- Three FFT calculations per measurement window
- Per-phase calculations plus vector summation
- Complex symmetrical component transformation
- Cross-phase relationships and unbalance
- Neutral current harmonic analysis
- Triplen harmonic special handling
- Increased event monitoring (per-phase events)

### Data Storage Requirements

**Single-Phase:**
- Moderate storage needs
- Two channels (voltage, current)
- Basic trend data

**Three-Phase:**
- 3-4× storage requirements (3 phases + neutral)
- Additional storage for sequence components
- Unbalance trending data
- Per-phase and system-wide event logs

---

## 8. Practical Implementation Considerations

### Sampling and Processing

**Minimum Sampling Rate:**
- 10 kHz for 50th harmonic measurement at 50Hz
- 12.8 kHz for 50th harmonic measurement at 60Hz
- Higher rates (25.6 kHz) for transient capture

**Processing Requirements:**
- Real-time FFT processing within 200ms windows
- Continuous buffering without data loss
- Sufficient computational power for three-phase systems
- Memory for waveform storage during events

### Accuracy Requirements

**Class A Instrument:**
- Voltage magnitude: ±0.1% of nominal
- Frequency: ±0.01 Hz
- Harmonics up to 40th: ±5% of measured value
- Power: ±0.5% of full scale
- Energy: Class 0.2S or better

### Communication and Integration

**Data Output:**
- Real-time data streaming for monitoring
- Event notification and alarms
- Historical data retrieval
- Trend analysis and reporting

**Protocols:**
- Modbus RTU/TCP for industrial integration
- IEC 61850 for substation automation
- MQTT for IoT applications
- REST API for web-based access

### User Interface Requirements

**Display Elements:**
- Real-time waveform display
- Phasor diagrams (especially for three-phase)
- Harmonic bar charts
- Trend graphs
- Event lists and waveform playback
- System status and diagnostics

---

## 9. Quality Assurance and Calibration

### Calibration Requirements

**Periodic Verification:**
- Annual calibration for Class A instruments
- Traceable calibration standards
- Voltage, current, power, and energy verification
- Harmonic accuracy verification

**Field Verification:**
- Quick checks using known reference sources
- Phase angle verification
- Harmonic injection testing
- Unbalance test scenarios for three-phase

### Self-Diagnostics

**Continuous Monitoring:**
- Input signal range verification
- ADC saturation detection
- Clock accuracy monitoring
- Memory integrity checks
- Communication link status

---

## Conclusion

Building an industrial-standard power analyzer requires comprehensive measurement capabilities, strict adherence to international standards, and robust data processing. Single-phase measurements provide foundational capabilities, while three-phase measurements add significant complexity with symmetrical components, unbalance analysis, and per-phase monitoring. The implementation should be staged according to application requirements, starting with essential Tier 1 measurements and progressing to advanced Tier 3 and 4 features as needed.

This specification provides a roadmap for developing a power analyzer that meets or exceeds the capabilities of commercial instruments while maintaining compliance with IEC and IEEE standards.
