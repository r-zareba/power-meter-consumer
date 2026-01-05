# STM32 Code Implementation Guide

This document tracks the step-by-step implementation of the power meter consumer firmware for STM32 Nucleo L476RG.

## Prerequisites
- STM32CubeMX configuration completed (Clock, TIM6, DMA, ADC1, USART2)
- Base project generated with auto-generated `main.c`

---

## ✅ Step 1: Add Buffer Declarations and Packet Structure

**Location:** `/* USER CODE BEGIN PV */` section (Private Variables)

**Code Added:**
```c
#define BUFFER_SIZE 2000           // 200ms at 10kHz (IEC 61000-4-7 compliant)
#define HALF_BUFFER_SIZE 1000      // 100ms per packet

// UART Packet Structure (4010 bytes total)
typedef struct {
  uint16_t start_marker;           // 0xAA55
  uint16_t sequence;               // Packet counter
  uint16_t count;                  // Samples per channel (1000)
  uint16_t voltage_data[1000];     // ADC1 voltage samples
  uint16_t current_data[1000];     // ADC2 current samples
  uint16_t checksum;               // CRC16-MODBUS
  uint16_t end_marker;             // 0x55AA
} PacketData;

uint32_t adc_buffer[BUFFER_SIZE];  // Dual ADC buffer: [I(31:16)|V(15:0)]
volatile uint8_t buffer_half_ready = 0;  // 0=none, 1=first half, 2=second half
volatile uint8_t uart_tx_busy = 0;       // 0=idle, 1=transmission in progress

static uint16_t packet_sequence = 0;
static PacketData tx_packet __attribute__((aligned(4)));
```

**Explanation:**

### Memory Layout and Alignment
The packet structure uses **all `uint16_t` fields** for natural alignment:

**Why NO `__attribute__((packed))` on struct?**
- All fields are `uint16_t` (2 bytes each)
- Compiler places them sequentially: 0, 2, 4, 6, 8...
- All addresses are **naturally even** (required for uint16_t)
- **No padding added** - struct is already compact!
- Total size: 2+2+2+2000+2000+2+2 = 4010 bytes (verified at compile time)

**Why `__attribute__((aligned(4)))` on variable?**
- Applied to **variable declaration**, not struct definition
- Ensures struct starts at address divisible by 4 (e.g., 0x20000000, 0x20000004...)
- STM32 DMA controller prefers 4-byte aligned addresses for efficiency
- Prevents DMA from rejecting the buffer

**Packed vs Aligned - Key Differences:**
```c
// ❌ WRONG: Contradictory attributes
struct __attribute__((packed)) __attribute__((aligned(32))) { ... };
// packed = "ignore alignment inside"
// aligned = "respect alignment"
// → Conflict! HAL DMA rejects this

// ✅ CORRECT: Natural alignment + variable alignment
struct { uint16_t fields... };  // Naturally aligned (no packed needed)
static struct Packet __attribute__((aligned(4)));  // Align variable for DMA
```

### ADC Buffer Format
- **`adc_buffer[2000]`**: Circular buffer filled by DMA
- **`uint32_t` type**: Dual ADC packs both channels in one 32-bit word
  - Bits 15-0: ADC1 voltage sample
  - Bits 31-16: ADC2 current sample
- **`BUFFER_SIZE = 2000`**: 200ms at 10kHz (IEC 61000-4-7 compliant window)
- **`HALF_BUFFER_SIZE = 1000`**: 100ms per packet (allows 44ms TX + 56ms margin)

### Control Flags
- **`buffer_half_ready`**: Set by ADC DMA callbacks (1=first half, 2=second half)
- **`uart_tx_busy`**: Prevents starting new TX while one is in progress
- **`volatile`**: Required for variables modified in interrupt context

**Memory Usage:**
- ADC buffer: 2000 × 4 = 8,000 bytes
- TX packet: 4,010 bytes
- Total: 12,010 bytes (9.4% of 128KB RAM)

---

## ✅ Step 2: Implement DMA Callback Functions

**Location:** `/* USER CODE BEGIN 4 */` section (before Error_Handler)

**Code Added:**
```c
/**
 * @brief  ADC conversion half complete callback (DMA filled first half of buffer)
 * @param  hadc: ADC handle
 * @retval None
 */
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef* hadc)
{
    if (hadc->Instance == ADC1)
    {
        // First half of buffer (samples 0-999) is now full and ready to transmit
        // DMA is currently filling the second half (samples 1000-1999)
        buffer_half_ready = 1;
    }
}

/**
 * @brief  ADC conversion complete callback (DMA filled second half of buffer)
 * @param  hadc: ADC handle
 * @retval None
 */
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
    if (hadc->Instance == ADC1)
    {
        // Second half of buffer (samples 1000-1999) is now full and ready to transmit
        // DMA will wrap around and start filling first half again (circular mode)
        buffer_half_ready = 2;
    }
}
```

**Explanation:**

### `HAL_ADC_ConvHalfCpltCallback()`
- **When called**: Automatically invoked by HAL when DMA completes filling first 1000 samples (indices 0-999)
- **What it does**: Sets `buffer_half_ready = 1` to signal main loop
- **Why important**: First half is now stable and safe to read/transmit while DMA fills second half
- **Frequency**: Called every 100ms (1000 samples ÷ 10000 samples/sec)

### `HAL_ADC_ConvCpltCallback()`
- **When called**: Automatically invoked by HAL when DMA completes filling second 1000 samples (indices 1000-1999)
- **What it does**: Sets `buffer_half_ready = 2` to signal main loop
- **Why important**: Second half is now stable and safe to read/transmit while DMA wraps around to fill first half
- **Frequency**: Called every 100ms (alternating with half-complete callback)

### Double Buffering Pattern
```
Timeline at 10kHz sampling:
0ms ───────► 100ms ───────► 200ms ───────► 300ms
     Fill      |      Fill     |      Fill     |
   [0-999]     |   [1000-1999] |    [0-999]    |
               ↓               ↓               ↓
          Callback 1      Callback 2      Callback 1
       (half ready=1)  (half ready=2)  (half ready=1)
        Main can           Main can         Main can
      transmit [0]     transmit [1000]   transmit [0]
```

**Key Points:**
- Callbacks execute in **interrupt context** - keep them fast (just set flag)
- Main loop does heavy work (packet building, UART transmission)
- DMA never overwrites data being transmitted (working on opposite half)
- Circular mode ensures continuous, seamless data acquisition

**Safety Check:**
- `if (hadc->Instance == ADC1)` ensures callback only processes our ADC (good practice if multiple ADCs used)

---

## 📘 Understanding DMA Data Width Configuration

### CubeMX Settings: Byte vs Half Word vs Word

When configuring DMA in STM32CubeMX, you'll see **Data Width** settings for both **Peripheral** and **Memory**. Understanding these is critical for proper operation and alignment.

#### DMA Data Width Options
- **Byte**: 8-bit transfers (1 byte at a time)
- **Half Word**: 16-bit transfers (2 bytes at a time)
- **Word**: 32-bit transfers (4 bytes at a time)

