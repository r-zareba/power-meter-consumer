# Power Meter Consumer

Python application for receiving and analyzing dual-channel ADC data (voltage and current) from STM32 Nucleo L476RG board.

## Project Overview

This project implements a **dual simultaneous ADC sampling system** at 10kHz using STM32 Nucleo L476RG with DMA for data acquisition. Both voltage and current channels are sampled at exactly the same instant using hardware-synchronized ADC1 and ADC2 in dual mode, ensuring accurate power measurements and phase relationship analysis.

The sampled data is transmitted via UART to a laptop where Python software performs power quality analysis including:
- Real, reactive, and apparent power calculations
- Power factor and harmonic analysis
- IEC 61000-4-7 compliant measurements

## STM32 Configuration Steps

### Step 1: Configure uC Clock Source

**Configuration:**
- System clock (SYSCLK): 80 MHz (maximum for STM32L476RG)
- Clock source: HSI → PLL → SYSCLK
- APB1 timer clock: 80 MHz

**Why:**
- The timer frequency calculations depend on the system clock frequency
- 80 MHz provides sufficient resolution for precise 10kHz timing
- APB1 timer clock is automatically doubled when APB1 prescaler ≠ 1, resulting in 80 MHz for timers

**In STM32CubeMX:**
1. Go to Clock Configuration tab
2. Set SYSCLK to 80 MHz
3. Verify APB1 timer clocks show 80 MHz

### Step 2: Configure Timer for 10kHz ADC Triggering

**Timer Selected:** TIM6 (Basic Timer)

**Configuration:**
- Prescaler (PSC): 7
- Counter Period (ARR): 999
- Counter Mode: Up
- Auto-reload preload: Enabled
- Master Mode (TRGO): Update Event

**Calculations:**
```
Trigger Frequency = Timer_Clock / ((Prescaler + 1) × (Period + 1))
10,000 Hz = 80,000,000 Hz / ((7 + 1) × (999 + 1))
10,000 Hz = 80,000,000 Hz / 8,000
```

**Why TIM6:**
- Basic timer designed specifically for triggering DAC/ADC peripherals
- No GPIO pins needed (internal only)
- Simpler configuration than general-purpose timers
- Leaves other timers free for different purposes

**Why TRGO = Update Event:**
- TRGO (Trigger Output) is the internal signal that triggers the ADC
- Update Event occurs each time the timer counter resets (reaches ARR and wraps to 0)
- This creates a precise, periodic trigger at exactly 10kHz
- The ADC will be configured to start conversion on each TRGO pulse

**Why Auto-reload Preload:**
- Prevents glitches if timer parameters are updated during runtime
- New ARR values take effect only at the next update event
- Ensures continuous, uninterrupted triggering

**In STM32CubeMX:**
1. Navigate to Timers → TIM6
2. Check "Activated"
3. Set Prescaler = 7
4. Set Counter Period = 999
5. Enable Auto-reload preload
6. Set Trigger Event Selection = Update Event
7. Generate code

**Starting the Timer:**
```c
// After all peripheral initialization
HAL_TIM_Base_Start(&htim6);
```

**Note:** Timer should be started only after ADC and DMA are fully configured to ensure proper synchronization.

### Step 3: Configure DMA for ADC Data Transfer

**Why DMA First:**
- DMA must be configured before completing ADC setup
- Once DMA channel is added, ADC's "DMA Continuous Requests" option becomes available
- This is the correct order in STM32CubeMX workflow

**DMA Configuration for Dual ADC Mode:**
- DMA Controller: DMA1 or DMA2
- DMA Request: ADC1 (Master ADC)
- Channel: Auto-assigned by CubeMX
- Direction: Peripheral to Memory
- Priority: High (or Very High for guaranteed timing)
- Mode: **Circular**
- Increment Address: Memory address increment enabled, Peripheral address fixed
- Data Width: **Word (32-bit)** for both peripheral and memory ⭐ **CRITICAL for dual mode**

**Why Circular Mode:**
- DMA automatically wraps around to buffer start after reaching the end
- Enables continuous data capture without CPU intervention
- Perfect for ring buffer implementation
- Works with Half Transfer Complete and Transfer Complete interrupts for double buffering

**Why Word (32-bit) Data Width:**
- In dual simultaneous mode, both ADC results are packed into single 32-bit word
- Common Data Register (CDR): [ADC2_data(31:16) | ADC1_data(15:0)]
- DMA reads both ADCs' results in one transfer
- Memory buffer should be array of `uint32_t` (not `uint16_t`!)
- Each 32-bit word contains: lower 16 bits = ADC1 (voltage), upper 16 bits = ADC2 (current)

**Why Memory Increment Enabled:**
- Each new ADC sample goes to next position in buffer array
- Creates sequential data storage
- Peripheral address stays fixed (always ADC->DR register)

**Why High Priority:**
- Ensures DMA transfers happen immediately after ADC conversion
- Prevents data loss due to ADC overrun
- At 10kHz, DMA has plenty of time, but high priority adds safety margin

**In STM32CubeMX:**
1. Navigate to Analog → ADC1
2. Go to "DMA Settings" tab (in ADC1 Configuration panel)
3. Click "Add" button
4. Configure the DMA Request:
   - DMA Request: ADC1
   - Channel: (auto-assigned)
   - Direction: Peripheral To Memory
   - Priority: High
