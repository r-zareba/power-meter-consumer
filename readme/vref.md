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

```c
// Read VREFINT using the same ADC that measures your signals
uint16_t vrefint_reading = ADC_Read_VREFINT();

// Calculate actual VDDA
VDDA_actual = (1.21V × 65535) / vrefint_reading

// Use VDDA_actual instead of assumed 3.3V
voltage = (adc_reading / 65535) × VDDA_actual
```

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

### Option 3: Include VDDA in Every Packet (Recommended)
- Read VREFINT periodically (e.g., once per second)
- Include VDDA value (2 bytes) in every data packet
- **Overhead:** 0.05% bandwidth (+2 bytes per 4010-byte packet)
- **Benefits:** Always works, no timing issues, real-time tracking

### Option 4: Request/Response Protocol
- Python sends "REQUEST_CALIBRATION" command after connecting
- STM32 responds with calibration packet
- Requires bidirectional communication

## Performance Impact

Adding VREFINT calibration (Option 3):
```
Current system: 20,000 ADC conversions/sec
+ VREFINT: +1 conversion/sec = +0.005% CPU overhead

Current packet: 4010 bytes
+ VDDA field: +2 bytes = +0.05% bandwidth overhead

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
