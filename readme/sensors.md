# Sensor Selection and Configuration Guide

Complete guide for accurate AC power measurement with STM32 Nucleo boards - covering ADC characteristics, sensor selection, calibration procedures, and error analysis.

**Quick Links:**
- **Sensor configuration:** `src/config.py` (VOLTAGE_SENSOR, CURRENT_SENSOR)
- **Recommended order:** Read sections 1-4 → Assemble hardware → Section 5 (ADC test) → Section 6 (calibration) → Section 7 (understand errors)

---

## 1. STM32 ADC Fundamentals

### 1.1 ADC Input Range Constraint

**STM32 ADC can ONLY measure 0 to 3.3V:**
- Negative voltages → read as 0V (risk of ADC damage)
- Valid range: 0.0V to 3.3V only
- **Therefore:** All AC signals must be conditioned with DC bias to fit this range

### 1.2 ADC Resolution

| Board | Resolution | Levels | Quantization Step | % of Full Scale |
|-------|------------|--------|-------------------|-----------------|
| **L476RG** | 12-bit | 4096 | 0.806 mV | 0.024% |
| **H755ZI-Q** | 16-bit | 65536 | 0.050 mV | 0.0015% |

**Key insight:** H755ZI-Q provides 16× finer resolution - critical for Class A compliance.

### 1.3 ADC Noise Characteristics

**Noise sources:**
- **Quantization noise:** ±0.5 LSB inherent (unavoidable)
- **Thermal noise:** Electronics generate random voltage fluctuations
- **Reference voltage noise:** VREF isn't perfectly stable (~few mV)
- **Power supply ripple:** VCC variations couple into measurements

**Typical noise levels (DC input test with potentiometer):**
- **L476RG:** ±2-3 LSB standard deviation (~2-2.5 mV peak-to-peak)
- **H755ZI-Q:** ±5-10 LSB standard deviation (~0.25-0.5 mV peak-to-peak)

**Signal-to-Noise Ratio (SNR):**
- **L476RG:** ~60-65 dB (12-bit effective)
- **H755ZI-Q:** ~80-85 dB (16-bit effective, **20 dB better**)

**What is SNR?** Measures how much stronger your signal is compared to background noise. Higher = better!
- **60 dB:** Signal is 1,000× stronger than noise (good for basic measurements)
- **80 dB:** Signal is 10,000× stronger than noise (excellent for power quality analysis)
- **20 dB difference:** H755ZI-Q can detect signals **10× smaller** than L476RG

**Impact of noise on different measurements:**

**1. RMS Calculations (Basic Power Measurement):**
```
Noise reduction through averaging 2000 samples:
Reduction factor = √(N samples) = √2000 ≈ 45×

L476RG effective noise: 2.5 LSB / 45 ≈ 0.06 LSB (~0.002% of full scale)
H755ZI-Q effective noise: 8 LSB / 45 ≈ 0.18 LSB (~0.0003% of full scale)
```
**Conclusion:** Noise becomes negligible (<0.01%) compared to sensor accuracy (±1-2%). **Averaging makes both boards excellent for RMS.**

**2. Harmonic Analysis (FFT / Power Quality):**
- Noise creates a **noise floor** in frequency spectrum
- Harmonics below noise floor are undetectable (buried in noise)
- **L476RG (-60 to -65 dB):** Can detect harmonics down to ~1% of fundamental
- **H755ZI-Q (-80 to -85 dB):** Can detect harmonics down to ~0.1% of fundamental
- **Impact:** H755ZI-Q detects harmonics **10× smaller** (critical for IEC 61000-4-7)

**3. Power Factor & Phase Measurements:**
- Noise affects **zero-crossing detection** accuracy
- Phase jitter from noise → errors in power factor calculation
- **L476RG:** Phase accuracy ±0.5-1.0° typical (±0.009-0.017 PF error)
- **H755ZI-Q:** Phase accuracy ±0.1-0.2° typical (±0.002-0.003 PF error)
- **Impact:** H755ZI-Q provides **5× better** phase accuracy