5. Click on the DMA Request to configure Mode and Data Width:
   - Mode: Circular
   - Increment Address: ☑ Memory (checked), ☐ Peripheral (unchecked)
   - Data Width: **Word (32 bits)** for BOTH Peripheral and Memory ⭐
6. Now "DMA Continuous Requests" in ADC Parameter Settings will be automatically enabled

**IMPORTANT:** The 32-bit Word setting is configured AFTER enabling dual ADC mode in ADC1 multi-mode settings.

**Buffer Declaration in Code:**
```c
#define BUFFER_SIZE 2000  // 200ms of data at 10kHz (dual channel)
uint32_t adc_buffer[BUFFER_SIZE];  // Circular buffer for DMA (32-bit for dual ADC!)
// Each 32-bit word contains: [ADC2_current(31:16) | ADC1_voltage(15:0)]
```

**DMA Interrupts Configuration:**
1. Go to NVIC Settings tab (in ADC1 or DMA configuration)
2. Enable DMA interrupts for the channel
3. These interrupts will trigger callbacks for Half Transfer and Transfer Complete

---

### Step 4: Hardware Pin Configuration for Dual-Channel Measurement

**Pin Assignments:**

**Voltage Channel:**
- Arduino Pin: **A0**
- STM32 Pin: **PA0**
- ADC Channel: **ADC1_IN5**
- Sensor: Voltage sensor (0-3.3V output)
- Status: ✅ Already connected

**Current Channel:**
- Arduino Pin: **A1**
- STM32 Pin: **PA1**
- ADC Channel: **ADC2_IN6**
- Sensor: Current sensor (0-3.3V output)
- Status: ✅ Already connected

**Physical Wiring on Nucleo Board:**
```
CN8 Connector (Arduino Analog Header):
Pin 1 → A0 (PA0) ← Voltage sensor output ✅
Pin 2 → A1 (PA1) ← Current sensor output ✅
Pin 8 → GND      ← Common ground for both sensors
```

**⚠️ CRITICAL SAFETY REQUIREMENTS:**

**Signal Conditioning Mandatory:**
- Both sensors MUST output 0-3.3V DC signals (ADC input range)
- **NEVER connect AC mains voltage directly** - instant board destruction!
- **NEVER connect AC current directly** - safety hazard!

**Voltage Measurement (for AC mains):**
- Isolation transformer (230V AC → 12V AC)
- Precision voltage divider + DC offset circuit
- Output: 1.65V ± 1.65V (0-3.3V range centered at mid-supply)
- Galvanic isolation MANDATORY

**Current Measurement:**
- Current transformer (CT) - e.g., SCT-013-000
- Burden resistor to convert current to voltage
- DC offset circuit for bipolar signals
- Output: 1.65V ± 1.65V (0-3.3V range)
- Alternative: Hall effect sensor with built-in isolation

**Why PA0 and PA1:**
- Adjacent pins on Arduino header - easy wiring
- Minimize noise coupling with proper PCB layout
- Both pins compatible with dual simultaneous ADC mode
- PA0 = ADC1_IN5, PA1 = ADC2_IN6 (both support their respective ADCs)

---

### Step 5: Configure Dual Simultaneous ADC Mode

**Dual ADC Configuration:** ADC1 (Master) + ADC2 (Slave)

**Multi-Mode Settings (Critical):**
- Mode: **Dual mode - Regular simultaneous mode only**
- DMA Access Mode: **Enabled** (this activates Common Data Register)
- Effect: Both ADCs sample at exactly the same instant (<10ns synchronization)
- Data packing: Single 32-bit word = [ADC2_data(31:16) | ADC1_data(15:0)]

**In STM32CubeMX - Configuring Multi-Mode:**
1. Click on **ADC1** in left sidebar (not ADC2!)
2. Find "Multi mode parameters" section in Parameter Settings
3. Set **Mode**: "Dual mode - Regular simultaneous mode only"
4. Set **DMA Access Mode**: **Enabled** ⭐
   - Note: You may NOT see additional dropdown options - that's OK!
   - CubeMX will use DMA mode 1 by default (which is correct)
5. AFTER configuring multi-mode, go back to DMA Settings tab
6. Update DMA Data Width to **Word (32 bits)** for both Peripheral and Memory

**ADC1 Configuration (Master - Voltage Channel):**
- Pin: PA0 (ADC1_IN5) - Single-ended mode
- Role: Master ADC in dual mode
- Trigger source: Timer 6 TRGO event

**ADC2 Configuration (Slave - Current Channel):**
- Pin: PA1 (ADC2_IN6) - Single-ended mode
- Role: Slave ADC in dual mode
- Trigger: Automatically synchronized to ADC1 by hardware

**In STM32CubeMX - Configuring ADC2:**
1. Click on **ADC2** in left sidebar
2. In "Mode" section, enable **IN6 Single-ended** (this enables PA1)
3. Configure Parameter Settings (same as ADC1):
   - Clock Prescaler: Asynchronous clock / 4
   - Resolution: 12 bits
   - Data Alignment: Right alignment
   - Scan Conversion Mode: Disabled
   - Continuous Conversion Mode: Disabled
4. Configure ADC2 Channel (Rank 1):
   - Channel: Channel 6
   - Sampling Time: 12.5 Cycles (same as ADC1)
5. **IMPORTANT:** Do NOT set external trigger for ADC2!
   - ADC2 is slave - triggered automatically by ADC1
   - Leave trigger as "Software Trigger" or disabled