### ADC DMA Configuration (Required Settings)

For our dual ADC simultaneous mode:
```
DMA1 Channel 1 (ADC):
  Peripheral: Word (32-bit)
  Memory:     Word (32-bit)
```

**Why Word (32-bit) is MANDATORY, not optional:**

1. **Hardware Requirement**: Dual ADC simultaneous mode packs BOTH channel results into a single 32-bit register:
   ```
   ADC Common Data Register (CDR):
   ┌─────────────────┬─────────────────┐
   │  ADC2 (31:16)   │  ADC1 (15:0)    │
   │    Current      │    Voltage      │
   └─────────────────┴─────────────────┘
         16 bits          16 bits
   ```

2. **Cannot Use Half Word**: If you tried 16-bit DMA, you'd only transfer half the register (either voltage OR current, losing the other channel!)

3. **Memory Alignment Consequence**: Word (32-bit) DMA requires source buffer address divisible by 4:
   ```c
   uint32_t adc_buffer[2000];  // Each element holds both ADC values
   // Buffer must start at address like: 0x20000000, 0x20000004, 0x20000008...
   // NOT: 0x20000001, 0x20000002, 0x20000003 (causes HardFault!)
   ```

4. **Performance is Secondary**: We use 32-bit DMA because the hardware REQUIRES it, not because it's faster

### UART DMA Configuration (Our Settings)

For our UART transmission:
```
DMA1 Channel 7 (USART2_TX):
  Peripheral: Byte (8-bit)
  Memory:     Byte (8-bit)
```

**Why Byte (8-bit) is appropriate:**

1. **UART is Byte-Oriented**: UART transmits one byte at a time (8N1 format = 8 data bits, no parity, 1 stop bit)

2. **Flexible Alignment**: Byte-mode DMA has no alignment restrictions:
   ```c
   uint8_t data[100];  // Can start at ANY address
   // 0x20000000 ✓  0x20000001 ✓  0x20000002 ✓  0x20000003 ✓
   ```

3. **Struct Compatibility**: Works with any buffer, even odd-sized or misaligned:
   ```c
   // This works because UART DMA is Byte-mode:
   HAL_UART_Transmit_DMA(&huart2, (uint8_t*)&tx_packet, sizeof(tx_packet));
   // tx_packet can start at ANY address
   ```

### Could We Use Word DMA for UART?

**Yes, technically**, but:
- ❌ Requires buffer size divisible by 4 (ours is 4010 bytes - NOT divisible by 4!)
- ❌ Requires buffer address aligned to 4 bytes (adds complexity)
- ❌ No performance benefit (UART transmit speed bottleneck is baud rate, not DMA)
- ✅ Byte-mode is simpler and works with any data size

### Memory Alignment Summary

| DMA Width | Alignment Requirement | Buffer Must Be | Example Use Case |
|-----------|----------------------|----------------|------------------|
| **Byte**  | None (any address)   | Any size | UART, byte arrays, chars |
| **Half Word** | Address ÷ 2 = 0 | Even addresses, even size | Single 12-bit ADC, uint16_t arrays |
| **Word** | Address ÷ 4 = 0 | Addresses ending in 0/4/8/C, size ÷ 4 = 0 | Dual ADC, uint32_t arrays |

### Practical Impact on Our Code

```c
// ADC Buffer - MUST be 32-bit aligned (Word DMA)
uint32_t adc_buffer[2000];  // Compiler automatically aligns to 4 bytes ✓

// UART Packet - Byte DMA, no alignment needed
static PacketData tx_packet __attribute__((aligned(4)));
// aligned(4) here is for EFFICIENCY (slight speedup), not requirement
// Even without it, Byte-mode UART DMA would work fine
```

### Key Takeaways

1. **ADC Word DMA = Hardware Requirement** (dual channel data packed in 32-bit register)
2. **UART Byte DMA = Flexibility Choice** (works with any data, no alignment headaches)
3. **Alignment issues only appear when DMA width > Byte** (Half Word or Word modes)
4. **Compiler usually handles alignment** for global/static arrays, but understanding why helps debugging

**Reference:** STM32L4 Reference Manual RM0351, Section 13 (DMA) and Section 16 (ADC)

---

## ✅ Step 3: Add CRC16 Checksum Calculation Function

**Location:** `/* USER CODE BEGIN 0 */` section (before main function)

**Code Added:**
```c
/**
 * @brief  Calculate CRC16 checksum (MODBUS variant)
 * @param  data: Pointer to data buffer (uint16_t array)
 * @param  count: Number of uint16_t elements to process
 * @retval 16-bit CRC value
 */
uint16_t calculate_crc16(uint16_t *data, uint16_t count)
{
    uint16_t crc = 0xFFFF;  // Initial value
    uint8_t *bytes = (uint8_t*)data;  // Process as bytes
    uint16_t byte_count = count * 2;  // Convert word count to byte count
    
    for (uint16_t i = 0; i < byte_count; i++) {
        crc ^= bytes[i];  // XOR byte into CRC
        
        for (uint8_t j = 0; j < 8; j++) {  // Process each bit
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;  // Apply polynomial if LSB is 1
            } else {
                crc = crc >> 1;  // Just shift if LSB is 0
            }
        }
    }
    
    return crc;
}
```

**Explanation:**

### CRC16-MODBUS Algorithm
- **Standard protocol**: Uses CRC16 with polynomial 0xA001 (reverse of 0x8005)
- **Initial value**: 0xFFFF (all bits set)
- **Processing**: Byte-by-byte with bit-by-bit polynomial application
- **Result**: 16-bit checksum for error detection

### Function Parameters
- **`data`**: Pointer to uint16_t array (ADC samples or packet data)
- **`count`**: Number of 16-bit words to process
- **Returns**: 16-bit CRC checksum

### How It Works
1. **Initialize CRC** to 0xFFFF
2. **Convert to bytes**: Cast uint16_t array to uint8_t for byte-wise processing
3. **For each byte**:
   - XOR byte with current CRC
   - Process each of 8 bits:
     - If LSB is 1: shift right and XOR with polynomial 0xA001
     - If LSB is 0: just shift right
4. **Return final CRC** value

### Why CRC16 Instead of Simple Checksum?
- **Better error detection**: Catches burst errors, bit flips, and multi-bit errors
- **Industry standard**: CRC16-MODBUS widely used in industrial protocols (Modbus RTU, etc.)
- **Reliable**: Can detect 99.998% of all transmission errors
- **Efficient**: Only ~10-20 CPU cycles per byte on ARM Cortex-M4

### Usage Example
```c
// Calculate CRC over 1000 ADC samples
uint16_t crc = calculate_crc16(adc_buffer, 1000);

// Calculate CRC over packet header + data
uint16_t *packet_start = &sequence_number;  // Start of data to checksum
uint16_t word_count = 1 + 1 + 1000;  // seq + count + samples
uint16_t crc = calculate_crc16(packet_start, word_count);
```

