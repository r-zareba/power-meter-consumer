# Power Meter Consumer

Python application for receiving and analyzing dual-channel ADC data (voltage and current) from STM32 Nucleo boards.

## Supported Hardware

This project supports two STM32 Nucleo boards:

### 1. **STM32 Nucleo-L476RG**
- **ADC Resolution:** 12-bit (4096 levels)
- **CPU:** 80 MHz ARM Cortex-M4
- **RAM:** 128 KB
- **Compliance:** IEC 61000-4-30 Class S
- **Accuracy:** ±1-2% (with calibration)
- **Folder:** `stm32/L476RG/`

### 2. **STM32 Nucleo-H755ZI-Q**
- **ADC Resolution:** 16-bit (65536 levels)
- **CPU:** Dual-core - M7 @ 480 MHz + M4 @ 240 MHz
- **RAM:** 1 MB
- **Compliance:** IEC 61000-4-30 Class A capable
- **Accuracy:** ±0.2% (with certified sensors)
- **Folder:** `stm32/H755ZIQ/`

## Project Overview

This project implements a **dual simultaneous ADC sampling system** at 10.24kHz with DMA for data acquisition. Both voltage and current channels are sampled at exactly the same instant using hardware-synchronized ADC1 and ADC2 in dual mode, ensuring accurate power measurements and phase relationship analysis.

**Sampling frequency (10.24 kHz) is the IEC 61000-4-7 standard for 50Hz grids**, providing perfect 2048-sample (2^11) FFT windows for optimal harmonic analysis.

> **Note:** Actual sampling frequency is **10,256.41 Hz** (10.26 kHz) due to integer timer divider constraints. This 0.16% deviation from the ideal 10,240 Hz is negligible for power quality analysis and maintains perfect 2048-sample windows in ~199.6ms.

The sampled data is transmitted via UART to a laptop where Python software performs power quality analysis including:
- Real, reactive, and apparent power calculations
- Power factor and harmonic analysis
- IEC 61000-4-7 compliant measurements (200ms windows = 2,048 samples)
- Class A power quality monitoring per IEC 61000-4-30

---

## STM32 Configuration

### Start

For detailed STM32CubeMX configuration steps, refer to the board-specific guides:

- **📘 L476RG:** [L476RG_cubemx.md](readme/L476RG_cubemx.md) - Complete CubeMX setup for 12-bit @ 80 MHz
- **📗 H755ZI-Q:** [H755ZIQ_cubemx.md](readme/H755ZIQ_cubemx.md) - Complete CubeMX setup for 16-bit @ 200 MHz

### Hardware Pin Assignments

#### 📘 **L476RG Pin Configuration:**
```
CN8 Arduino Header (Analog):
Pin 1 (A0) → PA0  → ADC1_IN5   (Voltage sensor)
Pin 2 (A1) → PA1  → ADC2_IN6   (Current sensor)

Serial Communication:
PA2 → USART2_TX (ST-Link Virtual COM)
PA3 → USART2_RX (ST-Link Virtual COM)
```

#### 📗 **H755ZI-Q Pin Configuration:**
```
CN9 Arduino Header (Analog):
Pin 1 (A0) → PA0_C → ADC1_INP16 (Voltage sensor)
Pin 2 (A1) → PC0   → ADC2_INP10 (Current sensor)

Serial Communication:
PD8 → USART3_TX (ST-Link Virtual COM)
PD9 → USART3_RX (ST-Link Virtual COM)
```

### Configuration Summary

| Feature | L476RG | H755ZI-Q |
|---------|--------|----------|
| **ADC Resolution** | 12-bit (4096 levels) | 16-bit (65536 levels) |
| **System Clock** | 80 MHz | 200 MHz |
| **Timer Clock** | 80 MHz | 200 MHz |
| **ADC Clock** | 20 MHz | 64 MHz |
| **Sampling Rate** | 10.24 kHz (50Hz grids) | 10.24 kHz (50Hz grids) |
| **TIM6 Setup** | PSC=7, ARR=974 | PSC=24, ARR=194 |
| **Voltage Pin** | PA0 (ADC1_IN5) | PA0_C (ADC1_INP16) |
| **Current Pin** | PA1 (ADC2_IN6) | PC0 (ADC2_INP10) |
| **UART** | USART2 @ 921600 | USART3 @ 921600 |
| **UART Pins** | PA2/PA3 | PD8/PD9 |
| **DMA Mode** | Circular, 32-bit | Circular, 32-bit |