**4. THD (Total Harmonic Distortion) Measurements:**
- THD limited by ability to detect small harmonics above noise
- **L476RG:** THD measurements limited to ~1-2% minimum
- **H755ZI-Q:** THD measurements down to ~0.1-0.2% possible
- **Impact:** H755ZI-Q meets Class A THD requirements (<1%), L476RG does not

**Summary - Noise Impact by Application:**

| Application | L476RG (12-bit) | H755ZI-Q (16-bit) | Winner |
|-------------|-----------------|-------------------|--------|
| **Basic RMS (V, I, P)** | Excellent (±0.002%) | Excellent (±0.0003%) | Tie ✓ |
| **Harmonic detection** | Good (down to 1%) | Excellent (down to 0.1%) | H755ZI-Q ✓✓ |
| **Power factor** | Good (±0.5-1.0°) | Excellent (±0.1-0.2°) | H755ZI-Q ✓✓ |
| **THD measurement** | Limited (>1% only) | Precise (>0.1%) | H755ZI-Q ✓✓ |
| **Class A compliance** | No (noise floor too high) | Yes (with quality sensors) | H755ZI-Q ✓✓ |

**Key insight:** For **basic power monitoring**, both boards work well. For **power quality analysis** (harmonics, THD, Class A), **H755ZI-Q's 20 dB better SNR is essential**.

---

## 2. Signal Conditioning Requirements

### 2.1 DC Biasing Concept

**Problem:** AC signals swing positive and negative, but STM32 ADC requires 0-3.3V.

**Solution:** Add DC offset of **1.65V** (midpoint of 0-3.3V range):
- AC signal centered at 1.65V can swing ±1.65V without going negative
- Sensor VCC/2 creates this bias automatically when powered at 3.3V

**Example waveform at ADC input:**
```
                                      L476RG (12-bit)   H755ZI-Q (16-bit)
Mains peak:  +230V√2  →  ADC: 3.15V  (ADC: ~3900)      (ADC: ~62650)
Mains zero:      0V  →  ADC: 1.65V  (ADC: ~2048)      (ADC: ~32768) ← DC bias
Mains trough:-230V√2  →  ADC: 0.15V  (ADC: ~190)       (ADC: ~3050)
```

### 2.2 Signal Chain Overview

**Voltage measurement:**
```
230V AC Mains → ZMPT101B (isolation + scaling) → DC Bias 1.65V → STM32 ADC PA0
   ±325V peak          ±1.5V AC max                  0-3.3V range      Safe!
```

**Current measurement:**
```
AC Load Current → ACS712 (Hall effect) → DC Bias 1.65V → STM32 ADC PA1/PC0
    0-5A                ±0.5V AC           0-3.3V range      Safe!
```

---

## 3. Sensor Hardware Selection

### 3.1 Voltage Sensor - ZMPT101B

**Recommended:** ZMPT101B precision voltage transformer module (~$2-5)

**Why ZMPT101B:**
- Galvanic isolation (transformer-based, 1kV minimum)
- Built-in DC bias circuit (VCC/2 automatic)
- Adjustable gain (potentiometer calibration)
- Wide input range (0-250V AC covers worldwide mains)

**Specifications:**
- **Accuracy:** ±1-2% after calibration
- **Linearity:** >95% across 10-100% input range  
- **Temperature drift:** Low (better than Hall effect)
- **Frequency range:** 50/60 Hz optimized
- **Response time:** <500 ms

**Error sources:**
- Nonlinearity: ±1% typical
- Temperature coefficient: ±0.3% over 0-40°C
- Aging: <0.5% per year

**Configuration:**
1. **Power:** 3.3V from STM32 (NOT 5V - would need level shifter!)
2. **Gain adjustment:** Use oscilloscope, adjust pot for ~3.0V peak-to-peak at 230V input (leaves 0.15V margin)
3. **Signal output → STM32 ADC pin:**
   - L476RG: PA0 (ADC1_IN5, CN8 Pin 1)
   - H755ZI-Q: PA0_C (ADC1_INP16, CN9 Pin 1)
