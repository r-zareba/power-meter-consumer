# Power Meter - Industry Standard Specifications

## Overview
This document outlines the measurements, metrics, and standards for building an accurate, industry-standard power analyzer comparable to commercial units like Fluke 435 or Hioki PW3198.

---

## 1. Fundamental Power Measurements (IEC 61000-4-30 Class A/S)

### Electrical Measurements
- **RMS Voltage** (V_rms) - 200ms windows, 10-min averaging
- **RMS Current** (I_rms) - 200ms windows, 10-min averaging
- **Active Power** (P) - Real power in Watts
- **Reactive Power** (Q) - Reactive power in VAR
- **Apparent Power** (S) - Total power in VA

### Power Quality Metrics
- **Power Factor** (PF) - Ratio P/S
- **Displacement Power Factor** - cos(φ) at fundamental frequency only
- **Frequency** - Grid frequency tracking (49-51 Hz monitoring)

---

## 2. Harmonic Analysis (IEC 61000-4-7)

### Standard Requirements
- **Window Duration**: 200ms (10 cycles at 50Hz)
- **Frequency Resolution**: 5Hz bins (for 10kHz sampling, 2000 samples)
- **Harmonic Range**: Up to 50th harmonic (2.5 kHz)

### Measurements
- **Individual Harmonics (H1-H50)**
  - Voltage harmonics amplitude
  - Current harmonics amplitude
  - Phase angles (optional but valuable for diagnosis)

- **THD-V** - Total Harmonic Distortion for Voltage
  - Formula: `THD-V = √(H2² + H3² + ... + H50²) / H1`
  
- **THD-I** - Total Harmonic Distortion for Current
  - Formula: `THD-I = √(H2² + H3² + ... + H50²) / H1`

---

## 3. Power Quality Indices

- **TDD** (Total Demand Distortion)
  - THD-I normalized to rated/demand current
  - Important for IEEE 519 compliance
  
- **Crest Factor**
  - Formula: Peak Value / RMS Value
  - Calculated for both voltage and current
  
- **K-Factor**
  - Transformer derating factor
  - Accounts for increased heating from harmonics
  
- **Voltage Events**
  - Sag detection (>10% drop)
  - Swell detection (>10% rise)
  - Duration tracking
  
- **Flicker Severity** (Optional, complex)
  - Requires specialized algorithms

---

## 4. Energy Metrics

Integrated power measurements over time:

- **Active Energy** (kWh) - Billable energy
- **Reactive Energy** (kVARh) - Non-productive energy
- **Apparent Energy** (kVAh) - Total energy delivery

---

## 5. Per-Harmonic Power (Advanced)

Individual power contribution from each harmonic:

```
P_h = V_h × I_h × cos(θ_v,h - θ_i,h)
```

Where:
- `V_h` = Voltage amplitude of harmonic h
- `I_h` = Current amplitude of harmonic h
- `θ_v,h` = Voltage phase of harmonic h
- `θ_i,h` = Current phase of harmonic h

**Use Case**: Identify which harmonics contribute to or detract from real power delivery.

---

## 6. Time-Domain Statistics

Statistical analysis per 200ms window:

- **Min/Max/Average** values
- **Standard Deviation**
- **Percentiles** (95th, 99th)

---

## Implementation Priority

### Phase 1: Essential Measurements
✓ Core functionality for basic power monitoring

- RMS Voltage & Current
- Active Power (P)
- Reactive Power (Q)
- Apparent Power (S)
- Power Factor (PF)
- THD-V & THD-I
- Individual harmonics H1-H50 (amplitude only)
- Energy accumulation (kWh, kVARh, kVAh)

### Phase 2: Standard Compliance
✓ Meet IEC/IEEE standards

- Grid frequency tracking
- Crest factor calculation
- TDD calculation
- Voltage event detection (sag/swell)
- 10-minute aggregation & logging
- Displacement power factor

### Phase 3: Advanced Features
✓ Professional-grade capabilities

- Harmonic phase angles
- Per-harmonic power calculation
- K-factor calculation
- Waveform capture on events
- Advanced statistical analysis

---

## Data Storage & Reporting