### Key Configuration Steps (Overview)

Both boards follow the same general configuration pattern:

1. **System Clock** - Configure for maximum performance (80 MHz or 200 MHz)
2. **TIM6** - Setup for 10 kHz ADC trigger rate
3. **GPIO** - Assign analog input pins
4. **DMA** - Configure circular 32-bit DMA for ADC1
5. **ADC1 & ADC2** - Configure dual simultaneous mode
6. **UART** - Setup 921600 baud for data transmission
7. **NVIC** - Enable interrupts with proper priorities

---

## Data Packet Protocol

### Why Protocol Needed

- **No structure in raw data:** PC cannot determine where packets start/end in continuous stream
- **Synchronization required:** After connection or data loss, receiver must find packet boundaries
- **Error detection essential:** Identify corrupted data from transmission errors
- **Metadata tracking:** Sequence numbers detect dropped packets, sample counts enable validation

### Protocol Design Goals

- **Simple STM32 implementation:** Minimal CPU overhead for real-time performance
- **Easy Python parsing:** Straightforward synchronization and extraction
- **Robust error detection:** CRC16 checksums and sequence tracking
- **Low overhead:** Maximize data throughput (~0.25% protocol overhead)
- **Unambiguous framing:** Sync markers distinguishable from ADC data

---

## VREF Calibration

The system uses **VREFINT** (internal voltage reference) on the H755ZI-Q board to measure actual VDDA and improve ADC accuracy

**Key points:**
- ADC3 reads VREFINT once per second
- Calculated VDDA (in millivolts) is included in every data packet
- Python receiver uses this for accurate voltage conversions
- No external components needed - fully automatic

For detailed information about VREFINT calibration, see [vref.md](readme/vref.md).

---

### Packet Structure

```
┌─────────────┬────────────┬──────────────┬──────────┬──────────────┬──────────────┬──────────┬─────────────┐
│ Start Marker│ Seq Number │ Sample Count │ VDDA (mV)│ Voltage Data │ Current Data │ Checksum │ End Marker  │
│   2 bytes   │  2 bytes   │   2 bytes    │ 2 bytes  │  N×2 bytes   │  N×2 bytes   │ 2 bytes  │  2 bytes    │
└─────────────┴────────────┴──────────────┴──────────┴──────────────┴──────────────┴──────────┴─────────────┘
     0xFFFF       uint16        uint16       uint16     uint16[N]      uint16[N]      CRC16        0xFFFE
                                            (3280 =   (ADC1-PA0)     (ADC2-PC0)
                                             3.28V)
```

### Field Descriptions

**1. Start Marker (2 bytes): 0xFFFF**
- Fixed pattern for packet synchronization
- Python searches for this pattern to find packet boundaries
- Little-endian: sent as 0xFF, 0xFF on wire

**2. Sequence Number (2 bytes): 0-65535**
- Increments for each packet
- Detects lost packets (gaps in sequence)
- Wraps around at 65536
- Enables verification of continuous streaming

**3. Sample Count (2 bytes): Number of samples per channel**
- Typically 1000 (for 100ms buffers at 10 kHz)
- Allows variable-length packets if needed
- Validation: should match expected buffer size
- Future flexibility for different buffer configurations

**4. VREF (2 bytes): ADC reference voltage in millivolts**
- Measured via VREFINT internal reference (updated every 1 second)
- Example: 3280 = 3.28V actual VDDA
- See [vref.md](readme/vref.md) for calibration details