**Why Single-ended (not Differential):**
- Single-ended measures voltage on PA0 relative to ground (VSSA)
- Suitable for most sensor applications where signal is referenced to ground
- Differential mode measures voltage difference between two pins (e.g., IN5+ and IN5-)
- Differential is only needed for signals without ground reference or for noise rejection
- For power meter with ground-referenced voltage measurement, single-ended is correct choice

**Configuration:**
- Clock Prescaler: Asynchronous clock mode, Prescaler = 4
- Resolution: 12 bits (0-4095 range)
- Data Alignment: Right aligned
- Scan Conversion Mode: Disabled (single channel)
- Continuous Conversion Mode: Disabled
- Discontinuous Conversion Mode: Disabled
- DMA Continuous Requests: Enabled
- End of Conversion Selection: EOC flag at end of single conversion
- External Trigger Conversion Source: **Timer 6 Trigger Out event**
- External Trigger Conversion Edge: **Rising edge**

**ADC Timing Configuration:**
- Sampling Time: 12.5 cycles (minimum for adequate accuracy at high speed)
- Total Conversion Time: ~1.6 μs per sample
- At 10kHz (100 μs between samples), this leaves plenty of margin

**Why ADC1:**
- Most flexible ADC on STM32L476RG
- Direct connection to DMA1 or DMA2
- Supports external trigger from multiple timer sources

**Why External Trigger = TIM6_TRGO:**
- Ensures precise, hardware-timed sampling at exactly 10kHz
- No CPU intervention needed between samples
- Eliminates timing jitter that would occur with software triggering
- Hardware synchronization between timer and ADC

**Why Rising Edge:**
- ADC conversion starts immediately on rising edge of TRGO signal
- Provides deterministic, consistent trigger-to-conversion delay
- Standard practice for timer-triggered ADC conversions

**Why DMA Continuous Requests = Enabled:**
- ADC automatically signals DMA after each conversion
- DMA transfers data without CPU involvement
- Essential for high-speed continuous sampling
- Prevents data loss between conversions

**Why Continuous Conversion = Disabled:**
- With external trigger, ADC waits for each timer trigger
- Prevents ADC from free-running
- Ensures exact 10kHz sampling rate controlled by timer
- If enabled, ADC would run at maximum speed, ignoring timer

**ADC Conversion Time Calculation:**
```
ADC_Clock = 80 MHz / 4 = 20 MHz
Sampling_Time = 12.5 cycles
Conversion_Time = 12.5 cycles (for 12-bit resolution)
Total_Time = (12.5 + 12.5) / 20 MHz = 1.25 μs

Available time at 10kHz = 100 μs
Margin = 100 μs - 1.25 μs = 98.75 μs ✓ (plenty of time)
```

**In STM32CubeMX:**
1. Navigate to Analog → ADC1
2. Enable: IN5 → Select "IN5 Single-ended" (not Differential)
3. Configuration → Parameter Settings:
   - Clock Prescaler: Asynchronous clock / 4
   - Resolution: 12 bits
   - Data Alignment: Right alignment
   - Scan Conversion Mode: Disabled
   - Continuous Conversion Mode: Disabled
   - Discontinuous Conversion Mode: Disabled
   - DMA Continuous Requests: Enabled
5. Configuration → ADC_Regular_ConversionMode:
   - External Trigger Conversion Source: Timer 6 Trigger Out event
   - External Trigger Conversion Edge: Trigger detection on rising edge
   - Rank 1 Sampling Time: 12.5 Cycles
6. Generate code

**Starting the ADC:**
```c
// Start ADC with DMA (after DMA configuration)
HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, BUFFER_SIZE);
```

**Key Points:**
- ADC must be calibrated before first use: `HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED)`
- Buffer must be properly sized and aligned for DMA access
- Start ADC before starting timer to be ready for first trigger

**Verification:**
- Use debugger to check ADC_CR register bits (ADSTART should be set)
- Verify CFGR register shows external trigger configured
- Check that conversions only occur when timer is running

---

### Step 6: Implement DMA Callbacks for Double Buffering

**Double Buffering Strategy:**
- DMA fills a circular buffer continuously
- Use **Half Transfer Complete** and **Transfer Complete** callbacks
- When first half fills → process/transmit first half while DMA fills second half
- When second half fills → process/transmit second half while DMA fills first half
- This prevents data loss and enables continuous streaming

**Buffer Structure:**
```c
#define BUFFER_SIZE 2000  // Total buffer size (2000 samples dual-channel)
#define HALF_BUFFER_SIZE 1000  // Half buffer = 100ms at 10kHz

uint32_t adc_buffer[BUFFER_SIZE];  // Circular DMA buffer (32-bit for dual ADC)
volatile uint8_t buffer_half_ready = 0;  // Flag: 1=first half, 2=second half
```

**Why This Buffer Size:**
- 2000 samples total for circular DMA operation (32-bit words)
- Each 32-bit word contains both voltage (ADC1) and current (ADC2)
- Each half = 1000 samples = 100ms of data at 10kHz
- 100ms chunks provide good balance between latency and efficiency
- Small enough for responsive data streaming, large enough to minimize overhead

**DMA Callback Functions:**

The HAL library provides two callback functions that you must implement:

