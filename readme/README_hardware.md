# Hardware Setup Guide

This document describes the hardware requirements and signal conditioning for AC voltage and current measurement using STM32 Nucleo L476RG.

**Note:** Sensor parameters are configured globally in `src/config.py` (VOLTAGE_SENSOR and CURRENT_SENSOR). Update these values to match your actual hardware and calibration.

## Critical Constraint: STM32 ADC Input Range

**STM32 ADC can ONLY measure 0 to 3.3V**
- Negative voltages → read as 0 (risk of damage)
- Valid range: 0.0V to 3.3V
- ADC resolution: 12-bit (0-4095)

**Therefore:** All AC signals must be conditioned to fit 0-3.3V range with DC bias.

---

## 1. AC Voltage Measurement

### Signal Conditioning Requirements

AC mains voltage (230V RMS, ±325V peak) cannot be measured directly. Required signal chain:

```
230V AC Mains → Isolation/Scaling → DC Bias → STM32 ADC (PA0)
   ±325V            ±1.5V max        +1.65V      0-3.3V
```

### DC Biasing Concept

AC signals swing positive and negative, but STM32 ADC requires 0-3.3V:

- **Solution:** Add DC offset of 1.65V (midpoint of 0-3.3V range)
- **Result:** AC signal centered at 1.65V, can swing ±1.65V without going negative

**Example waveform at ADC input:**
```
Mains peak:  +230V√2  →  ADC: 3.15V  (ADC value: ~3900)
Mains zero:      0V  →  ADC: 1.65V  (ADC value: ~2048) ← DC bias point
Mains trough:-230V√2  →  ADC: 0.15V  (ADC value: ~190)
```

### ZMPT101B Voltage Sensor Module

**Recommended sensor:** ZMPT101B precision voltage transformer module

**Specifications:**
- Input: 0-250V AC (mains voltage side)
- Output: DC-biased AC signal (0-5V default, adjustable)
- Built-in isolation transformer
- Built-in voltage divider and DC bias circuit
- Adjustable gain (potentiometer)

**Configuration for STM32:**
1. **Power with 3.3V** (not 5V!) → DC bias becomes 1.65V automatically
2. **Adjust potentiometer** to ensure output stays within 0-3.3V at max input
3. **Connect output** directly to STM32 PA0 (ADC1_IN5)
4. **Connect GND** to common ground

**Typical scaling:** 230V RMS input → ~1.0-1.5V RMS output (adjustable)

### Software Processing

```python
# 1. Convert ADC to voltage
voltage = (adc_value / 4095) * 3.3

# 2. Remove DC bias (center at 0V)
dc_bias = 1.65  # or calculate: np.mean(samples)
ac_signal = voltage - dc_bias

# 3. Calculate RMS (effective AC voltage)
rms = np.sqrt(np.mean(ac_signal**2))

# 4. Apply calibration factor
actual_voltage = rms * calibration_factor
```

**Calibration:** Measure known voltage (e.g., 230V mains), calculate scaling factor.

---

## 2. AC Current Measurement

### Signal Conditioning Requirements

AC current measurement requires conversion to voltage with DC bias:

```
AC Current → Current Sensor → DC Bias → STM32 ADC (PA1)
  0-10A         ±1.5V max      +1.65V      0-3.3V
```

### Current Sensor Options

**Option A: Current Transformer (CT) - SCT-013-000**
- Non-invasive (clamp around wire)
- Galvanic isolation
- Output: AC current (needs burden resistor)
- **Circuit:** CT → Burden resistor → DC bias network → PA1

**Burden resistor calculation:**
```
For 10A max → 1.5V peak output:
R_burden = 1.5V / (10A / CT_ratio)
Example: SCT-013-000 (100:0.05A ratio)
R_burden = 1.5V / 0.5A = 3Ω (use 10Ω for safety margin)
```

**DC bias circuit:**
```
CT output → [Rbias 10kΩ to 1.65V] + [Coupling cap 10µF] → PA1
            [Rbias 10kΩ to GND]
```

**Option B: Hall Effect Current Sensor - ACS712**
- Measures current via magnetic field
- Built-in isolation
- Output: DC-biased voltage (typically 2.5V ± sensing range)
- **For STM32:** Use ACS712-05B or similar, power with 3.3V

**Configuration:**
1. **Power with 3.3V** → output bias becomes 1.65V
2. **Sensitivity:** ~185mV/A (for ACS712-05A)
3. **Connect output** directly to STM32 PA1 (ADC2_IN6)
4. **Connect GND** to common ground

### Software Processing

Same as voltage measurement:
```python
# Remove DC bias and calculate RMS
dc_bias = np.mean(current_samples_voltage)
ac_current_voltage = samples - dc_bias
rms_voltage = np.sqrt(np.mean(ac_current_voltage**2))

# Convert to actual current (apply sensor sensitivity)
actual_current = rms_voltage / sensor_sensitivity  # e.g., 0.185 V/A
```

---

## Complete Dual-Channel Setup

**STM32 Connections (L476RG):**
```
CN8 Arduino Header:
Pin 1 (A0/PA0) ← ZMPT101B output (voltage sensor)
Pin 2 (A1/PA1) ← Current sensor output (CT or Hall effect)
Pin 8 (GND)    ← Common ground for all sensors
```

**STM32 Connections (H755ZI-Q):**
```
CN9 Arduino Header:
Pin 1 (A0/PA0) ← ZMPT101B output (voltage sensor) - ADC1_INP16
Pin 2 (A1/PC0) ← Current sensor output (CT or Hall effect) - ADC2_INP10
Pin 8 (GND)    ← Common ground for all sensors
```

**Power Requirements:**
- Power sensors with 3.3V from STM32 (avoid 5V!)
- Common ground for all components
- Separate analog and digital grounds if possible (noise reduction)

**Safety:**
- **NEVER** connect mains voltage directly to STM32
- Use **isolated** sensors only (ZMPT101B, CT, or Hall effect)
- Verify sensor output range with multimeter before connecting to STM32
- Add **3.3V Zener diode** protection on ADC inputs (optional but recommended)

---

## Testing Without Mains Voltage

For safe initial testing, use signal generator (e.g., PicoScope AWG):

1. **Generate test signal:** 1.65V DC + 0.5V AC (50Hz sine)
2. **Connect to sensor output** (bypass sensor for pure signal path test)
3. **Verify STM32 reads:** DC bias ≈ 2048, AC swing ± few hundred counts
4. **Validate RMS calculation** against known input
5. **Gradually increase amplitude** to test full range

**Alternative:** Use sensor with low AC input voltage:
- ZMPT101B: Input 12V AC (from isolation transformer) instead of 230V
- CT: Measure small AC current (1A instead of 10A)
- Verify linearity at safe levels before using at full scale

---

## Calibration Procedure

1. **Measure DC bias:** Sample ADC with no input → should read ~2048 (1.65V)
2. **Apply known AC voltage/current** (use calibrated meter as reference)
3. **Calculate scaling factor:** `factor = known_value / measured_rms`
4. **Store calibration factor** in firmware/software
5. **Verify across range:** Test at 10%, 50%, 100% of full scale

**Typical accuracy:** ±1-2% after calibration (limited by ADC resolution and sensor quality)