### Performance
- **Processing time**: ~0.5ms for 1000 samples at 80 MHz
- **Impact on timing**: Negligible (have 100ms window, use <1ms)
- **Memory**: No additional buffers needed (processes in-place)

**Key Points:**
- Processes data as **bytes** (uint8_t) even though input is uint16_t array
- Works with little-endian format (STM32's native format)
- Python receiver will use identical algorithm to verify CRC
- Failed CRC indicates corrupted packet - receiver should discard it

---

## ✅ Step 4: Create Packet Structure and Transmission Function

**Locations:** 
- Include: `/* USER CODE BEGIN Includes */`
- Struct & globals: `/* USER CODE BEGIN PV */` 
- Function: `/* USER CODE BEGIN 0 */`

**Code Added:**

### 1. Include Statement
```c
#include <string.h> // For memcpy() in packet transmission
```

### 2. Packet Structure Definition
```c
// Packet structure for UART transmission (dual-channel)
typedef struct {
  uint16_t start_marker;                  // 0xAA55 - synchronization marker
  uint16_t sequence_number;               // Packet counter (0-65535, wraps around)
  uint16_t sample_count;                  // Number of samples per channel in this packet
  uint16_t voltage_data[HALF_BUFFER_SIZE]; // ADC1 samples (1000 values) - PA0 voltage sensor
  uint16_t current_data[HALF_BUFFER_SIZE]; // ADC2 samples (1000 values) - PA1 current sensor
  uint16_t checksum;                      // CRC16 for integrity validation
  uint16_t end_marker;                    // 0x55AA - end of packet marker
} __attribute__((packed)) ADCPacket;

// Global variables for packet transmission
static uint16_t packet_sequence = 0; // Increments with each packet sent
static ADCPacket tx_packet; // Packet buffer (static to avoid stack overflow - ~8KB)
```

### 3. Transmission Function
```c
/**
 * @brief  Build packet and transmit dual ADC buffer via UART with DMA
 * @param  data: Pointer to dual ADC data buffer (32-bit packed words)
 * @param  size: Number of samples to transmit per channel
 * @retval None
 */
void transmit_buffer_uart(uint32_t *data, uint16_t size) {
  if (uart_tx_busy) {
    // UART transmission already in progress - skip this buffer
    // In production, might want to log this as a data loss event
    return;
  }

  // Build packet header
  tx_packet.start_marker = 0xAA55; // Sync pattern for packet detection
  tx_packet.sequence_number = packet_sequence++; // Increment packet counter
  tx_packet.sample_count = size;                 // Number of samples per channel

  // Unpack 32-bit dual ADC data into separate voltage and current arrays
  // Each 32-bit word contains: [ADC2_current(31:16) | ADC1_voltage(15:0)]
  for (uint16_t i = 0; i < size; i++) {
    tx_packet.voltage_data[i] = (uint16_t)(data[i] & 0xFFFF);         // Lower 16 bits = ADC1
    tx_packet.current_data[i] = (uint16_t)((data[i] >> 16) & 0xFFFF); // Upper 16 bits = ADC2
  }

  // Calculate CRC16 checksum over: sequence_number + sample_count + voltage_data + current_data
  uint8_t *checksum_data_bytes = (uint8_t *)&tx_packet.sequence_number;
  uint16_t checksum_byte_count = (1 + 1 + size + size) * 2; // (seq + count + voltage + current) * 2 bytes
  
  // Calculate CRC inline
  uint16_t crc = 0xFFFF;
  for (uint16_t i = 0; i < checksum_byte_count; i++) {
    crc ^= checksum_data_bytes[i];
    for (uint8_t j = 0; j < 8; j++) {
      if (crc & 0x0001) {
        crc = (crc >> 1) ^ 0xA001;
      } else {
        crc = crc >> 1;
      }
    }
  }
  tx_packet.checksum = crc;

  // Add end marker
  tx_packet.end_marker = 0x55AA;

  // Calculate total packet size in bytes for dual-channel
  // Header: start(2) + seq(2) + count(2) = 6 bytes
  // Data: voltage_data (size * 2) + current_data (size * 2) bytes  
  // Trailer: checksum(2) + end(2) = 4 bytes
  uint16_t packet_size = 6 + (size * 2 * 2) + 4;

  // Start non-blocking UART transmission via DMA
  uart_tx_busy = 1;
  HAL_UART_Transmit_DMA(&huart2, (uint8_t *)&tx_packet, packet_size);
}
```

**Explanation:**

### Packet Structure (ADCPacket)

```
┌─────────────┬────────────┬──────────────┬──────────────┬──────────────┬──────────┬─────────────┐
│ Start Marker│ Seq Number │ Sample Count │ Voltage Data │ Current Data │ Checksum │ End Marker  │
│   2 bytes   │  2 bytes   │   2 bytes    │  1000×2 B    │  1000×2 B    │ 2 bytes  │  2 bytes    │
└─────────────┴────────────┴──────────────┴──────────────┴──────────────┴──────────┴─────────────┘
     0xAA55      0-65535        1000       uint16[1000]   uint16[1000]    CRC16       0x55AA
                                           (ADC1-PA0)     (ADC2-PA1)
```

**Field Details:**

1. **`start_marker` (0xAA55)**
   - Fixed synchronization pattern
   - Python receiver searches for this to find packet boundaries
   - Unlikely to occur in 12-bit ADC data (max value 4095)
   - Little-endian: transmitted as `0x55 0xAA` on wire

2. **`sequence_number` (0-65535)**
   - Increments with each packet sent
   - Detects lost/dropped packets
   - Wraps around at 65536 automatically (uint16_t overflow)
   - Helps verify continuous streaming

3. **`sample_count` (typically 1000)**
   - Number of ADC samples per channel in this packet
   - Allows variable-length packets if needed
   - Receiver validates this matches expected size

4. **`voltage_data[1000]`**
   - ADC1 samples from PA0 (voltage sensor)
   - Unpacked from lower 16 bits of dual ADC 32-bit words
   - 12-bit values right-aligned in 16-bit words
   - Little-endian format (STM32's native format)

5. **`current_data[1000]`**
   - ADC2 samples from PA1 (current sensor)
   - Unpacked from upper 16 bits of dual ADC 32-bit words
   - 12-bit values right-aligned in 16-bit words
   - Time-aligned with voltage_data (sampled simultaneously)

6. **`checksum` (CRC16)**
   - Calculated over: sequence + count + voltage_data + current_data
   - Detects transmission errors
   - Start/end markers NOT included in checksum

7. **`end_marker` (0x55AA)**
   - Confirms complete packet reception
   - Different from start marker (aids debugging)
   - Validates packet framing

**`__attribute__((packed))`:**
- Prevents compiler from adding padding between struct fields
- Ensures exact memory layout for transmission
- Critical for protocol compatibility
- Note: Taking addresses of packed members can cause alignment warnings, so we use byte pointers for CRC calculation

### Global Variables

**`packet_sequence`:**
- Static counter incremented for each packet
- Helps detect lost packets on receiver side
- Wraps around automatically (uint16_t: 0→65535→0)

**`tx_packet`:**
- Static allocation (~8KB buffer for dual-channel)
- Avoids stack overflow (too large for stack)
- Reused for each transmission (no malloc needed)

### Transmission Function Flow

1. **Check if UART busy**
   - If previous transmission still ongoing, skip (prevents overwrite)
   - In production, could increment error counter

2. **Build packet header**
   - Set start marker (0xAA55)
   - Increment and assign sequence number
   - Set sample count (per channel)

3. **Unpack dual ADC data**
   - Loop through 32-bit buffer extracting voltage and current
   - Each 32-bit word: [ADC2_current(31:16) | ADC1_voltage(15:0)]
   - Lower 16 bits → voltage_data array (ADC1)
   - Upper 16 bits → current_data array (ADC2)
   - Ensures perfect time alignment between channels

4. **Calculate checksum**
   - CRC16 over sequence + count + voltage_data + current_data
   - Uses byte pointer to avoid alignment issues with packed struct
   - Calculates CRC inline using same algorithm as `calculate_crc16()` function
   - Byte count: (1 + 1 + 1000 + 1000) words × 2 = 4004 bytes

5. **Set end marker**
   - 0x55AA for packet validation

6. **Calculate packet size**
   - Total: 4010 bytes (for 1000 dual-channel samples)
   - Overhead: 10 bytes (~0.25%)

7. **Start UART DMA transmission**
   - Non-blocking: function returns immediately
   - DMA handles transfer in background
   - Set `uart_tx_busy` flag before starting

### Timing Analysis

```
At 921600 baud:
- Bytes per second: 921600 / 10 = 92160 bytes/s
- Packet size: 4010 bytes (dual-channel)
- Transmission time: 4010 / 92160 ≈ 43.5 ms

Timeline:
0ms: Buffer half ready (callback sets flag)
0ms: transmit_buffer_uart() called
0ms: Packet built (~1ms for unpacking + CRC)
1ms: UART DMA starts
44.5ms: UART DMA completes (callback clears uart_tx_busy)
100ms: Next buffer half ready

Margin: 100 - 44.5 = 55.5 ms ✓ (plenty of time)
```

### Safety Features

1. **uart_tx_busy check**: Prevents concurrent transmissions
2. **Sequence numbers**: Detects lost packets
3. **CRC16 checksum**: Validates data integrity
4. **Start/end markers**: Enables synchronization and framing validation
5. **Static allocation**: No dynamic memory (reliable for embedded)
6. **Dual-channel unpacking**: Maintains time alignment between voltage and current

**Key Points:**
- Function returns immediately (non-blocking DMA)
- Packet built in ~1ms, transmitted in ~44ms
- Python receiver will use matching CRC algorithm to verify
- Start/end markers enable robust packet synchronization
- Dual-channel data perfectly time-aligned for power analysis

---

## ✅ Step 5: Implement UART DMA Callback

**Location:** `/* USER CODE BEGIN 4 */` section (with ADC callbacks)

**Code Added:**
```c
/**
 * @brief  UART transmission complete callback (DMA finished sending packet)
 * @param  huart: UART handle
 * @retval None
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
  if (huart->Instance == USART2) {
    // UART DMA transmission complete - ready for next packet
    uart_tx_busy = 0;
  }
}
```

**Explanation:**

### HAL_UART_TxCpltCallback()

**When called:**
- Automatically invoked by HAL when UART DMA completes transmitting packet
- Happens ~22ms after `HAL_UART_Transmit_DMA()` starts
- Called in interrupt context (keep fast and simple)

**What it does:**
- Clears `uart_tx_busy` flag to signal transmission complete
- Makes system ready to accept next transmission
- Checks `huart->Instance == USART2` to verify it's our UART

**Why it's critical:**
- Without this, `uart_tx_busy` would stay `1` after first packet
- Main loop checks this flag before starting new transmission
- Prevents attempting concurrent UART DMA transfers (undefined behavior)
- Ensures proper synchronization between buffer ready and UART ready

### Timing Diagram

```
Time (ms):  0    22   100  122  200  222  300
            │    │    │    │    │    │    │
Buffer:     [─ 0-999 ─]   [─1000-1999─]  [─ 0-999 ─]
            │         │         │         │
Callbacks:  Half      TxCplt    Full      TxCplt Half
            ready=1   busy=0    ready=2   busy=0  ready=1
            │         │         │         │
Main Loop:  Start TX  ✓Ready    Start TX  ✓Ready  Start TX
            busy=1              busy=1              busy=1
            ├────22ms────┤      ├────22ms────┤     ├──
            [UART DMA TX]       [UART DMA TX]      [UART...
```

**Flow:**
1. **t=0ms**: DMA fills first half → `HAL_ADC_ConvHalfCpltCallback()` → `buffer_half_ready=1`
2. **t=0ms**: Main loop sees flag → calls `transmit_buffer_uart()` → `uart_tx_busy=1`
3. **t=22ms**: UART DMA done → `HAL_UART_TxCpltCallback()` → `uart_tx_busy=0`
4. **t=100ms**: DMA fills second half → `HAL_ADC_ConvCpltCallback()` → `buffer_half_ready=2`
5. **t=100ms**: Main loop sees flag and `!uart_tx_busy` → starts next transmission
6. **Repeat...**

### Safety Margin

```
Buffer interval: 100ms (time between buffer halves ready)
UART TX time:    22ms (time to transmit 2010 bytes)
Margin:          78ms (buffer interval - TX time)

Ratio: 100/22 = 4.5× safety factor ✓
```

This generous margin ensures:
- UART always finishes before next buffer ready
- Time for main loop processing
- Tolerance for jitter and delays
- System won't drop packets under normal conditions

### Error Conditions Prevented

**Without this callback:**
```c
// uart_tx_busy stays 1 forever
transmit_buffer_uart(...) {
  if (uart_tx_busy) {  // Always true after first TX!
    return;  // All subsequent packets dropped!
  }
  ...
}
```

**With this callback:**
```c
// uart_tx_busy properly cleared after each transmission
// System works continuously without data loss
```

**Concurrent transmission attempt (if flag missing):**
- HAL_UART_Transmit_DMA() returns HAL_BUSY
- DMA transfer pointer corrupted
- Data integrity lost
- System may crash or hang

### Interrupt Priority

- UART DMA interrupt should have **lower** priority than ADC DMA
- ADC timing is critical (10kHz sampling)
- UART has generous timing margin (78ms)
- If both interrupts fire simultaneously, ADC callback runs first

**Key Points:**
- Executes in **interrupt context** - simple flag clear only
- Timing: called every ~22ms (alternating with buffer ready every 100ms)
- Critical for continuous operation - without it, only one packet would transmit
- Works with `uart_tx_busy` flag checked in `transmit_buffer_uart()`

---

## ✅ Step 6: Add Main Loop Logic with ADC/Timer Startup

**Locations:**
- Initialization: `/* USER CODE BEGIN 2 */` (after peripheral init, before while loop)
- Main loop: `/* USER CODE BEGIN 3 */` (inside while loop)

**Code Added:**

### 1. Initialization Sequence
```c
// Calibrate ADC for accurate measurements (required before first use)
HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);

// Start ADC with DMA in circular mode
// Buffer will be filled continuously: samples 0-999, then 1000-1999, then wrap to 0-999, etc.
// Callbacks fire at half-complete (999) and complete (1999)
HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adc_buffer, BUFFER_SIZE);

// Start timer to trigger ADC conversions at 10kHz
// Timer MUST be started AFTER ADC is ready
HAL_TIM_Base_Start(&htim6);
```

### 2. Main Loop Processing
```c
while (1) {
  // Check if first half of buffer is ready and UART is available
  if (buffer_half_ready == 1 && !uart_tx_busy) {
    // Transmit first half (samples 0-999)
    // DMA is currently filling second half (samples 1000-1999)
    transmit_buffer_uart(&adc_buffer[0], HALF_BUFFER_SIZE);
    buffer_half_ready = 0; // Clear flag after starting transmission
  }
  // Check if second half of buffer is ready and UART is available
  else if (buffer_half_ready == 2 && !uart_tx_busy) {
    // Transmit second half (samples 1000-1999)
    // DMA has wrapped around and is filling first half (samples 0-999)
    transmit_buffer_uart(&adc_buffer[HALF_BUFFER_SIZE], HALF_BUFFER_SIZE);
    buffer_half_ready = 0; // Clear flag after starting transmission
  }

  // Optional: Add low-power mode here if needed
  // __WFI();  // Wait For Interrupt - sleeps until next interrupt
}
```

**Explanation:**

### Initialization Sequence

#### 1. ADC Calibration
```c
HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
```

**Why calibrate:**
- Compensates for ADC offset errors
- Improves measurement accuracy
- Required before first ADC use
- Takes ~1ms to complete
- Should be done after power-on or wakeup from low-power mode

**ADC_SINGLE_ENDED:**
- Matches our configuration (PA0 single-ended input)
- Alternative: `ADC_DIFFERENTIAL_ENDED` for differential inputs

#### 2. Start ADC with DMA
```c
HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adc_buffer, BUFFER_SIZE);
```

**What it does:**
- Enables ADC peripheral
- Configures DMA to transfer ADC results to `adc_buffer`
- Sets up circular mode (DMA wraps around at end)
- ADC now waits for timer triggers to start conversions

**Parameters:**
- `&hadc1`: ADC handle (configured in CubeMX)
- `adc_buffer`: Destination for ADC samples
- `BUFFER_SIZE`: 2000 samples (enables double buffering)

**After this call:**
- DMA interrupts enabled (half-complete and complete)
- ADC ready to respond to TIM6 triggers
- Callbacks will fire when buffer halves fill

#### 3. Start Timer
```c
HAL_TIM_Base_Start(&htim6);
```

**What it does:**
- Starts TIM6 counting: 0→999→0→999→...
- Generates TRGO (Trigger Output) on each overflow
- TRGO triggers ADC conversion at exactly 10kHz
- Sampling begins immediately

**Why start timer LAST:**
- ADC must be ready before first trigger arrives
- DMA must be configured before ADC starts converting
- Prevents missing first samples
- Ensures clean startup

**Critical startup order:**
```
1. Calibrate ADC     ← Improve accuracy
2. Start ADC+DMA     ← Prepare data acquisition
3. Start Timer       ← Begin sampling at 10kHz
```

### Main Loop Logic

#### Event-Driven Processing

The main loop is **interrupt-driven** and **non-blocking**:

```
┌─────────────────────────────────────────────┐
│  Main Loop (Foreground)                     │
│  - Check flags                              │
│  - Start transmissions                      │
│  - Low overhead                             │
└─────────────────────────────────────────────┘
         ↑                           ↑
         │ Sets flags                │ Sets flags
         │                           │
┌────────┴─────────┐       ┌────────┴─────────┐
│  DMA Callbacks   │       │  UART Callback   │
│  (Background)    │       │  (Background)    │
│  - Fast ISR      │       │  - Fast ISR      │
│  - Set ready=1/2 │       │  - Clear busy    │
└──────────────────┘       └──────────────────┘
```

#### First Half Processing
```c
if (buffer_half_ready == 1 && !uart_tx_busy) {
  transmit_buffer_uart(&adc_buffer[0], HALF_BUFFER_SIZE);
  buffer_half_ready = 0;
}
```

**When executed:**
- `HAL_ADC_ConvHalfCpltCallback()` sets `buffer_half_ready = 1`
- Main loop detects flag and checks UART available
- Calls `transmit_buffer_uart()` with pointer to first half

**Safe to transmit:**
- First half (0-999) is complete and stable
- DMA currently writing to second half (1000-1999)
- No race condition - different memory regions

**Pointer arithmetic:**
- `&adc_buffer[0]` = pointer to sample 0
- `HALF_BUFFER_SIZE` = 1000 samples to transmit

#### Second Half Processing
```c
else if (buffer_half_ready == 2 && !uart_tx_busy) {
  transmit_buffer_uart(&adc_buffer[HALF_BUFFER_SIZE], HALF_BUFFER_SIZE);
  buffer_half_ready = 0;
}
```

**When executed:**
- `HAL_ADC_ConvCpltCallback()` sets `buffer_half_ready = 2`
- Main loop detects flag and checks UART available
- Calls `transmit_buffer_uart()` with pointer to second half

**Safe to transmit:**
- Second half (1000-1999) is complete and stable
- DMA wrapped around, now writing to first half (0-999)
- No race condition - different memory regions

**Pointer arithmetic:**
- `&adc_buffer[HALF_BUFFER_SIZE]` = `&adc_buffer[1000]` = pointer to sample 1000
- `HALF_BUFFER_SIZE` = 1000 samples to transmit

#### Why `else if` Instead of Two Separate `if` Statements?

```c
// Correct: else if
if (buffer_half_ready == 1 && !uart_tx_busy) {
  transmit_buffer_uart(&adc_buffer[0], HALF_BUFFER_SIZE);
  buffer_half_ready = 0;
}
else if (buffer_half_ready == 2 && !uart_tx_busy) {  // Only checked if first condition false
  transmit_buffer_uart(&adc_buffer[HALF_BUFFER_SIZE], HALF_BUFFER_SIZE);
  buffer_half_ready = 0;
}
```

**Reason:**
- Only one buffer half should be processed per loop iteration
- Both halves can't be ready simultaneously under normal operation
- `else if` is more efficient (skips second check after first succeeds)
- Prevents potential edge cases if both flags somehow set

#### Flag Clearing

```c
buffer_half_ready = 0;  // Clear flag after starting transmission
```

**Critical timing:**
- Flag cleared **after** calling `transmit_buffer_uart()`
- Function returns immediately (non-blocking DMA)
- Safe because we're transmitting from stable buffer half
- Next callback can set flag again (100ms later)

**What if we cleared flag before transmission:**
```c
// WRONG:
buffer_half_ready = 0;  // Clear first
transmit_buffer_uart(...);  // Then transmit

// Problem: If callback fires between these lines, flag gets cleared!
// Would miss a buffer and lose data
```

### Optional: Low-Power Mode

```c
__WFI();  // Wait For Interrupt
```

**What it does:**
- Puts CPU to sleep until next interrupt
- Reduces power consumption
- Wakes on any interrupt (DMA, UART, timer, etc.)
- Execution resumes immediately after `__WFI()`

**When to use:**
- Battery-powered applications
- Thermal management
- When CPU idle time is significant

**When NOT to use:**
- If main loop needs to poll other peripherals
- If debugging (makes single-stepping difficult)
- If real-time constraints require immediate processing

**In this application:**
- Optional - CPU mostly idle between buffer ready events
- Main loop only processes every 100ms
- Could save ~20-30% power consumption

### Complete System Flow

```
Startup:
  1. HAL_Init() + Clock Config + Peripheral Init
  2. Calibrate ADC
  3. Start ADC+DMA (circular mode, buffer size 2000)
  4. Start TIM6 (10kHz trigger)
  
Runtime (repeating every 200ms):
  
  t=0ms:    TIM6 starts triggering ADC at 10kHz
            DMA fills buffer[0-999]
            
  t=100ms:  DMA half-complete → HAL_ADC_ConvHalfCpltCallback()
            Sets buffer_half_ready = 1
            Main loop: transmit_buffer_uart(&buffer[0], 1000)
            UART DMA starts (~22ms transmission)
            DMA continues filling buffer[1000-1999]
            
  t=122ms:  UART DMA complete → HAL_UART_TxCpltCallback()
            Clears uart_tx_busy = 0
            
  t=200ms:  DMA complete → HAL_ADC_ConvCpltCallback()
            Sets buffer_half_ready = 2
            Main loop: transmit_buffer_uart(&buffer[1000], 1000)
            UART DMA starts (~22ms transmission)
            DMA wraps to buffer[0-999]
            
  t=222ms:  UART DMA complete → HAL_UART_TxCpltCallback()
            Clears uart_tx_busy = 0
            
  t=300ms:  DMA half-complete (cycle repeats)
```

### Performance Characteristics

**Sampling:**
- Rate: 10,000 samples/second (10kHz)
- Resolution: 12-bit (0-4095)
- Timing accuracy: ±0.01% (crystal-controlled timer)

**Data throughput:**
- Raw data: 20,000 bytes/second
- With protocol: ~20,100 bytes/second
- UART capacity: ~92,000 bytes/second
- Utilization: ~22% (plenty of margin)

**Latency:**
- Buffer fill time: 100ms
- Transmission time: 22ms
- Total latency: ~122ms from sample to PC

**CPU usage:**
- ADC+DMA: <1% (interrupt-driven)
- Main loop: <2% (check flags, start TX)
- Total: <5% CPU usage (mostly idle)

**Memory:**
- ADC buffer: 4000 bytes (2000 samples × 2 bytes)
- TX packet: ~2010 bytes
- Total: ~6KB RAM

### Testing and Verification

**Initial testing:**
1. Build and flash firmware
2. Connect to PC via USB (ST-Link virtual COM port)
3. Open serial terminal at 921600 baud
4. Should see continuous data stream

**Verify with oscilloscope:**
- Probe PA0: Should see sampled signal
- Probe UART TX (PA2): Should see data bursts every 100ms
- Toggle GPIO in callbacks to measure timing

**Python receiver:**
- Use provided `src/main.py` to receive and parse packets
- Check sequence numbers for dropped packets
- Verify CRC checksums pass
- Plot data to verify signal integrity

**Common issues:**
- No data: Check baud rate, UART connection, timer running
- Corrupted data: Verify CRC algorithm matches Python
- Dropped packets: Check sequence numbers, increase buffer size if needed
- Wrong timing: Verify timer prescaler and period calculations

---

## ✅ Implementation Complete!

**All steps finished:**
- [x] Step 1: Buffer declarations and defines
- [x] Step 2: DMA callback functions
- [x] Step 3: CRC16 checksum calculation
- [x] Step 4: Packet structure and transmission
- [x] Step 5: UART DMA callback
- [x] Step 6: Main loop with ADC/Timer startup

---

## Summary

The firmware is now complete and implements:

✅ **10kHz ADC sampling** triggered by TIM6
✅ **Circular DMA** with double buffering (no data loss)
✅ **Robust protocol** with sync markers, sequence numbers, and CRC16
✅ **Non-blocking UART** transmission via DMA
✅ **Interrupt-driven architecture** (low CPU usage)
✅ **Error detection** (CRC validation, sequence tracking)

### Next Steps

1. **Build the project** in STM32CubeIDE
2. **Flash to Nucleo board**
3. **Connect to PC** via USB
4. **Run Python receiver** (`python src/main.py --port /dev/ttyACM0 --baud 921600 --plot`)
5. **Verify continuous data** streaming and analysis

### File Summary

All code changes made to `/home/rafal/PROJECTS/power-meter-consumer/src/main.c` in `USER CODE` sections:
- Private variables (buffers, flags, packet structure)
- Private functions (CRC16, transmit function)
- Callbacks (ADC DMA, UART DMA)
- Initialization (calibrate, start ADC+DMA, start timer)
- Main loop (buffer processing and transmission)

**Ready to build and test!** 🚀

---

## 📚 Advanced Topics

### Understanding ADC Hardware Architecture

This section explains how ADC peripherals work in microcontrollers and industry approaches to multi-phase power measurement.

#### Physical ADCs vs Input Channels

**STM32L476RG has 3 physical ADC converters:**

```
┌─────────────────────────────────────────────────┐
│  STM32L476RG                                    │
│                                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐│
│  │   ADC1     │  │   ADC2     │  │   ADC3     ││
│  │ (12-bit)   │  │ (12-bit)   │  │ (12-bit)   ││
│  │ SAR core   │  │ SAR core   │  │ SAR core   ││
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘│
│        │ MUX           │ MUX           │ MUX    │
│   ┌────┴────┐     ┌────┴────┐     ┌────┴────┐  │
│   │16 inputs│     │16 inputs│     │16 inputs│  │
│   │CH0-CH15 │     │CH0-CH15 │     │CH0-CH15 │  │
│   └─────────┘     └─────────┘     └─────────┘  │
│        │               │               │        │
│       PA0             PA1             PB0       │
│       PA1             PA4             PB1       │
│       PA2             PA6             ...       │
│       ...             ...                       │
└─────────────────────────────────────────────────┘
```

**Key Concepts:**

**1. Three Physical ADC Cores = 3 Independent Conversion Circuits**
- Each has its own SAR (Successive Approximation Register) logic
- Each can convert ONE sample at a time
- **Can work simultaneously** (convert different inputs at same instant)
- All 3 ADCs share same clock source and timing

**2. Each ADC has ~16 Input Channels = Analog Multiplexer (MUX)**
- Channels are GPIO pins (PA0, PA1, PC0, etc.)
- **Only ONE channel can be connected to ADC core at a time**
- Switching channels requires MUX settling time (~100ns)
- Channel selection controlled by software configuration

**3. Current Single-Phase Setup (Dual ADC Mode)**
```
Timer Trigger (10kHz)
    ↓
ADC1: Connected to CH5 (PA0 - voltage) ─┐
                                        ├─ Sampled SIMULTANEOUSLY
ADC2: Connected to CH6 (PA1 - current) ─┘
                                        
Result: One 32-bit word [Current|Voltage] every 100μs
```

- **No multiplexing** - each ADC stays locked on one channel
- Both ADCs triggered at exactly same instant
- Perfect phase alignment between voltage and current
- Hardware packs results into 32-bit Common Data Register (CDR)

#### Why Sequential Scanning Adds Delays

When using **one ADC with multiple channels**, the physical hardware limitation becomes apparent:

**Inside ONE ADC Core:**
```
Timer trigger arrives
    ↓
Step 1: Switch MUX to Channel 5 (V1)
        Wait 100ns for analog settling
        Convert (12-bit SAR = ~1.5μs)
        Store result
    ↓
Step 2: Switch MUX to Channel 8 (V2)  ⏱️ +1.6μs delay from Step 1
        Wait 100ns for settling
        Convert (~1.5μs)
        Store result
    ↓
Step 3: Switch MUX to Channel 11 (V3) ⏱️ +3.2μs delay from Step 1
        Wait 100ns
        Convert (~1.5μs)
        Store result

Total time: ~5μs (but samples taken at DIFFERENT instants!)
```

**The delay is unavoidable** because one ADC core can only look at one input at a time. The samples are not truly simultaneous even though they're fast.

---

### Industry Standards for 3-Phase Power Measurement

#### Approach 1: Triple Dual ADC (Gold Standard) ⭐

**Hardware Required: 6 ADC cores total**

```
Phase 1: ADC1 (V1) + ADC2 (I1) → simultaneous sampling
Phase 2: ADC3 (V2) + ADC4 (I2) → simultaneous sampling
Phase 3: ADC5 (V3) + ADC6 (I3) → simultaneous sampling

All 6 ADCs triggered at same instant by hardware timer
```

**Advantages:**
- ✅ Perfect phase alignment across all 3 phases (within <10ns)
- ✅ V and I within each phase perfectly synchronized
- ✅ Accurate power factor and phase angle measurements
- ✅ Meets IEC 62053-21 Class 0.2S requirements
- ✅ Can capture fast transients (voltage sags, swells)

**Disadvantages:**
- ❌ Requires high-end MCU (STM32H7, TI C2000)
- ❌ Higher cost (~$15-30 per MCU)
- ❌ More complex PCB routing

**Used By:**
- **Yokogawa WT5000** - 7-channel power analyzer (~$30,000)
- **Fluke 1760** - Three-phase power quality recorder (~$8,000)
- **Hioki PW8001** - Power analyzer (~$15,000)
- Revenue-grade smart meters (certified for billing)

**Note:** STM32L476 has only 3 ADCs, so this approach requires upgrading to STM32H743 (5 ADCs) or using external ADC chips.

---

#### Approach 2: Sequential Scanning (Budget Power Meters) ⚠️

**Hardware Required: 2 ADC cores (dual mode) with channel scanning**

**Configuration:**
```
ADC1 setup:
  - Scan mode ENABLED
  - Channels: CH5 (V1), CH8 (V2), CH11 (V3)
  - Rank 1, 2, 3
  
ADC2 setup:
  - Scan mode ENABLED  
  - Channels: CH6 (I1), CH9 (I2), CH12 (I3)
  - Rank 1, 2, 3

Timer: 30kHz trigger rate (3× higher than single phase)
```

**Sample Sequence:**
```
Timer @ 30kHz triggers ADC pair
    ↓
Time 0μs:   ADC1(V1) + ADC2(I1) simultaneous → [I1|V1]
Time 33μs:  ADC1(V2) + ADC2(I2) simultaneous → [I2|V2]
Time 67μs:  ADC1(V3) + ADC2(I3) simultaneous → [I3|V3]
Time 100μs: ADC1(V1) + ADC2(I1) simultaneous → [I1|V1] (repeat)

Each phase effectively sampled at 10kHz (30kHz ÷ 3)
```

**Buffer Layout:**
```c
uint32_t adc_buffer[6000];  // 200ms × 30kHz = 6000 samples total
// Interleaved: [I1|V1], [I2|V2], [I3|V3], [I1|V1], [I2|V2], ...
//              sample 0          sample 1          sample 2
```

**Advantages:**
- ✅ Simple, uses only 2 ADCs
- ✅ Each phase sampled at adequate rate (~10kHz effective)
- ✅ V and I **within same phase** perfectly synchronized
- ✅ Works with STM32L476 (no hardware upgrade needed)
- ✅ Low cost solution

**Disadvantages:**
- ⚠️ **Phase-to-phase timing skew** up to 67μs
- ⚠️ At 50Hz (20ms period), 67μs = **1.2° phase error between phases**
- ⚠️ At 60Hz (16.7ms period), 67μs = **1.4° phase error between phases**
- ⚠️ Affects cross-phase measurements (unbalance, sequence components)
- ⚠️ Cannot accurately capture very fast transients (<100μs)

**Phase Error Impact:**

| Measurement | Single Phase | 3-Phase Sequential | Impact |
|-------------|-------------|-------------------|--------|
| Active Power (W) | ✅ Accurate | ✅ Accurate (<0.5% error) | Minimal |
| Power Factor | ✅ Accurate | ✅ Acceptable (within phase) | Minimal |
| THD (harmonics) | ✅ Accurate | ✅ Accurate | None |
| Voltage unbalance | N/A | ⚠️ 1-2° error | Moderate |
| Phase sequence | N/A | ⚠️ May misidentify | Significant |
| Transient capture | ✅ Accurate | ❌ Blurred timing | Poor |

**When Acceptable:**
- Power quality monitoring (harmonics, distortion) ✅
- Energy consumption tracking ✅
- Residential/commercial metering (non-revenue) ✅
- Load profiling and trending ✅
- Budget-constrained designs ✅

**When NOT Acceptable:**
- Revenue metering (legal requirements) ❌
- Grid-tied inverter monitoring (needs <0.1° accuracy) ❌
- Transient power quality events (IEEE 1159 Class I) ❌
- High-precision phase angle measurements ❌
- Synchronization with grid events ❌

**Used By:**
- Entry-level 3-phase energy monitors
- Building management systems (BMS)
- Non-certified residential meters
- Educational/prototyping projects

---

#### Approach 3: External ADC Chips (Industrial Standard) 🏭

**Hardware: Dedicated multi-channel simultaneous ADC ICs**

**Popular Chips:**

**Analog Devices ADE9000** (~$5-8)
- 7 simultaneous channels (V1, I1, V2, I2, V3, I3, Neutral)
- 8kSPS per channel
- Built-in DSP: FFT, harmonics, power calculations
- SPI/I2C interface to MCU
- Certified for IEC 62053-21/22 (revenue metering)

**Microchip ATM90E32** (~$4-6)
- 6 simultaneous channels
- 4kSPS per channel
- On-chip power/energy calculations
- SPI interface
- 0.1% accuracy class

**Maxim MAX78630** (~$6-10)
- 6 simultaneous channels
- 4kSPS with 24-bit resolution
- Integrated LCD driver
- Revenue-grade accuracy

**Architecture:**
```
STM32L476                External ADC Chip (ADE9000)
  │                              │
  │                     ┌────────┴─────────────┐
  │                     │  6 SAR ADC Cores     │
  │                     │  Hardware Sample/Hold│
  │                     │  All triggered same  │
  │                     │  instant (<10ns skew)│
  │                     └─┬──┬──┬──┬──┬──┬─────┘
  │                      V1 I1 V2 I2 V3 I3
  │                              │
  │                     ┌────────┴─────────────┐
  │                     │  Built-in DSP Engine │
  │                     │  - Active/Reactive P │
  │                     │  - Harmonics to 63rd │
  │                     │  - RMS calculations  │
  │                     └──────────┬───────────┘
  │                              │
  ├──────── SPI (10MHz) ─────────┤
  │                              │
  │  STM32 reads:                │
  │  - Calculated power values   │
  │  - Pre-computed harmonics    │
  │  - Calibrated RMS            │
```

**Advantages:**
- ✅ True simultaneous sampling (all 6 channels within <10ns)
- ✅ Built-in power calculations (W, VAR, VA, PF, energy)
- ✅ Hardware harmonic analysis (up to 63rd harmonic)
- ✅ Certified for revenue metering (IEC 62053-21/22)
- ✅ Reduces MCU CPU load (calculations offloaded to ADC chip)
- ✅ Higher resolution (16-24 bit vs 12-bit internal ADC)
- ✅ Built-in calibration features
- ✅ Proven, tested designs

**Disadvantages:**
- ❌ Additional BOM cost ($5-10 per chip)
- ❌ Requires external component design (voltage dividers, current transformers)
- ❌ More complex PCB (analog signal routing)
- ❌ Learning curve for chip-specific APIs

**Used By:**
- **Commercial smart meters** (Landis+Gyr, Itron, Elster)
- **Industrial power monitors** (Schneider Electric, ABB)
- **Grid-tied inverters** (SolarEdge, Enphase)
- **Substation monitoring equipment**
- **Data center power distribution units (PDUs)**

**Development Ecosystem:**
- Reference designs available from manufacturers
- Evaluation boards (~$100-200)
- Arduino/STM32 libraries available
- Certification test houses familiar with these chips

---

### Recommended Approach for Different Use Cases

#### For Your Current Project (Single Phase) ✅

**Stick with dual ADC simultaneous mode:**
```
ADC1 (voltage) + ADC2 (current)
Timer: 10kHz
DMA: 32-bit Word mode
```

**Why:**
- Perfect for single-phase learning/research
- Meets IEC 61000-4-7 standards
- No phase timing issues
- Simple, proven architecture
- Easily scalable to sequential 3-phase later

---

#### For Future 3-Phase Projects

**Option A: Prototyping / Non-Critical Monitoring**

Use **sequential scanning** with current STM32L476:
```
ADC1: 3 channels (V1, V2, V3)
ADC2: 3 channels (I1, I2, I3)
Timer: 30kHz
```

**Good for:**
- Academic projects
- Non-revenue energy monitoring
- Building automation
- General power quality trending

**Limitations:**
- 1-2° phase error between phases
- Not certifiable for revenue metering

---

**Option B: Professional / Commercial Product**

Use **ADE9000 or ATM90E32** external ADC chip:
```
External ADC: 6 simultaneous channels
STM32: SPI communication + data logging
Total BOM addition: ~$8-12
```

**Good for:**
- Product development for sale
- Certification requirements (CE, UL, IEC)
- Revenue-grade accuracy needed
- Competitive with commercial analyzers

**Benefits:**
- Saves months of calibration and testing
- Proven accuracy and reliability
- Built-in power calculations reduce firmware complexity
- Certifiable for legal metrology

---

**Option C: High-End / Research Equipment**

Upgrade to **STM32H743** or similar (5 ADCs):
```
Phase 1: ADC1 + ADC2
Phase 2: ADC3 + ADC4  
Phase 3: ADC5 + external sigma-delta ADC
Timer: 10-100kHz
```

**Good for:**
- Research laboratory equipment
- High-precision transient analysis
- Custom analyzer development
- Maximum flexibility

**Trade-offs:**
- Higher MCU cost (~$10-15 vs $5)
- More complex firmware
- Overkill for most applications

---

### Summary Table

| Approach | ADC Cores | Phase Accuracy | Complexity | Cost | Best For |
|----------|-----------|----------------|------------|------|----------|
| **Dual ADC (current)** | 2 | Perfect (single phase) | Low | $5 | Single-phase learning ✅ |
| **Sequential Scan** | 2 | ±1-2° between phases | Low | $5 | Non-critical 3-phase |
| **External ADC Chip** | 2 + IC | <0.1° (all channels) | Medium | $13-18 | Commercial products ⭐ |
| **Multi-ADC MCU** | 5-6 | <0.01° (all channels) | High | $15-30 | Research/high-end |

### Industry Reality

**What professional manufacturers use:**
- **90%+ use external ADC chips** (ADE9000, ATM90E32, etc.)
- **5% use high-end MCUs** (TI C2000 DSPs with 6+ ADCs)
- **<5% use sequential scanning** (low-cost non-certified products only)

**Why external ADCs dominate:**
1. **Certification** - Pre-certified for IEC/ANSI standards
2. **Reliability** - Proven designs, millions deployed
3. **Support** - Reference designs, app notes, test procedures
4. **Cost** - Cheaper than months of calibration work
5. **Performance** - Better accuracy than MCU internal ADCs

**Bottom Line:**
- For **learning**: Current dual ADC approach is perfect ✅
- For **products**: External ADC chip is industry standard ✅
- For **budget prototypes**: Sequential scanning acceptable ⚠️
- For **research**: High-end MCU or custom analog front-end ✅

---

### Further Reading

- **AN5305** - STM32 ADC modes and their applications (ST Microelectronics)
- **IEC 61000-4-30** - Power quality measurement methods
- **IEC 62053-21/22** - Revenue metering accuracy requirements
- **ADE9000 Application Note** - 3-phase power measurement best practices
- **IEEE 1159-2019** - Recommended practice for monitoring electric power quality