**5. Voltage Data (N×2 bytes): ADC1 samples**
- Array of 16-bit ADC values from voltage sensor
- Little-endian format (LSB first)
- 12-bit data right-aligned (L476RG) or 16-bit (H755ZI-Q)
- Unpacked from lower 16 bits of dual ADC 32-bit words

**6. Current Data (N×2 bytes): ADC2 samples**
- Array of 16-bit ADC values from current sensor
- Little-endian format (LSB first)
- 12-bit data right-aligned (L476RG) or 16-bit (H755ZI-Q)
- Unpacked from upper 16 bits of dual ADC 32-bit words

**7. Checksum (2 bytes): CRC16**
- Validates data integrity (sequence, count, vdda, voltage, current)
- Detects transmission errors and corruption
- CRC16-ANSI polynomial for robust error detection

**8. End Marker (2 bytes): 0xFFFE**
- Confirms complete packet reception
- Different from start marker (aids debugging)
- Validates packet framing

### Protocol Overhead Analysis

- **Header:** 2 + 2 + 2 + 2 = 8 bytes
- **Trailer:** 2 + 2 = 4 bytes
- **Total overhead:** 12 bytes per packet
- **Example:** 1000 dual-channel samples = 2000 + 2000 + 12 = **4012 bytes** (~0.3% overhead)

### Synchronization Marker Safety Analysis

**Marker Values:**
- Start Marker: 0xFFFF = 65535 decimal
- End Marker: 0xFFFE = 65534 decimal

**12-bit ADC (L476RG):**
- Maximum value: 4095 (0x0FFF)
- **✅ PERFECTLY SAFE:** Markers 0xFFFF (65535) and 0xFFFE (65534) cannot occur in 12-bit ADC data
- **Collision probability:** 0% - mathematically impossible

**16-bit ADC (H755ZI-Q):**
- Maximum value: 65535 (0xFFFF)
- **✅ SAFE:** Markers only occur at sensor saturation (fault condition)
- **Risk analysis:** Sensors output centered signals around 1.65V (ADC ≈ 32768)
- **Typical range:** 32768 ± 20000 (approximately 12768 to 52768)
- **Markers 65535 and 65534:** Only at full-scale (3.3V) - indicates sensor fault
- **Collision probability:** ~0% in normal operation

### Solutions for 16-bit ADC Marker Collision

**Solution 1: Use Extreme Value Markers (RECOMMENDED)**

Change markers to values outside typical sensor range:

```
Start Marker: 0xFFFF (65535) - Maximum ADC value
End Marker:   0xFFFE (65534) - Near-maximum value
```

