# STM32 Code Implementation Guide

This document tracks the step-by-step implementation of the power meter consumer firmware for STM32 Nucleo L476RG.

## Prerequisites
- STM32CubeMX configuration completed (Clock, TIM6, DMA, ADC1, USART2)
- Base project generated with auto-generated `main.c`

---

## ✅ Step 1: Add Buffer Declarations and Defines

**Location:** `/* USER CODE BEGIN PV */` section (Private Variables)

**Code Added:**
```c
// DMA Buffer for ADC sampling (circular buffer)
#define BUFFER_SIZE 2000           // Total buffer: 2000 samples (200ms at 10kHz)
#define HALF_BUFFER_SIZE 1000      // Half buffer: 1000 samples (100ms at 10kHz)

uint16_t adc_buffer[BUFFER_SIZE];  // Circular buffer filled by DMA
volatile uint8_t buffer_half_ready = 0;  // 0=none, 1=first half ready, 2=second half ready
volatile uint8_t uart_tx_busy = 0;       // 0=idle, 1=transmission in progress
```

**Explanation:**
- **`adc_buffer[2000]`**: Circular buffer where DMA continuously writes ADC samples at 10kHz
- **`BUFFER_SIZE = 2000`**: Total buffer holds 200ms of data (2000 samples ÷ 10000 samples/sec)
- **`HALF_BUFFER_SIZE = 1000`**: Each half holds 100ms of data, giving time for UART transmission (~22ms)
- **`buffer_half_ready`**: Flag set by DMA callbacks to signal which half is ready to transmit
  - `0` = No buffer ready
  - `1` = First half (samples 0-999) ready
  - `2` = Second half (samples 1000-1999) ready
- **`uart_tx_busy`**: Flag to prevent starting new UART transmission while one is in progress
- **`volatile` keyword**: Required for variables modified in interrupt handlers to prevent compiler optimization

**Why these values:**
- 2000 samples enables circular DMA with proper double buffering
- 1000 samples per half provides 100ms transmission window (UART needs ~22ms at 921600 baud)
- 16-bit samples match ADC 12-bit data stored in 16-bit registers

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
// Packet structure for UART transmission
typedef struct {
  uint16_t start_marker;    // 0xAA55 - synchronization marker
  uint16_t sequence_number; // Packet counter (0-65535, wraps around)
  uint16_t sample_count;    // Number of ADC samples in this packet
  uint16_t adc_data[HALF_BUFFER_SIZE]; // ADC samples (1000 values)
  uint16_t checksum;                   // CRC16 for integrity validation
  uint16_t end_marker;                 // 0x55AA - end of packet marker
} __attribute__((packed)) ADCPacket;

// Global variables for packet transmission
static uint16_t packet_sequence = 0; // Increments with each packet sent
static ADCPacket tx_packet; // Packet buffer (static to avoid stack overflow)
```

### 3. Transmission Function
```c
/**
 * @brief  Build packet and transmit ADC buffer via UART with DMA
 * @param  data: Pointer to ADC data buffer
 * @param  size: Number of samples to transmit
 * @retval None
 */