### Time Windows
- **Real-time**: 200ms windows (IEC 61000-4-7 compliant)
- **Aggregated**: 3-second averages (15 × 200ms windows)
- **Logged**: 10-minute intervals (standard for billing/compliance)

### Event Recording
- Capture and store waveform data when thresholds are exceeded
- Timestamp all events
- Log event duration and magnitude

---

## Czarnecki's Power Theory (Advanced)

### Overview
Czarnecki's Power Theory provides a more detailed decomposition of power in non-sinusoidal conditions, distinguishing between different types of non-active power.

### Power Decomposition

**Apparent Power (S):**
```
S² = P² + Q₁² + D_H² + D_V²
```

Where:
- **P** - Active Power (real power, does work)
- **Q₁** - Reactive Power (fundamental frequency only, phase shift)
- **D_H** - Current Distortion Power (from current harmonics)
- **D_V** - Voltage Distortion Power (from voltage harmonics)

### Different Power Factors

#### 1. Total Power Factor (PF)
Classical definition, includes all effects:
```
PF = P / S
```
- Range: 0 to 1
- Accounts for phase shift + harmonics + distortion
- Used for billing and IEC compliance

#### 2. Displacement Power Factor (DPF or cos φ₁)
Only fundamental frequency component:
```
DPF = cos(θ_v1 - θ_i1)
```
- Phase angle between fundamental voltage and current
- Ignores harmonics completely
- Shows only "traditional" reactive power effect

#### 3. Distortion Power Factor (DF)
Harmonic content effect:
```
DF = √(1 - THD_I²) / √(1 + THD_I²)
```
Or more precisely:
```
DF = I₁ / I_rms
```
- Shows impact of current harmonics
- Independent of phase shift
- DF = 1 means no harmonics (pure sine)

#### 4. Relationship
```
PF = DPF × DF
```

**Example:**
- DPF = 0.95 (5° phase shift at fundamental)
- DF = 0.90 (10% current harmonics)
- PF = 0.95 × 0.90 = 0.855

### Calculation from Samples

**Fundamental Phase Angle (for DPF):**
1. Extract H1 voltage and current from FFT (with phase)
2. Calculate: `DPF = cos(phase_v1 - phase_i1)`

**Distortion Factor (for DF):**
1. Calculate I_rms from all samples
2. Extract I₁ (fundamental current RMS from FFT)
3. Calculate: `DF = I₁ / I_rms`

**Total Power Factor:**
1. Calculate P and S from samples
2. `PF = P / S` (includes everything automatically)

### Use Cases

| Metric | Use Case |
|--------|----------|
| **PF** | Billing, efficiency, overall system performance |
| **DPF** | Capacitor bank sizing (only corrects phase shift) |
| **DF** | Harmonic filter effectiveness |
| **Q₁** | Traditional reactive compensation |
| **D_H** | Active filter design, harmonic mitigation |

### Implementation Note
For **industrial compliance and billing**, use classical PF = P/S. Czarnecki's decomposition is valuable for:
- Diagnosing power quality issues
- Designing compensation systems
- Understanding harmonic effects
- Research and advanced analysis

---

## Relevant Standards

### IEC 61000-4-7
- **Harmonic Measurements**
- 200ms measurement window (10 cycles at 50Hz)
- Up to 50th harmonic
- 5Hz frequency resolution

### IEC 61000-4-30 (Class A/S)
- **Power Quality Measurements**
- 200ms windows
- 10-minute aggregation
- Event detection requirements

### IEEE 519
- **Harmonic Limits**
- TDD requirements
- Individual harmonic distortion limits
- Point of common coupling (PCC) measurements

---

## System Configuration

### Current Implementation
- **Sampling Frequency**: 10 kHz
- **Buffer Size**: 2000 samples
- **Window Duration**: 200ms (10 cycles at 50Hz)
- **Frequency Resolution**: 5 Hz
- **Nyquist Frequency**: 5 kHz (100th harmonic capability)
- **Target Harmonics**: 50th harmonic (2.5 kHz)

### Hardware Requirements
- STM32 ADC with sufficient resolution (12-bit minimum, 16-bit recommended)
- Synchronous sampling for voltage and current channels
- Adequate memory for 2000-sample buffers
- Real-time processing capability