4. **Ground:** Common GND with STM32

**Typical scaling:** 1:200 to 1:230 (230V mains → 1.0-1.3V RMS sensor output)

### 3.2 Current Sensor - ACS712

**Recommended:** ACS712-05B Hall effect current sensor module (~$1-3)

**Why ACS712:**
- Simple integration (pre-configured, no external components)
- Galvanic isolation (Hall effect)
- Bidirectional (AC measurement ready)
- Compact PCB module

**Model selection:**
- **ACS712-05B:** ±5A, 185 mV/A @ 5V (100 mV/A @ 3.3V) - **RECOMMENDED**
- **ACS712-20B:** ±20A, 100 mV/A @ 5V - for higher currents
- **ACS712-30B:** ±30A, 66 mV/A @ 5V - industrial loads

**Specifications (05B model):**
- **Accuracy:** ±1.5% at 25°C
- **Noise:** ~21 mV RMS @ 5V (reduces at 3.3V)
- **Bandwidth:** 80 kHz (sufficient for 50/60 Hz + harmonics)
- **Response time:** <5 µs

**Error sources:**
- Nonlinearity: ±1% typical
- Temperature coefficient: ±2 mV/°C offset drift
- Noise: ±0.5% after averaging 2000 samples

**Configuration:**
1. **Power:** 3.3V from STM32 (sensitivity becomes ~100 mV/A)
2. **Current path:** Wire AC load through sensor IP+ and IP- terminals
3. **Signal output → STM32 ADC pin:**
   - L476RG: PA1 (ADC2_IN6, CN8 Pin 2)
   - H755ZI-Q: PC0 (ADC2_INP10, CN9 Pin 2)
4. **Ground:** Common GND with STM32

**Alternative: Current Transformer (CT) - SCT-013-000**
- Non-invasive (clamp-on), higher accuracy (±1%)
- Requires external burden resistor (330Ω) + DC bias circuit
- Use when: Non-invasive install needed or measuring >30A

---

## 4. Complete Hardware Assembly

### 4.1 Wiring Connections

**L476RG (CN8 Arduino Header):**
```
Pin 1 (A0/PA0) ← ZMPT101B output (voltage)
Pin 2 (A1/PA1) ← ACS712 output (current)
Pin 8 (GND)    ← Sensor common ground
3.3V pin       → Sensor VCC (both sensors)
```

**H755ZI-Q (CN9 Arduino Header):**
```
Pin 1 (A0/PA0_C) ← ZMPT101B output (voltage, ADC1_INP16)
Pin 2 (A1/PC0)   ← ACS712 output (current, ADC2_INP10)
Pin 8 (GND)      ← Sensor common ground
3.3V pin         → Sensor VCC (both sensors)
```

### 4.2 Safety Checklist

- [ ] **NEVER** connect mains voltage directly to STM32
- [ ] Use **isolated** sensors only (ZMPT101B, ACS712, or CT)
- [ ] Verify sensor output <3.3V with multimeter **before** connecting to STM32
- [ ] Power sensors with 3.3V (NOT 5V)
- [ ] Common ground for all components
- [ ] Optional: Add 3.3V Zener diode protection on ADC inputs
- [ ] Proper insulation on mains voltage wiring

---

## 5. ADC Characterization (Optional but Recommended)

**Purpose:** Test ADC performance **before** connecting real sensors - isolates ADC errors from sensor errors.

**Required equipment:**
- Function generator or oscilloscope AWG output
- Multimeter (verify DC bias and AC amplitude)

### 5.1 DC Noise Test

**Objective:** Measure ADC noise floor