**1. Half Transfer Complete Callback:**
```c
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef* hadc)
{
    if (hadc->Instance == ADC1)
    {
        // First half of buffer (0 to 999) is now full
        buffer_half_ready = 1;
        
        // Optional: Set flag or post to queue for RTOS
        // Optional: Toggle LED for visual feedback during development
    }
}
```

**Why This Callback:**
- Called automatically when DMA fills first 1000 samples (indices 0-999)
- First half is now stable and safe to read/transmit
- DMA is simultaneously filling second half (indices 1000-1999)
- No risk of data corruption since DMA is working on different memory region

**2. Transfer Complete Callback:**
```c
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
    if (hadc->Instance == ADC1)
    {
        // Second half of buffer (1000 to 1999) is now full
        buffer_half_ready = 2;
        
        // Optional: Set flag or post to queue for RTOS
        // Optional: Toggle LED for visual feedback during development
    }
}
```

**Why This Callback:**
- Called when DMA fills second 1000 samples (indices 1000-1999)
- Second half is now stable and safe to read/transmit
- DMA wraps around and starts filling first half again (circular mode)
- Creates continuous, seamless data acquisition

**Main Loop Processing:**
```c
int main(void)
{
    // ... initialization ...
    
    // Calibrate ADC
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    
    // Start ADC with DMA
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, BUFFER_SIZE);
    
    // Start Timer (triggers ADC at 10kHz)
    HAL_TIM_Base_Start(&htim6);
    
    while (1)
    {
        if (buffer_half_ready == 1)
        {
            // Process/transmit first half (indices 0-999)
            transmit_buffer_uart(&adc_buffer[0], HALF_BUFFER_SIZE);
            buffer_half_ready = 0;  // Clear flag
        }
        else if (buffer_half_ready == 2)
        {
            // Process/transmit second half (indices 1000-1999)
            transmit_buffer_uart(&adc_buffer[HALF_BUFFER_SIZE], HALF_BUFFER_SIZE);
            buffer_half_ready = 0;  // Clear flag
        }
        
        // Optional: Sleep or perform other tasks
    }
}
```

**Why This Pattern:**
- Callbacks set flags (fast, minimal ISR time)
- Main loop does heavy work (UART transmission)
- Separates real-time acquisition from communication
- Prevents blocking in interrupt context

**Alternative: RTOS Implementation**
If using FreeRTOS or similar:
```c
// Use queue or semaphore instead of simple flag
QueueHandle_t buffer_queue;

void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef* hadc)
{
    uint8_t half = 1;
    xQueueSendFromISR(buffer_queue, &half, NULL);
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
    uint8_t half = 2;
    xQueueSendFromISR(buffer_queue, &half, NULL);
}

// In task:
void data_processing_task(void *param)
{
    uint8_t half;
    while (1)
    {
        if (xQueueReceive(buffer_queue, &half, portMAX_DELAY))
        {
            uint16_t *data_ptr = (half == 1) ? &adc_buffer[0] : &adc_buffer[HALF_BUFFER_SIZE];
            transmit_buffer_uart(data_ptr, HALF_BUFFER_SIZE);
        }
    }
}
```

**Why RTOS Approach:**
- Better separation of concerns
- Prevents missed callbacks if processing takes time
- Queue provides buffering for multiple ready buffers
- More scalable for complex applications

**Critical Timing Consideration:**
- At 10kHz, you have 100ms to transmit each half buffer
- UART transmission must complete in < 100ms
- At 921600 baud: 1000 samples × 2 bytes × 10 bits ≈ 22ms (safe!)
- If transmission is slower, increase buffer size or baud rate

**Error Handling:**
```c
// Add DMA error callback
void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1)
    {
        // Handle errors: overrun, DMA error, etc.
        // Optional: Restart ADC+DMA
        HAL_ADC_Stop_DMA(&hadc1);
        HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, BUFFER_SIZE);
        
        // Log error for debugging
        error_count++;
    }
}
```

**Verification & Testing:**
1. **Toggle GPIO in callbacks** to measure timing with oscilloscope
2. **Count callbacks** to verify 10Hz rate (each callback every 100ms)
3. **Monitor buffer_half_ready flag** to ensure no missed processing
4. **Check for ADC overrun** errors in error callback
5. **Verify data integrity** - inject known signal and verify captured values

**Common Issues:**
- **Missed callbacks**: Main loop processing too slow - use RTOS or increase buffer size
- **Data corruption**: Race condition - ensure flag is cleared only after transmission complete
- **No callbacks**: Check NVIC interrupt enabled for DMA channel
- **Wrong data**: Verify DMA data width matches ADC (16-bit)

**Performance Monitoring:**
```c
// Add to main loop
static uint32_t last_process_time = 0;
uint32_t start = HAL_GetTick();

// ... process buffer ...

uint32_t process_time = HAL_GetTick() - start;
if (process_time > 90)  // Warning if close to 100ms deadline
{
    // Processing too slow!
}
```

---

### Step 7: Configure UART for Data Transmission

**UART Selected:** USART2

**Why USART2:**
- Connected to ST-Link USB on Nucleo L476RG
- Appears as virtual COM port on PC (no external USB-UART adapter needed)
- Pins: PA2 (TX), PA3 (RX) - already connected to ST-Link circuit
- Most convenient for development and deployment

**Configuration:**
- Baud Rate: 921600 (high speed for 20 KB/s data rate)
- Word Length: 8 bits
- Parity: None
- Stop Bits: 1
- Mode: Asynchronous
- Hardware Flow Control: None (optional: enable RTS/CTS for reliability)