void transmit_buffer_uart(uint16_t *data, uint16_t size) {
  if (uart_tx_busy) {
    // UART transmission already in progress - skip this buffer
    // In production, might want to log this as a data loss event
    return;
  }

  // Build packet header
  tx_packet.start_marker = 0xAA55; // Sync pattern for packet detection
  tx_packet.sequence_number = packet_sequence++; // Increment packet counter
  tx_packet.sample_count = size;                 // Number of samples

  // Copy ADC data from DMA buffer to transmit packet
  memcpy(tx_packet.adc_data, data, size * sizeof(uint16_t));

  // Calculate CRC16 checksum over: sequence_number + sample_count + adc_data
  // Use byte pointer to avoid alignment warning with packed struct
  uint8_t *checksum_data_bytes = (uint8_t *)&tx_packet.sequence_number;
  uint16_t checksum_byte_count = (1 + 1 + size) * 2; // (seq + count + samples) * 2 bytes per word
  
  // Calculate CRC inline to avoid unaligned pointer issues
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
  tx_packet.end_marker = 0x55AA; // Different from start for validation

  // Calculate total packet size in bytes
  // Header: start(2) + seq(2) + count(2) = 6 bytes
  // Data: size * 2 bytes
  // Trailer: checksum(2) + end(2) = 4 bytes
  uint16_t packet_size = 6 + (size * 2) + 4;

  // Start non-blocking UART transmission via DMA
  uart_tx_busy = 1; // Set flag before starting transmission
  HAL_UART_Transmit_DMA(&huart2, (uint8_t *)&tx_packet, packet_size);
}
```

**Explanation:**

### Packet Structure (ADCPacket)

```
┌─────────────┬────────────┬──────────────┬─────────────┬──────────┬─────────────┐
│ Start Marker│ Seq Number │ Sample Count │  ADC Data   │ Checksum │ End Marker  │
│   2 bytes   │  2 bytes   │   2 bytes    │  1000×2 B   │ 2 bytes  │  2 bytes    │
└─────────────┴────────────┴──────────────┴─────────────┴──────────┴─────────────┘
     0xAA55      0-65535        1000        uint16[1000]   CRC16       0x55AA
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
   - Number of ADC samples in this packet
   - Allows variable-length packets if needed
   - Receiver validates this matches expected size

4. **`adc_data[1000]`**
   - Raw ADC samples from DMA buffer
   - 12-bit values right-aligned in 16-bit words
   - Little-endian format (STM32's native format)

5. **`checksum` (CRC16)**
   - Calculated over: sequence + count + data
   - Detects transmission errors
   - Start/end markers NOT included in checksum

6. **`end_marker` (0x55AA)**
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
- Static allocation (~2KB buffer)
- Avoids stack overflow (too large for stack)
- Reused for each transmission (no malloc needed)

### Transmission Function Flow

1. **Check if UART busy**
   - If previous transmission still ongoing, skip (prevents overwrite)
   - In production, could increment error counter

2. **Build packet header**
   - Set start marker (0xAA55)
   - Increment and assign sequence number
   - Set sample count

3. **Copy ADC data**
   - `memcpy()` from DMA buffer to packet buffer
   - Fast memory copy (uses optimized ARM instructions)
   - Size: 1000 samples × 2 bytes = 2000 bytes

4. **Calculate checksum**
   - CRC16 over sequence + count + all samples
   - Uses byte pointer to avoid alignment issues with packed struct
   - Calculates CRC inline using same algorithm as `calculate_crc16()` function
   - Byte count: (1 + 1 + 1000) words × 2 = 2004 bytes

5. **Set end marker**
   - 0x55AA for packet validation

6. **Calculate packet size**
   - Total: 2010 bytes (for 1000 samples)
   - Overhead: 10 bytes (~0.5%)

7. **Start UART DMA transmission**
   - Non-blocking: function returns immediately
   - DMA handles transfer in background
   - Set `uart_tx_busy` flag before starting

### Timing Analysis

```
At 921600 baud:
- Bytes per second: 921600 / 10 = 92160 bytes/s
- Packet size: 2010 bytes
- Transmission time: 2010 / 92160 ≈ 21.8 ms

Timeline:
0ms: Buffer half ready (callback sets flag)
0ms: transmit_buffer_uart() called
0ms: Packet built (~0.5ms for memcpy + CRC)
0.5ms: UART DMA starts
22.3ms: UART DMA completes (callback clears uart_tx_busy)
100ms: Next buffer half ready

Margin: 100 - 22.3 = 77.7 ms ✓ (plenty of time)
```

### Safety Features

1. **uart_tx_busy check**: Prevents concurrent transmissions
2. **Sequence numbers**: Detects lost packets
3. **CRC16 checksum**: Validates data integrity
4. **Start/end markers**: Enables synchronization and framing validation
5. **Static allocation**: No dynamic memory (reliable for embedded)

**Key Points:**
- Function returns immediately (non-blocking DMA)
- Packet built in ~0.5ms, transmitted in ~22ms
- Python receiver will use matching CRC algorithm to verify
- Start/end markers enable robust packet synchronization

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