**Procedure:**
1. Generate **1.65V DC** (use voltage divider: 3.3V with 2× 10kΩ resistors)
2. Connect to ADC input (PA0 for voltage test)
3. Capture 1000 ADC samples in firmware
4. Calculate statistics:
   ```python
   samples = read_adc(1000)
   mean = np.mean(samples)
   std_dev = np.std(samples)
   peak_to_peak = np.max(samples) - np.min(samples)
   
   # Expected results:
   # L476RG: mean ≈ 2048, std_dev ≈ 2-3 LSB, pk-pk ≈ 10-15 LSB
   # H755ZI-Q: mean ≈ 32768, std_dev ≈ 5-10 LSB, pk-pk ≈ 30-50 LSB
   ```

5. **Pass criteria:** 
   - Mean within ±10 LSB of expected (2048 or 32768)
   - Std dev <5 LSB (L476RG) or <15 LSB (H755ZI-Q)

### 5.2 AC RMS Test

**Objective:** Verify RMS calculation accuracy with known sine wave

**Procedure:**
1. Generate **1.65V DC + 1.0V AC @ 50Hz sine wave** from AWG
   - Peak voltage: 1.65V + 1.0V = 2.65V (safe margin from 3.3V)
   - RMS amplitude: 1.0V / √2 = 0.707V RMS
2. Verify with oscilloscope: DC level = 1.65V, peak-to-peak = 2.0V
3. Capture 2000 ADC samples (200ms window at 10 kHz)
4. Calculate RMS:
   ```python
   # Convert ADC to voltage
   voltage = (adc_data / 4095) * 3.3  # L476RG
   voltage = (adc_data / 65535) * 3.3  # H755ZI-Q
   
   # Remove DC bias
   dc_bias = np.mean(voltage)
   ac_signal = voltage - dc_bias
   
   # Calculate RMS
   measured_rms = np.sqrt(np.mean(ac_signal**2))
   
   # Expected: 0.707V ± 1%
   error_percent = abs(measured_rms - 0.707) / 0.707 * 100
   ```

5. **Pass criteria:**
   - DC bias: 1.65V ± 0.02V
   - RMS error: <±1% (should get 0.700-0.714V)

### 5.3 SNR Measurement

```python
# From AC test data:
signal_power = measured_rms**2
noise_power = std_dev**2  # From DC test
SNR_dB = 10 * np.log10(signal_power / noise_power)

# Expected:
# L476RG: SNR ≈ 60-65 dB
# H755ZI-Q: SNR ≈ 80-85 dB
```

**Result:** You now know ADC-only error contribution (<±1% for both boards after averaging).

---

## 6. System Calibration (Mandatory)

Calibrate the complete measurement chain: Sensor + ADC

### 6.1 Voltage Calibration

**Required equipment:**
- Calibrated multimeter (DMM)
- Known AC voltage source (mains outlet with verified voltage)

**Procedure:**

1. **DC bias verification:**
   - Disconnect AC input from ZMPT101B
   - Run firmware, read ADC value
   - **Expected:** L476RG ~2048, H755ZI-Q ~32768 (±1%)
   - **If wrong:** Check sensor powered at 3.3V (not 5V!)

2. **Connect known voltage:**
   - Measure mains with calibrated DMM (e.g., 232.5V RMS)
   - Safety: Proper insulation, isolated outlet
   - Connect ZMPT101B input to mains

3. **Capture data:**
   - Collect 2000 ADC samples (200ms window)
   - Repeat 5 times, average results

4. **Calculate scaling factor:**
   ```python
   # Convert ADC to voltage
   samples_v = (adc_data / 4095) * 3.3  # L476RG
   samples_v = (adc_data / 65535) * 3.3  # H755ZI-Q
   
   # Remove DC bias and calculate RMS
   dc_bias = np.mean(samples_v)
   ac_signal = samples_v - dc_bias
   sensor_rms = np.sqrt(np.mean(ac_signal**2))
   
   # Determine calibration factor
   scaling_factor = sensor_rms / dmm_voltage
   
   # Example: 
   # DMM: 232.5V, Sensor RMS: 1.01V
   # scaling_factor = 1.01 / 232.5 = 0.00434
   ```