**Why 921600 Baud:**
- Data rate requirement: 10kHz × 2 bytes = 20 KB/s minimum
- With protocol overhead (headers, checksums): ~25-30 KB/s
- UART at 921600 baud ≈ 92 KB/s theoretical, ~70-80 KB/s practical
- Provides ~3× safety margin over minimum requirement
- Standard baud rate, well-supported by USB-UART converters

**Baud Rate Options:**
```
460800:  ~46 KB/s practical - marginal (2× margin)
921600:  ~80 KB/s practical - good (3× margin) ✓ RECOMMENDED
1000000: ~90 KB/s practical - better (3.5× margin)
1500000: ~130 KB/s practical - excellent (5× margin)
2000000: ~170 KB/s practical - overkill but maximum safety
```

**Why No Parity:**
- Parity adds overhead (11 bits per byte instead of 10)
- Protocol checksums provide better error detection
- Maximizes throughput
- Standard for high-speed data transmission

**Why No Hardware Flow Control (Initially):**
- Simpler wiring (only TX/RX/GND needed)
- PC should always be faster than STM32 transmission
- Flow control can be added later if needed
- For reliable production systems, consider enabling RTS/CTS

**In STM32CubeMX:**
1. Navigate to Connectivity → USART2
2. Set Mode: Asynchronous
3. Configuration → Parameter Settings:
   - Baud Rate: 921600 Bits/s
   - Word Length: 8 Bits
   - Parity: None
   - Stop Bits: 1
   - Data Direction: Transmit Only (or Receive and Transmit if you need bidirectional)
   - Over Sampling: 16 Samples (default)
4. Optional - Hardware Flow Control: Disable (or enable RTS/CTS if using)
5. Generate code

**UART Transmission Methods:**

**Method 1: Blocking Transmission (Simple, but not recommended for real-time)**
```c
void transmit_buffer_uart(uint16_t *data, uint16_t size)
{
    // Simple but blocks CPU for ~22ms
    HAL_UART_Transmit(&huart2, (uint8_t*)data, size * 2, 100);  // 100ms timeout
}
```

**Why Not Recommended:**
- Blocks CPU during entire transmission (~22ms for 1000 samples)
- Cannot process other tasks during transmission
- Risks missing next DMA callback if transmission delayed

**Method 2: DMA Transmission (Recommended)**
```c
// Global flag to track UART DMA state
volatile uint8_t uart_tx_busy = 0;

void transmit_buffer_uart(uint16_t *data, uint16_t size)
{
    if (uart_tx_busy) {
        // Previous transmission still ongoing - error condition!
        // Either wait or skip this buffer (data loss)
        return;
    }
    
    uart_tx_busy = 1;
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)data, size * 2);
}

// UART DMA transmission complete callback
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2)
    {
        uart_tx_busy = 0;  // Ready for next transmission
    }
}
```

**Why DMA Transmission Recommended:**
- CPU free during transmission (can process other tasks)
- Non-blocking operation
- Callback notifies when transmission complete
- Essential for real-time data streaming

**Configuring UART DMA in STM32CubeMX:**
1. In USART2 Configuration panel, go to "DMA Settings" tab
2. Click "Add" button
3. Configure DMA Request:
   - DMA Request: USART2_TX
   - Channel: (auto-assigned)
   - Direction: Memory To Peripheral
   - Priority: Medium (or High if critical)
4. Click on the DMA Request to configure:
   - Mode: Normal (not Circular - we trigger each transmission manually)
   - Increment Address: ☑ Memory (checked), ☐ Peripheral (unchecked)
   - Data Width: Byte for both Peripheral and Memory
5. Enable UART TX interrupts in NVIC Settings tab

**Why Normal Mode (not Circular) for UART DMA:**
- Each buffer transmission is discrete (start → complete)
- We control when each transmission starts
- Circular mode would continuously retransmit same buffer
- Normal mode stops after each transmission, callback signals completion

**Why Byte Data Width for UART:**
- UART transmits bytes (8-bit)
- Even though ADC data is 16-bit, UART sends byte-by-byte
- DMA automatically handles 16-bit → 2× 8-bit conversion

**Complete Transmission Flow:**
```c
// In main.c
volatile uint8_t uart_tx_busy = 0;

int main(void)
{
    // ... initialization ...
    
    // Calibrate ADC
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    
    // Start ADC with DMA
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, BUFFER_SIZE);
    
    // Start Timer
    HAL_TIM_Base_Start(&htim6);
    
    while (1)
    {
        if (buffer_half_ready == 1 && !uart_tx_busy)
        {
            transmit_buffer_uart(&adc_buffer[0], HALF_BUFFER_SIZE);
            buffer_half_ready = 0;
        }
        else if (buffer_half_ready == 2 && !uart_tx_busy)
        {
            transmit_buffer_uart(&adc_buffer[HALF_BUFFER_SIZE], HALF_BUFFER_SIZE);
            buffer_half_ready = 0;
        }
    }
}

void transmit_buffer_uart(uint16_t *data, uint16_t size)
{
    uart_tx_busy = 1;
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)data, size * 2);
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2)
    {
        uart_tx_busy = 0;
    }
}
```