**Advantages:**
- **Simple implementation** - change two constants
- **Extremely low collision probability** - sensors rarely saturate at max values
- **Easy debugging** - still visible in hex dumps (all F's)
- **No overhead** - same packet structure
- **Backward compatible** - only marker values change

**Why these values are safe:**
- ADC reading 65535 means 3.3V (full-scale)
- Sensors output centered signals (VCC/2 ± variation)
- Full-scale (3.3V or 0V) indicates sensor malfunction or disconnection
- If these values appear in data, it's a legitimate fault condition worth flagging

**Implementation:**
```c
#define PACKET_START_MARKER  0xFFFF
#define PACKET_END_MARKER    0xFFFE
```

---

**Solution 2: COBS (Consistent Overhead Byte Stuffing)**

Encode packet data to guarantee no marker value appears:

**How COBS works:**
1. Choose marker (e.g., 0x00)
2. Encode data such that 0x00 never appears in payload
3. Use 0x00 as unambiguous packet delimiter
4. Decode on receiver side

**Advantages:**
- **Guaranteed no collisions** - mathematically impossible
- **Well-established algorithm** - proven in industrial protocols
- **Modest overhead** - ~0.4% for typical data

**Disadvantages:**
- **Increased complexity** - encoding/decoding required
- **CPU overhead** - processing time for encode/decode
- **Harder debugging** - data obfuscated during transmission

**Use when:** Maximum reliability required, CPU budget allows

---

**Solution 3: Byte Stuffing with Escape Sequences**

Insert escape byte when marker pattern appears in data:

**How it works:**
1. Define escape byte (e.g., 0xDB)
2. If data contains marker or escape byte, send: `0xDB + (original_byte XOR 0x20)`
3. Receiver detects 0xDB and reverses transformation

**Advantages:**
- **Simple concept** - easy to understand
- **Variable overhead** - only when collisions occur
- **Preserves debugging** - most data unchanged

**Disadvantages:**
- **Variable packet length** - complicates buffer management
- **Processing overhead** - scan entire packet
- **Potential 100% overhead** - worst case (rare)

**Use when:** Simple escape logic preferred over COBS

---

**Solution 4: Length-Based Framing (Hybrid Approach)**

Use sample count as primary framing, markers as secondary validation:

**How it works:**
1. Read start marker (0xFFFF)
2. Read sample count (e.g., 1000)
3. Calculate expected packet size: `6 + (1000×2) + (1000×2) + 4 = 4010 bytes`
4. Read exactly 4010 bytes from start marker
5. Validate end marker and CRC16

**Advantages:**
- **Tolerates marker collisions** - length determines boundaries
- **No encoding overhead** - raw data transmitted
- **Robust** - CRC16 catches any corruption

**Disadvantages:**
- **Synchronization harder** - if start marker missed, must search through data
- **Recovery slower** - need to find valid start marker + length + CRC combination

**Use when:** Markers less critical, CRC16 is primary validation

---

### Recommended Solution for H755ZI-Q

**Use Solution 1: Extreme Value Markers (0xFFFF / 0xFFFE)**

**Rationale:**
1. **Sensor physics:** Signals centered at 1.65V (ADC ≈ 32768), rarely reach extremes
2. **Fault detection:** If ADC reads 0xFFFF/0xFFFE, it indicates:
   - Sensor saturation (fault condition)
   - Disconnected sensor (should be detected anyway)
   - Power supply issue
3. **Simplicity:** Change two constants - no algorithm changes
4. **Debugging:** Pattern still easy to spot (all F's)
5. **Robustness:** CRC16 remains primary validation

**Implementation Priority:**
- **Primary validation:** CRC16 checksum (catches all corruption)
- **Secondary validation:** Sequence numbers (detects drops)
- **Tertiary validation:** Markers (framing aid, not critical)

**Fallback Plan:**
If extreme value markers still cause issues in practice:
1. Monitor collision frequency in production
2. If >1% collision rate, implement COBS (Solution 2)
3. COBS guarantees zero collisions with modest overhead

**Current Status:**
- **RECOMMENDED FOR BOTH BOARDS:** Use 0xFFFF/0xFFFE
  - L476RG (12-bit): Impossible to occur (max value 4095)
  - H755ZI-Q (16-bit): Extremely unlikely (only at sensor saturation)
- **Benefits of unified markers:**
  - Single protocol implementation for both boards
  - Same Python parser handles both
  - Simplified maintenance and testing
  - Maximum safety for both 12-bit and 16-bit ADC data

---

## UART Communication

### Baud Rate Selection

**Data Rate Requirements:**

**L476RG (12-bit dual-channel):**
- Sampling: 2 channels × 10 kHz × 2 bytes = 40 KB/s raw data
- Protocol overhead: +10 bytes per 1000 samples ≈ +0.1 KB/s
- **Total: ~40 KB/s**

**H755ZI-Q (16-bit dual-channel):**
- Sampling: 2 channels × 10 kHz × 2 bytes = 40 KB/s raw data
- Protocol overhead: +10 bytes per 1000 samples ≈ +0.1 KB/s
- **Total: ~40 KB/s**

### Baud Rate Options Comparison

| Baud Rate | Theoretical | Practical | Safety Margin | Recommendation |
|-----------|-------------|-----------|---------------|----------------|
| **460800** | 46 KB/s | ~38 KB/s | 0.95× | ❌ Too close, marginal |
| **921600** | 92 KB/s | ~80 KB/s | 2.0× | ✅ **RECOMMENDED** |
| **1000000** | 100 KB/s | ~87 KB/s | 2.2× | ✅ Good, non-standard |
| **1500000** | 150 KB/s | ~130 KB/s | 3.25× | ✅ Excellent |
| **2000000** | 200 KB/s | ~175 KB/s | 4.4× | ⚠️ Overkill, compatibility issues |

**Calculation (10 bits per byte: 1 start + 8 data + 1 stop):**
```
Theoretical: Baud_Rate / 10 bits = Bytes/s
Practical: ~87% of theoretical (accounting for overhead, processing)
```

### Selected Configuration: 921600 Baud

**Why 921600:**
- **Standard baud rate:** Well-supported by USB-UART converters and PC serial ports
- **2× safety margin:** Provides adequate headroom for both boards
- **Proven reliability:** Commonly used in embedded systems for high-speed data
- **Compatible:** Works with ST-Link virtual COM port without issues

**Why Not Higher:**
- **1000000+:** Non-standard, may not be supported by all USB-UART adapters
- **Clock divisor issues:** Some baud rates produce fractional divisors → timing errors
- **Compatibility:** 921600 is the highest widely-compatible standard rate

**Why Not Lower:**
- **460800:** Only ~0.95× headroom - insufficient safety margin
- **Risk of buffer overrun** if any transmission delays occur
- **No room for protocol expansion** or additional features

### UART Configuration

**Selected Peripheral:**
- **L476RG:** USART2 (connected to ST-Link virtual COM)
- **H755ZI-Q:** USART3 (connected to ST-Link virtual COM)

**Parameters:**
- **Baud Rate:** 921600 bits/s
- **Word Length:** 8 bits
- **Parity:** None (protocol CRC16 handles error detection)
- **Stop Bits:** 1
- **Flow Control:** None (sufficient margin, simple wiring)

**Why No Parity:**
- Adds 11 bits per byte instead of 10 (10% overhead)
- CRC16 in protocol provides superior error detection
- Maximizes throughput for given baud rate

**Why No Flow Control:**
- PC is always faster than STM32 transmission
- Simplified wiring (only TX, RX, GND needed)
- 2× safety margin eliminates need for hardware flow control
- Can enable RTS/CTS later if reliability issues arise

### Transmission Timing Analysis

**L476RG (2010 bytes per packet):**
```
Transmission time = 2010 bytes × 10 bits ÷ 921600 baud
                  = 20100 bits ÷ 921600 bits/s
                  ≈ 21.8 ms

Buffer interval: 100 ms (1000 samples at 10 kHz)
Margin: 100 - 21.8 = 78.2 ms ✓
```

**H755ZI-Q (4010 bytes per packet):**
```
Transmission time = 4010 bytes × 10 bits ÷ 921600 baud
                  = 40100 bits ÷ 921600 bits/s
                  ≈ 43.5 ms

Buffer interval: 100 ms
Margin: 100 - 43.5 = 56.5 ms ✓
```

### DMA vs Interrupt vs Blocking

**DMA (Recommended):**
- **Advantages:** CPU free during transmission, zero-copy, hardware-managed
- **Disadvantages:** More complex setup, requires DMA channel
- **Use when:** Real-time performance critical, CPU needs for other tasks

**Interrupt Mode:**
- **Advantages:** Less complex than DMA, CPU freed between bytes
- **Disadvantages:** Higher CPU overhead, interrupts per byte transmitted
- **Use when:** DMA unavailable, moderate performance acceptable

**Blocking Mode:**
- **Advantages:** Simplest implementation, no callback management
- **Disadvantages:** CPU blocked for entire transmission (21-43 ms)
- **Use when:** Debugging only, not recommended for production

**Selected: DMA Transmission**
- Non-blocking operation preserves real-time ADC acquisition
- Callback notification enables efficient double-buffering
- Essential for sustained continuous dual-channel streaming

### PC Serial Port Configuration

**Linux:**
- Device: `/dev/ttyACM0` (ST-Link virtual COM)
- Permissions: Add user to `dialout` group

**Windows:**
- Device: `COM3` (check Device Manager)
- Driver: ST-Link VCP driver (usually auto-installed)

**macOS:**
- Device: `/dev/cu.usbmodem14203` (number varies)
- Driver: Built-in CDC-ACM support

**Settings (all platforms):**
- Baud: 921600
- Data: 8 bits
- Parity: None
- Stop: 1 bit
- Flow: None

---

## DMA (Direct Memory Access)

### What is DMA?

DMA is a hardware feature that allows peripherals (ADC, UART) to transfer data directly to/from memory **without CPU involvement**. The CPU configures the transfer once, then the DMA controller handles all data movement autonomously, only notifying the CPU when complete via interrupts.

### Benefits

- **Zero CPU overhead during transfers** - CPU free for other tasks while data moves
- **Real-time performance** - Guaranteed timing without software delays
- **Efficient buffering** - Hardware double-buffering for continuous streaming
- **Lower power consumption** - CPU can sleep during transfers
- **Deterministic behavior** - No interrupt latency or software jitter

### DMA in This Project

**ADC DMA (Circular Mode):**
- **Configuration:** 2000-word circular buffer in RAM
- **Operation:** DMA automatically stores ADC1+ADC2 results as 32-bit words
- **Double buffering:** Half-complete and full-complete callbacks alternate
- **CPU involvement:** Only processes data in callbacks (~100ms intervals)
- **Benefit:** Continuous 10 kHz dual-channel sampling with <1% CPU load

**UART DMA (Normal Mode):**
- **Configuration:** Single packet buffer for transmission
- **Operation:** DMA streams packet to UART TX register automatically
- **Non-blocking:** CPU starts transfer and continues processing
- **CPU involvement:** Only in transmission-complete callback
- **Benefit:** 43.5ms UART transmission happens in background, CPU free for ADC processing

### Performance Impact

**Without DMA:**
- ADC: ~200 interrupts/second (per conversion) → 20% CPU load
- UART: ~40,000 byte-send operations/second → 30% CPU load
- **Total: ~50% CPU load** + interrupt overhead

**With DMA:**
- ADC: 20 callbacks/second (buffer half/complete) → <1% CPU load
- UART: 10 callbacks/second (packet complete) → <0.5% CPU load
- **Total: <2% CPU load** + 98% CPU available for analytics

This efficiency enables real-time power analysis, harmonic calculations, and future features like FFT processing without compromising sample rate.

---

## Key Design Decisions

**Buffer Size (1000 samples):**
- **Timing:** At 10 kHz sampling, 1000 samples = 100ms per buffer half
- **UART Transmission:** 4010 bytes @ 921600 baud ≈ 43.5ms transmission time
- **Safety Margin:** 56.5ms headroom prevents buffer overruns
- **IEC Compliance:** 200ms windows (2×100ms) align with IEC 61000-4-7 requirements
- **Memory:** 4010 bytes per packet fits comfortably in STM32 RAM

**Synchronization Markers (0xFFFF / 0xFFFE):**
- **All F's pattern** highly visible in hex dumps for debugging
- **Different start/end markers** aid packet validation and debugging
- **Extreme values** impossible for 12-bit ADC, extremely unlikely for 16-bit
- **Unified across boards** - same markers work safely for both L476RG and H755ZI-Q

**Dual-Channel Unpacking:**
- **DMA captures 32-bit words:** `[ADC2_current(31:16) | ADC1_voltage(15:0)]`
- **Separate arrays in packet:** Voltage and current unpacked into distinct 16-bit arrays
- **Phase accuracy preserved:** Simultaneous sampling maintained at hardware level
- **Simplifies analysis:** Python receives separate voltage/current arrays

**Error Detection:**
- **CRC16 checksum:** Validates sequence number, sample count, and all ADC data
- **Sequence numbers:** Detect dropped packets (0-65535 with wraparound)
- **End marker:** Confirms complete packet reception and framing
- **Multi-layer validation:** Marker + CRC16 + sequence provides robust error handling

**Memory Considerations:**
- **Static allocation preferred:** `static ADCPacket tx_packet;` (avoid stack overflow)
- **Struct packing:** Use `__attribute__((packed))` to prevent compiler padding
- **Buffer alignment:** Ensure DMA-compatible alignment for efficient transfers

**Timing Impact:**
```
Packet overhead: 10 bytes
L476RG (12-bit): 2000 bytes data + 10 bytes = 2010 bytes in ~21.8 ms
H755ZI-Q (16-bit): 4000 bytes data + 10 bytes = 4010 bytes in ~43.5 ms
Available time window: 100 ms (each buffer half)
Safety margin: L476RG: 78.2 ms, H755ZI-Q: 56.5 ms ✓
```

---

## Python Receiver Application

### Features

- Packet synchronization and parsing with CRC16 validation
- Sequence number tracking for dropped packet detection
- Dual-channel data reception (voltage and current)
- IEC 61000-4-7 compliant 200ms analysis windows
- Real-time statistics display (1-second averaging)
- Raw byte mode for debugging



**To change sensor hardware:** Edit these values in `src/config.py` to match your actual sensors and calibration. These settings are shared across the simulator, receiver, and analytics modules.

See [README_sensors.md](readme/README_sensors.md) for detailed sensor selection, configuration, and calibration.

---

## Usage

```bash
python src/main.py --port /dev/ttyACM0 --baud 921600
```

**Raw byte mode (for debugging):**
```bash
python src/main.py --port /dev/ttyACM0 --baud 921600 --raw
```


**Command-line arguments:**
- `--port` - Serial port device (default: /dev/ttyACM0)
- `--baud` - Baud rate (default: 921600)
- `--raw` - Display raw bytes instead of parsing packets (for debugging)


## System Architecture

```
┌─────────────┐  Timer    ┌──────────────┐  DMA   ┌────────────┐
│   TIM6      │─────────→ │  ADC1+ADC2   │───────→│ DMA Buffer │
│   10kHz     │  Trigger  │  Dual ADC    │ Auto   │  2000×32b  │
└─────────────┘           └──────────────┘        └────────────┘
                           (Simultaneous)          (V+I packed)
                                                    │
                                                    ↓ Callbacks
                                            ┌───────────────┐
                                            │  Double       │
                                            │  Buffering    │
                                            └───────────────┘
                                                    │
                                                    ↓
                                            ┌───────────────┐
                                            │  Dual-Channel │
                                            │  Unpacking    │
                                            └───────────────┘
                                                    │
                                                    ↓
                                            ┌───────────────┐
                                            │  Protocol     │
                                            │  Framing      │
                                            └───────────────┘
                                                    │
                                                    ↓ UART DMA
                                            ┌───────────────┐
                                            │  USART2/3     │
                                            │  921600 baud  │
                                            └───────────────┘
                                                    │
                                                    ↓ USB Virtual COM
                                            ┌───────────────┐
                                            │  Python       │
                                            │  pyserial     │
                                            └───────────────┘
                                                    │
                                                    ↓
                                    ┌───────────────┴───────────────┐
                                    ↓                               ↓
                            ┌───────────────┐              ┌────────────────┐
                            │  Real-time    │              │  Data Logging  │
                            │  Power        │              │  & Storage     │
                            │  Analysis     │              │  (V+I pairs)   │
                            └───────────────┘              └────────────────┘
```

### Performance Characteristics

- **Sampling rate:** 10,000 samples/second per channel (dual simultaneous)
- **Data rate:** ~40 KB/s raw data (2 channels × 10kHz × 2 bytes)
- **Packet rate:** ~44 KB/s (with protocol overhead)
- **Latency:** ~100ms per buffer
- **Reliability:** CRC16 checksums, sequence number tracking
- **Throughput:** Sustained continuous dual-channel streaming
- **Phase accuracy:** <10ns between voltage and current measurements (hardware-synchronized)