5. **Update config.py:**
   ```python
   VOLTAGE_SENSOR = {
       "name": "ZMPT101B",
       "scaling_factor": 0.00434,  # Your measured value
       "dc_bias": 1.65,
       "max_input": 250.0
   }
   ```

6. **Multi-point verification** (if variable voltage available):
   - Test at 50%, 75%, 100% of range
   - All points should match DMM within ±2%
   - Verifies sensor linearity

**Typical values:** scaling_factor ≈ 0.0043 to 0.0050 (1:200 to 1:230 ratio)

### 6.2 Current Calibration

**Required equipment:**
- Calibrated clamp meter or DMM with AC current mode
- Variable AC load (resistive heater, dimmable)

**Required equipment:**
- Calibrated clamp meter or DMM with AC current mode
- Variable AC load (resistive heater, dimmable)

**Procedure:**

1. **DC bias verification:**
   - No current flowing, check ADC reading
   - **Expected:** L476RG ~2048, H755ZI-Q ~32768 (±1%)

2. **Flow known current:**
   - Start with 1-2A for safety
   - Measure with calibrated clamp meter (e.g., 3.2A)

3. **Capture data:**
   - Collect 2000 ADC samples (200ms window)
   - Repeat 5 times, average results

4. **Calculate sensitivity:**
   ```python
   # Convert ADC to voltage
   current_v = (adc_data / 4095) * 3.3  # L476RG
   current_v = (adc_data / 65535) * 3.3  # H755ZI-Q
   
   # Remove DC bias and calculate RMS
   ac_component = current_v - 1.65
   sensor_rms = np.sqrt(np.mean(ac_component**2))
   
   # Determine calibration factor
   sensitivity = sensor_rms / dmm_current
   
   # Example (ACS712-05B at 3.3V):
   # DMM: 3.2A, Sensor RMS: 0.32V
   # sensitivity = 0.32 / 3.2 = 0.100 V/A
   ```

5. **Update config.py:**
   ```python
   CURRENT_SENSOR = {
       "name": "ACS712-05B",
       "sensitivity": 0.100,  # Your measured value (V/A)
       "dc_bias": 1.65,
       "max_current": 5.0
   }
   ```

6. **Multi-point verification:**
   - Test at 1A, 3A, 5A (20%, 60%, 100% of range)
   - Verify linearity: All points should match meter within ±2%

**Expected values:**
- ACS712-05B @ 3.3V: sensitivity ≈ 0.095-0.105 V/A
- ACS712-05B @ 5V: sensitivity ≈ 0.185 V/A (datasheet)
- CT with 330Ω burden: Calculate from turns ratio

### 6.3 Calibration Best Practices

**Environmental conditions:**
- Stable temperature: 20-25°C (±2°C variation max)
- Sensor warm-up: 10-15 minutes powered on before calibration
- Avoid drafts, direct sunlight, or heat sources

**Multi-point calibration (if possible):**
- Voltage: Test at 50%, 75%, 100% of expected range
- Current: Test at 20%, 60%, 100% of sensor range
- Verifies linearity, detects sensor defects

**Recalibration schedule:**
- **Initial:** After assembly and sensor installation
- **Regular:** Every 6-12 months for ±1% accuracy target
- **After events:** Sensor replacement, power supply changes, PCB modifications

---

## 7. Error Budget Analysis

### 7.1 Error Types

**Two fundamental categories:**

**1. Random Errors (Precision):**
- Shot-to-shot variations, different each measurement
- **Sources:** ADC noise, sensor noise, electromagnetic interference
- **Characteristic:** Zero mean, normal distribution
- **Solution:** Averaging (reduces by √N factor)

**2. Systematic Errors (Accuracy):**
- Consistent offset or scaling, same every measurement
- **Sources:** Sensor nonlinearity, calibration residual, temperature drift
- **Characteristic:** Bias in one direction
- **Solution:** Calibration, temperature compensation