**Timing Analysis:**
```
Baud rate: 921600 bits/s
Bits per byte: 10 (1 start + 8 data + 1 stop)
Byte rate: 921600 / 10 = 92160 bytes/s

Buffer size: 1000 samples × 2 bytes = 2000 bytes
Transmission time: 2000 / 92160 ≈ 21.7 ms

Available time: 100 ms (before next buffer ready)
Margin: 100 - 21.7 = 78.3 ms ✓
```

**Error Handling:**
```c
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2)
    {
        // Handle errors: framing, overrun, etc.
        uart_tx_busy = 0;  // Reset flag
        
        // Optional: Restart UART DMA
        // Log error for debugging
        uart_error_count++;
    }
}
```

**Verification:**
1. **Test with simple message**: Send "Hello World" via UART before starting ADC
2. **Monitor with serial terminal**: Use PuTTY, minicom, or screen on PC
3. **Check baud rate on PC**: Must match STM32 setting exactly (921600)
4. **Verify timing**: Measure GPIO toggle during transmission with oscilloscope
5. **Test sustained operation**: Run for minutes to ensure no buffer overflow

**PC Serial Port Settings:**
- Baud Rate: 921600
- Data Bits: 8
- Parity: None
- Stop Bits: 1
- Flow Control: None
- Device: `/dev/ttyACM0` (Linux), `COMx` (Windows), `/dev/cu.usbmodem*` (macOS)

**Common Issues:**
- **No data on PC**: Check baud rate matches, verify cable connection, check device permissions
- **Corrupted data**: Baud rate mismatch, electrical noise, insufficient USB power
- **Data loss**: UART transmission taking too long, increase baud rate or buffer size
- **uart_tx_busy always 1**: UART DMA callback not firing, check NVIC interrupt enabled

**Alternative: IT (Interrupt) Mode:**
```c
// If DMA not available for UART
HAL_UART_Transmit_IT(&huart2, (uint8_t*)data, size * 2);
```
- Uses interrupts instead of DMA
- More CPU overhead than DMA but less than blocking
- Falls between blocking and DMA in efficiency

---

### Step 8: Implement Data Protocol and Packet Framing ✓

**Why Protocol Needed:**
- Raw ADC data stream has no structure - PC can't tell where packets start/end
- Synchronization required after connection or data loss
- Error detection needed to identify corrupted data
- Metadata useful (sequence numbers, timestamps, sample count)

**Protocol Design Goals:**
- Simple to implement on STM32
- Easy to parse in Python
- Robust synchronization and error detection
- Low overhead to maximize data throughput
- Unambiguous framing (sync markers unlikely in ADC data)

**Packet Structure:**

```
┌─────────────┬────────────┬──────────────┬──────────────┬──────────────┬──────────┬─────────────┐
│ Start Marker│ Seq Number │ Sample Count │ Voltage Data │ Current Data │ Checksum │ End Marker  │
│   2 bytes   │  2 bytes   │   2 bytes    │  N×2 bytes   │  N×2 bytes   │ 2 bytes  │  2 bytes    │
└─────────────┴────────────┴──────────────┴──────────────┴──────────────┴──────────┴─────────────┘
     0xAA55       uint16        uint16      uint16[N]      uint16[N]      uint16       0x55AA
                                           (ADC1-PA0)     (ADC2-PA1)
```

**Field Details:**

**1. Start Marker (2 bytes): 0xAA55**
- Fixed pattern for packet synchronization
- Unlikely to occur randomly in 12-bit ADC data
- Python searches for this pattern to find packet boundaries
- Little-endian: sent as 0x55, 0xAA on wire

**2. Sequence Number (2 bytes): 0-65535**
- Increments for each packet
- Detects lost packets
- Wraps around at 65536
- Helps synchronize and verify continuous streaming

**3. Sample Count (2 bytes): Number of samples per channel**
- Typically 1000 (for 1000-sample buffers)
- Allows variable-length packets if needed
- Validation: should match expected buffer size
- Enables future flexibility (different buffer sizes)

**4. Voltage Data (N×2 bytes): ADC1 samples from PA0**
- Array of 16-bit ADC values from voltage sensor
- Little-endian format (LSB first)
- 12-bit data right-aligned (bits 0-11 valid, 12-15 zero)
- Unpacked from lower 16 bits of dual ADC 32-bit words

**5. Current Data (N×2 bytes): ADC2 samples from PA1**
- Array of 16-bit ADC values from current sensor
- Little-endian format (LSB first)
- 12-bit data right-aligned (bits 0-11 valid, 12-15 zero)
- Unpacked from upper 16 bits of dual ADC 32-bit words

**6. Checksum (2 bytes): CRC16 or simple sum**
- Validates data integrity
- Detects transmission errors
- CRC16 preferred for better error detection
- Alternative: simple 16-bit sum for speed

**7. End Marker (2 bytes): 0x55AA**
- Confirms complete packet reception
- Different from start marker (aids debugging)
- Optional but helpful for validation

**Total Overhead:**
- Header: 2 + 2 + 2 = 6 bytes
- Trailer: 2 + 2 = 4 bytes
- Total: 10 bytes per packet
- For 1000 samples dual-channel: 2000 + 2000 + 10 = 4010 bytes (~0.25% overhead)

**C Implementation:**

