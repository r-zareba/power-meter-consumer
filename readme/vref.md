# VREF Calibration and Measurement Accuracy

## The Problem with Assuming 3.3V

ADC conversion formula:
```
Voltage = (ADC_reading / 65535) × VREF
```

**VDDA (Analog supply voltage)** is typically "3.3V" but actually varies:
- Voltage regulator tolerance: ±3%
- Load-dependent voltage drop: ±1%
- Temperature effects: ±0.5%
- **Actual range: 3.2V - 3.35V**

**Impact:** Assuming VREF = 3.3V when it's actually 3.25V → **1.5% systematic error** in all measurements

## VREFINT - Internal Voltage Reference

STM32 includes **VREFINT**, a factory-calibrated ~1.21V precision reference:
- Internal voltage source (no external pin needed)
- Temperature stable (±1mV over full range)
- Can be read via special ADC channel
- Factory calibration value stored in flash memory

### How VREFINT Calibration Works

**The Calibration Process:**

During manufacturing, STMicroelectronics:
1. Powers each chip with precise VDDA = 3.3V at 30°C
2. Reads the internal VREFINT (~1.21V) using the ADC
3. Stores this ADC reading in flash memory (called **VREFINT_CAL**)

During runtime, your firmware:
1. Reads VREFINT with current VDDA (which may not be exactly 3.3V)
2. Compares to factory calibration value
3. Calculates actual VDDA

**Formula:**
```c
// Constants (provided by manufacturer)
#define VREFINT_CAL_VREF 3300  // mV (VDDA during factory calibration)
uint16_t vrefint_cal = *VREFINT_CAL_ADDR;  // Factory calibration value

// Runtime measurement
uint32_t vrefint_raw = HAL_ADC_GetValue(&hadc3);  // Current VREFINT reading

// Calculate actual VDDA
vdda_mv = (VREFINT_CAL_VREF * vrefint_cal) / vrefint_raw;
```

**Example:**
- Factory calibration: VDDA = 3.3V → VREFINT reads 52428 counts
- Current reading: VREFINT reads 51200 counts
- Calculation: (3300 × 52428) / 51200 = 3378 mV (actual VDDA = 3.378V)

**Why it works:**
- VREFINT is a stable ~1.21V that doesn't change with VDDA
- If VDDA increases → ADC reading of VREFINT decreases (scale changes)
- If VDDA decreases → ADC reading of VREFINT increases
- By comparing current vs factory reading, we calculate the actual VDDA

**Key insight:** Both your signal AND VREFINT are measured by the same ADC with the same VDDA reference, so variations cancel out when calculating VDDA.

**Factory calibration addresses** (VREFINT_CAL):
- L476RG: `0x1FFF75AA` (calibrated at VDDA=3.0V, 30°C)
- H755ZI: `0x1FF1E860` (calibrated at VDDA=3.3V, 30°C)

## Implementation Options

### Option 1: Read Once at Startup, Send Calibration Packet
- Read VREFINT at startup → calculate VDDA
- Send special calibration packet before data packets
- **Problem:** Python app might connect later and miss the packet

### Option 2: Send Calibration Packet Periodically
- Read VREFINT once per second
- Send calibration packet every 5-10 seconds
- Python waits for calibration data after connecting
- **Overhead:** 0.005% CPU, one extra packet per 10 seconds

### Option 3: Include VDDA in Every Packet ✅ **IMPLEMENTED**
- Read VREFINT periodically (once per second via ADC3)
- Include VDDA value (2 bytes) in every data packet
- **Overhead:** 0.05% bandwidth (+2 bytes per 4012-byte packet)
- **Benefits:** Always works, no timing issues, real-time tracking
- **Implementation:** H755ZI-Q board only (ADC3 reads VREFINT channel)

### Option 4: Request/Response Protocol
- Python sends "REQUEST_CALIBRATION" command after connecting
- STM32 responds with calibration packet
- Requires bidirectional communication

## Performance Impact

Adding VREFINT calibration (Option 3):
```
Current system: 20,000 ADC conversions/sec
+ VREFINT: +1 conversion/sec = +0.005% CPU overhead

Packet size: 4010 → 4012 bytes (+2 bytes for vref_mv field)
Bandwidth overhead: +0.05%

UART timing: 43.6ms → 43.7ms per packet (+0.1ms)
System margin: 52ms available → 51.9ms after change
```

**Conclusion:** Negligible impact on system performance.

## Accuracy Improvement

| Method | Typical Error |
|--------|--------------|
| Assume 3.3V | ±4-5% |
| VREFINT calibration | ±1% |
| External precision reference (LM4040, REF5030) | ±0.1-0.5% |

## Industry Standards

**Consumer IoT:** Assume 3.3V (cost-sensitive, accuracy not critical)

**Industrial instruments:** VREFINT + periodic calibration (good accuracy, no extra cost)

**Medical/precision devices:** External precision voltage reference (highest accuracy, added cost)

**Power meter recommendation:** VREFINT calibration provides professional-grade accuracy (~1%) without additional hardware cost.

## Recommended Implementation

For this power meter project:
1. Read VREFINT once per second in STM32 firmware
2. Include VDDA value in every data packet (2 bytes after sample count)
3. Python receiver uses VDDA from packet for all voltage conversions
4. Improves accuracy from ~5% to ~1% with negligible overhead