### 7.2 Error Sources Summary

| Error Source | L476RG | H755ZI-Q | Type | Mitigation |
|--------------|--------|----------|------|------------|
| **ADC quantization** | 0.024% FS | 0.0015% FS | Random | Inherent (minimal) |
| **ADC noise (raw)** | ±2-3 LSB | ±5-10 LSB | Random | Averaging |
| **ADC noise (after avg)** | ~0.002% | ~0.0003% | Random | Already done |
| **Calibration residual** | ±0.5% | ±0.2% | Systematic | Better DMM, multi-point cal |
| **ZMPT101B nonlinearity** | ±1.0% | ±1.0% | Systematic | Multi-point calibration |
| **ACS712 nonlinearity** | ±1.5% | ±1.5% | Systematic | Multi-point calibration |
| **Temperature drift** | ±0.3% | ±0.3% | Systematic | Temp compensation (advanced) |
| **Aging (1 year)** | ±0.5% | ±0.5% | Systematic | Annual recalibration |

**FS = Full Scale**

### 7.3 Total Error Calculation

Use **Root Sum Square (RSS)** for combining independent errors:

```
Total Error = √(error₁² + error₂² + error₃² + ...)
```

**Why RSS (not direct sum):**
- Errors are independent, random, normally distributed
- Direct sum is overly pessimistic (worst-case, unlikely)
- RSS gives realistic expected error (68% confidence)

**Example 1: L476RG Voltage Measurement**
```
Error sources:
- ADC noise (after averaging): ±0.002%
- Calibration residual: ±0.5%
- ZMPT101B nonlinearity: ±1.0%
- Temperature drift: ±0.3%

Total = √(0.002² + 0.5² + 1.0² + 0.3²)
      = √(0.000004 + 0.25 + 1.0 + 0.09)
      = √1.34
      = ±1.16% ≈ ±1.2%

Result: ~230V ±2.8V accuracy
```

**Example 2: H755ZI-Q Current Measurement**
```
Error sources:
- ADC noise (after averaging): ±0.0003%
- Calibration residual: ±0.2%
- ACS712 nonlinearity: ±1.5%
- Temperature drift (±2mV / 100mV): ±2.0%

Total = √(0.0003² + 0.2² + 1.5² + 2.0²)
      = √(0.0000001 + 0.04 + 2.25 + 4.0)
      = √6.29
      = ±2.51% ≈ ±2.5%

Result: ~3.0A ±0.075A accuracy
```

### 7.4 Accuracy Expectations

**L476RG (12-bit ADC):**
- **Voltage measurement:** ±1.2-1.5% typical
- **Current measurement:** ±2.0-2.5% typical
- **Limiting factor:** Sensor quality (±1-1.5%)
- **ADC contribution:** <0.01% (negligible after averaging)

**H755ZI-Q (16-bit ADC):**
- **Voltage measurement:** ±0.5-0.8% typical (with quality sensors)
- **Current measurement:** ±1.5-2.0% typical
- **Limiting factor:** ACS712 temp drift (±2%) and nonlinearity (±1.5%)
- **ADC contribution:** <0.001% (negligible)
- **Potential:** ±0.2% achievable with precision sensors (e.g., CT + low-drift op-amps)

**Key insight:** **Sensors dominate error budget**, not ADC. Upgrading sensors has more impact than upgrading MCU for L476RG → H755ZI-Q.

### 7.5 Improving Accuracy

**To achieve <±1% total error:**

1. **Use better sensors:**
   - Replace ACS712 with CT (±1% vs ±1.5%)
   - Use precision voltage sensor (±0.5% available)
   - Cost: ~$10-20 more expensive

2. **Temperature compensation:**
   - Add temperature sensor (DS18B20, ~$1)
   - Measure ACS712 offset drift vs temperature
   - Apply correction in firmware
   - Improves: ±0.5-1% reduction in error