```c
// Packet structure for dual-channel transmission
typedef struct {
    uint16_t start_marker;      // 0xAA55
    uint16_t sequence_number;   // Packet counter
    uint16_t sample_count;      // Number of samples per channel
    uint16_t voltage_data[1000]; // ADC1 samples (voltage)
    uint16_t current_data[1000]; // ADC2 samples (current)
    uint16_t checksum;          // CRC16 or sum
    uint16_t end_marker;        // 0x55AA
} __attribute__((packed)) ADCPacket;

// Global variables
static uint16_t packet_sequence = 0;
static ADCPacket tx_packet;

// Simple 16-bit checksum (alternative to CRC16)
uint16_t calculate_checksum(uint16_t *data, uint16_t count)
{
    uint32_t sum = 0;
    for (uint16_t i = 0; i < count; i++) {
        sum += data[i];
    }
    return (uint16_t)(sum & 0xFFFF);
}

// CRC16 implementation (better error detection)
uint16_t calculate_crc16(uint16_t *data, uint16_t count)
{
    uint16_t crc = 0xFFFF;
    uint8_t *bytes = (uint8_t*)data;
    uint16_t byte_count = count * 2;
    
    for (uint16_t i = 0; i < byte_count; i++) {
        crc ^= bytes[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc = crc >> 1;
            }
        }
    }
    return crc;
}

// Prepare and send packet with dual-channel unpacking
void transmit_buffer_uart(uint32_t *data, uint16_t size)
{
    if (uart_tx_busy) {
        return;  // Skip if busy
    }
    
    // Build packet
    tx_packet.start_marker = 0xAA55;
    tx_packet.sequence_number = packet_sequence++;
    tx_packet.sample_count = size;
    
    // Unpack 32-bit dual ADC data into separate voltage and current arrays
    // Each 32-bit word: [ADC2_current(31:16) | ADC1_voltage(15:0)]
    for (uint16_t i = 0; i < size; i++) {
        tx_packet.voltage_data[i] = (uint16_t)(data[i] & 0xFFFF);         // Lower 16 bits
        tx_packet.current_data[i] = (uint16_t)((data[i] >> 16) & 0xFFFF); // Upper 16 bits
    }
    
    // Calculate checksum (over sequence, count, voltage_data, and current_data)
    uint16_t *checksum_data = &tx_packet.sequence_number;
    uint16_t checksum_count = 1 + 1 + size + size;  // seq + count + voltage + current
    tx_packet.checksum = calculate_crc16(checksum_data, checksum_count);
    
    tx_packet.end_marker = 0x55AA;
    
    // Calculate total packet size for dual-channel
    uint16_t packet_size = sizeof(uint16_t) * (4 + size + size + 2);  // markers + header + voltage + current + checksum + end
    
    // Transmit via UART DMA
    uart_tx_busy = 1;
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)&tx_packet, packet_size);
}
```

**Alternative: Simpler Protocol (Minimal Overhead):**

If overhead is critical and reliability is less of a concern:

```c
// Minimal packet: just start marker + data + checksum
typedef struct {
    uint16_t start_marker;      // 0xAA55
    uint16_t adc_data[1000];    // ADC samples
    uint16_t checksum;          // Simple sum
} __attribute__((packed)) SimplePacket;

void transmit_buffer_simple(uint16_t *data, uint16_t size)
{
    static SimplePacket packet;
    
    packet.start_marker = 0xAA55;
    memcpy(packet.adc_data, data, size * sizeof(uint16_t));
    packet.checksum = calculate_checksum(data, size);
    
    uart_tx_busy = 1;
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)&packet, sizeof(SimplePacket));
}
```

**Why These Markers (0xAA55 / 0x55AA):**
- Alternating bit pattern (10101010 01010101)
- Easy to spot in hex dumps
- Unlikely in 12-bit ADC data (would require value 43605 = 0xAA55, but ADC max is 4095)
- Not sequential numbers or common patterns
- Asymmetric start vs end aids debugging

**Memory Considerations:**

```c
// Stack allocation (if packet fits)
ADCPacket tx_packet;  // ~2KB for 1000 samples

// Or global/static to save stack
static ADCPacket tx_packet;

// Or dynamic allocation (not recommended for real-time)
ADCPacket *packet = malloc(sizeof(ADCPacket));
```

**Timing Impact:**

```
Packet overhead: 10 bytes
Original single-channel: 2000 bytes in 21.7 ms
Dual-channel transmission: 4010 bytes in 43.5 ms
Available time window: 100 ms (each buffer half)
Safety margin: 56.5 ms ✓ (plenty of headroom)
```

**Integration with Main Loop:**

```c
int main(void)
{
    // ... initialization ...
    
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, BUFFER_SIZE);
    HAL_TIM_Base_Start(&htim6);
    
    while (1)
    {
        if (buffer_half_ready == 1 && !uart_tx_busy)
        {
            transmit_buffer_uart(&adc_buffer[0], HALF_BUFFER_SIZE);
            buffer_half_ready = 0;
        }
        else if (buffer_half_ready == 2 && !uart_tx_busy)
        {
            transmit_buffer_uart(&adc_buffer[HALF_BUFFER_SIZE], HALF_BUFFER_SIZE);
            buffer_half_ready = 0;
        }
    }
}
```

**Debugging Tips:**

```c
// Add debug output during development
void transmit_buffer_uart(uint16_t *data, uint16_t size)
{
    // ... packet preparation ...
    
    #ifdef DEBUG_PROTOCOL
    printf("Sending packet: seq=%u, samples=%u, checksum=0x%04X\n", 
           tx_packet.sequence_number, 
           tx_packet.sample_count, 
           tx_packet.checksum);
    #endif
    
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)&tx_packet, packet_size);
}
```