3. **Multi-point calibration:**
   - Calibrate at 3-5 voltage/current levels
   - Create lookup table or polynomial fit
   - Corrects sensor nonlinearity
   - Improves: ±0.3-0.5% reduction

4. **Use H755ZI-Q with precision sensors:**
   - 16-bit ADC + CT + precision voltage sensor
   - Temperature compensation
   - **Result:** ±0.2-0.5% achievable (Class A compliance)

---

## 8. Software Processing Reference

Complete code example for RMS calculation:

```python
# Configuration in src/config.py
VOLTAGE_SENSOR = {
    "name": "ZMPT101B",
    "scaling_factor": 0.00434,  # Calibrated (V_sensor / V_mains)
    "dc_bias": 1.65,            # VCC/2 for 3.3V operation
    "max_input": 250.0          # Maximum input voltage (V AC)
}

CURRENT_SENSOR = {
    "name": "ACS712-05B",
    "sensitivity": 0.100,  # V/A at 3.3V supply
    "dc_bias": 1.65,       # VCC/2 for 3.3V operation
    "max_current": 5.0     # ±A
}

# Processing function
def process_adc_samples(voltage_adc, current_adc, adc_resolution=4095):
    """
    Process dual-channel ADC samples to voltage and current measurements.
    
    Args:
        voltage_adc: Array of ADC values from voltage channel (2000 samples)
        current_adc: Array of ADC values from current channel (2000 samples)
        adc_resolution: 4095 for L476RG, 65535 for H755ZI-Q
    
    Returns:
        (voltage_rms, current_rms): Calibrated RMS values in V and A
    """
    # 1. Convert ADC to voltage
    voltage_samples = (voltage_adc / adc_resolution) * 3.3
    current_samples = (current_adc / adc_resolution) * 3.3
    
    # 2. Remove DC bias (center at 0V)
    voltage_ac = voltage_samples - np.mean(voltage_samples)
    current_ac = current_samples - np.mean(current_samples)
    
    # 3. Calculate RMS
    voltage_sensor_rms = np.sqrt(np.mean(voltage_ac**2))
    current_sensor_rms = np.sqrt(np.mean(current_ac**2))
    
    # 4. Apply sensor calibration
    voltage_mains_rms = voltage_sensor_rms / VOLTAGE_SENSOR["scaling_factor"]
    current_rms = current_sensor_rms / CURRENT_SENSOR["sensitivity"]
    
    return voltage_mains_rms, current_rms

# Example usage:
# voltage_rms, current_rms = process_adc_samples(adc_voltage_buffer, adc_current_buffer, 65535)
# print(f"Mains: {voltage_rms:.1f}V RMS, {current_rms:.2f}A RMS")
# power = voltage_rms * current_rms  # Apparent power (VA)
```

**Why RMS:**
- AC signals vary sinusoidally, average is zero
- RMS = "effective" value (equivalent DC power delivery)
- For sine wave: V_RMS = V_peak / √2 ≈ 0.707 × V_peak

---

## 9. Validation & Testing

### 9.1 Known Load Test

**Resistive load (100W incandescent bulb):**
```
Expected at 230V:
- Current: P / V = 100W / 230V = 0.43A
- Power factor: 1.0 (resistive)
- Phase: Voltage and current in-phase

Measured should be:
- Voltage: 230V ± 3V (±1.5% error)
- Current: 0.43A ± 0.01A (±2.5% error)
- Power: ~100W ± 3W
```

### 9.2 Power Factor Check

**Resistive load:** PF should be ≈ 1.0 (±0.05)  
**Inductive load (motor):** PF typically 0.6-0.8 (lagging)  
**Capacitive load (PSU):** PF typically 0.5-0.9 (complex)

### 9.3 Phase Relationship

For resistive loads, voltage and current should be **in-phase**:
- Plot both waveforms simultaneously
- Zero-crossings should align within ±1ms
- Verifies dual simultaneous ADC sampling works correctly