**Testing Strategy:**

1. **Loopback test**: Connect UART TX to RX, verify packet echoes correctly
2. **Known data**: Fill buffer with known pattern (0, 1, 2, 3...), verify on PC
3. **Checksum validation**: Intentionally corrupt data, verify checksum catches it
4. **Sequence checking**: Monitor sequence numbers, verify no gaps
5. **Continuous operation**: Run for extended period, verify no dropped packets

**Common Issues:**

- **Struct packing**: Always use `__attribute__((packed))` to prevent padding
- **Endianness**: STM32 and most PCs are little-endian, but verify
- **Buffer alignment**: Ensure tx_packet is properly aligned for DMA
- **Checksum coverage**: Decide what to include (just data, or headers too?)
- **Marker collisions**: Monitor if 0xAA55 appears in ADC data (shouldn't with 12-bit)

**Protocol Variations:**

**Add timestamp:**
```c
struct {
    uint16_t start_marker;
    uint32_t timestamp_ms;    // From HAL_GetTick()
    uint16_t sample_count;
    // ... rest of packet
};
```

**Add error flags:**
```c
struct {
    uint16_t start_marker;
    uint16_t sequence_number;
    uint16_t flags;           // bit 0: ADC overrun, bit 1: UART error, etc.
    // ... rest of packet
};
```

---

### Step 9: Python Receiver Application ✓

**Overview:**
Python application to receive, parse, validate, and analyze dual-channel ADC data from STM32 via serial port.

**Features:**
- Packet synchronization and parsing with CRC16 validation
- Sequence number tracking for dropped packet detection
- Dual-channel data reception (voltage and current)
- IEC 61000-4-7 compliant 200ms analysis windows
- Real-time statistics display (1-second averaging)
- Raw byte mode for debugging

**Implementation:**
See the following files for the complete implementation:
- `src/main.py` - Main entry point with command-line interface
- `src/receiver/receiver.py` - `ADCReceiver` class for serial communication and packet parsing
- `src/analytics/analytics.py` - Power analysis functions (IEC 61000-4-7 & IEC 61000-4-30 compliant)
- `src/analytics/plots.py` - Plotting utilities for data visualization

---

## Python Dependencies

```bash
pip install pyserial numpy matplotlib scipy
```

Or install from requirements file:
```bash
pip install -r requirements.txt
```

## Sensor Configuration

Hardware sensor parameters are centrally defined in `src/config.py`:

```python
# Voltage sensor (ZMPT101B default)
VOLTAGE_SENSOR = {
    "name": "ZMPT101B",
    "scaling_factor": 1.0 / 230.0,  # V_sensor/V_mains
    "dc_bias": 1.65,                # V (VCC/2)
    "max_input": 250.0,             # V AC
}

# Current sensor (ACS712-05B default)
CURRENT_SENSOR = {
    "name": "ACS712-05B",
    "sensitivity": 0.185,  # V/A
    "dc_bias": 1.65,       # V (VCC/2)
    "max_current": 5.0,    # ±A
}
```

**To change sensor hardware:** Edit these values in `src/config.py` to match your actual sensors and calibration. These settings are shared across the simulator, receiver, and analytics modules.

See `README_hardware.md` for detailed sensor setup information.

## Usage

### STM32 Side:
1. Configure peripherals using STM32CubeMX following Steps 1-5
2. Implement DMA callbacks and UART protocol (Steps 6-8)
3. Build and flash firmware to Nucleo L476RG
4. Connect to PC via USB (ST-Link virtual COM port)

### Python Side:

**Normal operation - receive and display statistics:**
```bash
python src/main.py --port /dev/ttyACM0 --baud 921600
```

**Raw byte mode (for debugging):**
```bash
python src/main.py --port /dev/ttyACM0 --baud 921600 --raw
```

**On Windows:**
```bash
python src/main.py --port COM3 --baud 921600
```

**On macOS:**
```bash
python src/main.py --port /dev/cu.usbmodem14203 --baud 921600
```

**Command-line arguments:**
- `--port` - Serial port device (default: /dev/ttyACM0)
- `--baud` - Baud rate (default: 921600)
- `--raw` - Display raw bytes instead of parsing packets (for debugging)

### Troubleshooting:

**Permission denied on Linux:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Then logout and login

# Or use sudo temporarily
sudo python src/main.py --port /dev/ttyACM0
```

**Find the correct port:**
```bash
# Linux
ls /dev/ttyACM* /dev/ttyUSB*

# macOS
ls /dev/cu.usbmodem*

# Windows - Check Device Manager or use:
mode
```

## Complete System Overview

```
┌─────────────┐  Timer    ┌──────────────┐  DMA   ┌────────────┐
│   TIM6      │─────────→ │  ADC1+ADC2   │───────→│ DMA Buffer │
│   10kHz     │  Trigger  │ Dual 12-bit  │ Auto   │  2000×32b  │
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
                                            │  USART2       │
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

**Performance:**
- Sampling rate: 10,000 samples/second per channel (dual simultaneous)
- Data rate: ~40 KB/s raw data (2 channels × 10kHz × 2 bytes)
- Packet rate: ~44 KB/s (with protocol overhead)
- Latency: ~100ms per buffer
- Reliability: CRC16 checksums, sequence number tracking
- Throughput: Sustained continuous dual-channel streaming
- Phase accuracy: <10ns between voltage and current measurements
