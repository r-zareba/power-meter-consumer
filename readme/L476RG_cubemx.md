# STM32 Nucleo-L476RG CubeMX Configuration Guide

**Board:** NUCLEO-L476RG  
**Project:** Power Meter - Dual ADC Data Acquisition  
**Target:** 10.24 kHz simultaneous dual ADC sampling with DMA and UART transmission (IEC 61000-4-7 standard for 50Hz grids)

---

## Hardware Pin Configuration

### Analog Inputs (CN8 Arduino Header)

```
CN8 Connector (Arduino Analog Header):
├─ Pin 1 (A0) → PA0 → ADC1_IN5   (Voltage sensor input)
├─ Pin 2 (A1) → PA1 → ADC2_IN6   (Current sensor input)
└─ Pin 8 (GND) → Ground          (Common ground)
```

### Serial Communication

**USART2 (ST-Link Virtual COM Port):**
- **PA2:** USART2_TX (auto-assigned by ST-Link connection)
- **PA3:** USART2_RX (auto-assigned by ST-Link connection)

---

## CubeMX Configuration Steps

### Step 1: Configure System Clock (80 MHz)

**Target:** SYSCLK = 80 MHz, APB1 Timer clocks = 80 MHz

**In STM32CubeMX:**
1. Go to **Clock Configuration** tab
2. Configure clock tree:
   - **Input source:** HSI (16 MHz internal RC oscillator)
   - **PLL Source Mux:** HSI
   - **PLLM (divider):** /1
   - **PLLN (multiplier):** ×10  → VCO = 160 MHz
   - **PLLR (divider):** /2  → PLLCLK = 80 MHz
   - **System Clock Mux:** PLLCLK
   - **AHB Prescaler:** /1  → HCLK = 80 MHz
   - **APB1 Prescaler:** /1  → APB1 = 80 MHz
   - **APB2 Prescaler:** /1  → APB2 = 80 MHz

**Verification:**
- SYSCLK shows **80 MHz** (green)
- APB1 Timer clocks show **80 MHz** (green)
- No red warnings

**Why 80 MHz:**
- Maximum frequency for STM32L476RG
- APB1 timer clock automatically doubled when prescaler ≠ 1, giving 80 MHz
- Required for TIM6 calculations to achieve exact 10 kHz trigger rate

---

### Step 2: Configure TIM6 for 10.24 kHz ADC Triggering

**Timer:** TIM6 (Basic Timer)

**In STM32CubeMX:**
1. Navigate to **Timers → TIM6**
2. Mode section:
   - ☑ Check **"Activated"**
3. Configuration → **Parameter Settings:**
   - **Prescaler (PSC):** **7**
   - **Counter Period (ARR):** **974**
   - **Counter Mode:** Up
   - **Auto-reload preload:** ☑ **Enable**
4. Configuration → **Trigger Output (TRGO) Parameters:**
   - **Trigger Event Selection:** **Update Event**

**Calculation:**
```
Timer_Clock = 80 MHz
Trigger_Freq = Timer_Clock / ((PSC+1) × (ARR+1))
10,256.4 Hz = 80,000,000 / ((7+1) × (974+1))
10,256.4 Hz = 80,000,000 / 7,800 ✓
```

**Verification:**
- TIM6 shows "Activated"
- PSC = 7, ARR = 974
- Trigger Event Selection = Update Event

**Why these settings:**
- **TIM6:** Basic timer designed for ADC/DAC triggering, no GPIO pins needed
- **TRGO = Update Event:** Generates internal trigger pulse to ADC every time counter resets
- **Auto-reload preload:** Prevents glitches if parameters change during runtime
- **10.24 kHz is the IEC 61000-4-7 standard for 50Hz grids**
- **Perfect FFT alignment:** 200ms window = 2,048 samples (2^11)
- Used by Fluke 435-II, Hioki PW3198, and other professional analyzers

---

### Step 3: Configure GPIO Pins for ADC Inputs

**In STM32CubeMX:**
1. Go to **Pinout & Configuration** tab
2. Find **PA0** pin on chip diagram
3. Click **PA0** → Select **ADC1_IN5** → Mode: **Single-ended**
4. Find **PA1** pin on chip diagram  
5. Click **PA1** → Select **ADC2_IN6** → Mode: **Single-ended**

**Verification:**
- PA0 shows **ADC1_IN5** (green or yellow on pinout)
- PA1 shows **ADC2_IN6** (green or yellow on pinout)
- Both configured as **Single-ended**

**Why Single-ended:**
- Measures voltage relative to ground (VSSA)
- Suitable for sensors with ground-referenced outputs
- Differential mode only needed for floating signals or noise rejection

---

### Step 4: Configure DMA for ADC1

**In STM32CubeMX:**
1. Navigate to **Analog → ADC1**
2. Click **"DMA Settings"** tab
3. Click **"Add"** button
4. Configure DMA Request:
   - **DMA Request:** ADC1
   - **Channel:** (auto-assigned by CubeMX)
   - **Direction:** Peripheral To Memory
   - **Priority:** High
5. Click on the DMA Request to expand detailed settings:
   - **Mode:** **Circular**
   - **Increment Address:**
     - ☑ **Memory:** Enabled
     - ☐ **Peripheral:** Disabled
   - **Data Width:**
     - **Peripheral:** **Word (32 bits)** ⚠️ Critical for dual mode
     - **Memory:** **Word (32 bits)**

**Verification:**
- DMA Request shows "ADC1"
- Mode = "Circular"
- Data Width = "Word" for both Peripheral and Memory
- Memory increment enabled, Peripheral increment disabled

**Why these settings:**
- **Circular mode:** DMA auto-wraps to buffer start, enables continuous capture
- **Word (32-bit):** Dual ADC mode packs both results: `[ADC2(31:16) | ADC1(15:0)]`
- **Memory increment:** Each sample stored in next buffer position
- **High priority:** Prevents data loss from ADC overrun

**Note:** DMA must be configured BEFORE completing ADC setup. After DMA is added, "DMA Continuous Requests" option will appear in ADC settings.

---

### Step 5: Configure ADC1 (Master - Voltage Channel)

**In STM32CubeMX:**
1. Left sidebar: **Analog → ADC1**
2. Mode section:
   - **IN5 (PA0)** should already show as enabled (from Step 3)
   - Verify: **Single-ended**
3. Configuration → **Parameter Settings:**
   - **Clock Prescaler:** Asynchronous clock / 4
   - **Resolution:** 12 bits
   - **Data Alignment:** Right alignment
   - **Scan Conversion Mode:** Disabled
   - **Continuous Conversion Mode:** Disabled
   - **Discontinuous Conversion Mode:** Disabled
   - **DMA Continuous Requests:** ☑ Enabled (auto-enabled after DMA setup)
   - **End Of Conversion Selection:** EOC flag at end of single conversion
4. Configuration → **ADC_Regular_ConversionMode:**
   - **External Trigger Conversion Source:** Timer 6 Trigger Out event
   - **External Trigger Conversion Edge:** Rising edge
   - **Rank 1:**
     - **Channel:** Channel 5
     - **Sampling Time:** 12.5 Cycles

**Timing Calculation:**
```
ADC_Clock = 80 MHz / 4 = 20 MHz
Sample_Time = 12.5 cycles
Conversion_Time = 12.5 cycles (12-bit)
Total = (12.5 + 12.5) / 20 MHz = 1.25 µs
Available @ 10kHz = 100 µs → Margin: 98.75 µs ✓
```

**Verification:**
- Resolution = "12 bits"
- External Trigger = "Timer 6 Trigger Out event"
- Trigger Edge = "Rising edge"  
- Sampling Time = "12.5 Cycles"
- DMA Continuous Requests = Enabled

**Why these settings:**
- **External trigger:** Hardware-timed sampling at exact 10 kHz, no CPU jitter
- **Continuous conversion disabled:** ADC waits for timer trigger (not free-running)
- **DMA Continuous Requests:** ADC automatically signals DMA after each conversion

---

### Step 6: Configure ADC2 (Slave - Current Channel)

**In STM32CubeMX:**
1. Left sidebar: **Analog → ADC2**
2. Mode section:
   - **IN6 (PA1)** should already show as enabled (from Step 3)
   - Verify: **Single-ended**
3. Configuration → **Parameter Settings:**
   - **Clock Prescaler:** Asynchronous clock / 4 (same as ADC1)
   - **Resolution:** 12 bits
   - **Data Alignment:** Right alignment
   - **Scan Conversion Mode:** Disabled
   - **Continuous Conversion Mode:** Disabled
4. Configuration → **ADC_Regular_ConversionMode:**
   - **External Trigger Conversion Source:** ⚠️ **Software Trigger** (leave as-is, do NOT set external trigger)
   - **Rank 1:**
     - **Channel:** Channel 6
     - **Sampling Time:** 12.5 Cycles (match ADC1)

**Verification:**
- Resolution = "12 bits"
- Sampling Time = "12.5 Cycles" (matches ADC1)
- External Trigger = "Software Trigger" (NOT set to timer!)

**⚠️ CRITICAL:**
- **DO NOT configure external trigger for ADC2**
- ADC2 is slave - triggered automatically by ADC1 via multi-mode hardware
- Setting external trigger on ADC2 will break synchronization

---

### Step 7: Configure Dual Simultaneous ADC Mode

**In STM32CubeMX:**
1. Click on **ADC1** in left sidebar (NOT ADC2!)
2. Find **"Multi mode parameters"** section in Parameter Settings
3. Configure:
   - **Mode:** **"Dual mode - Regular simultaneous mode only"**
   - **DMA Access Mode:** **Enabled** ⭐
4. **After configuring multi-mode:**
   - Go back to ADC1 → **DMA Settings** tab
   - Verify/update DMA Data Width to **Word (32 bits)** for both Peripheral and Memory

**Verification:**
- Multi-mode shows "Dual mode - Regular simultaneous mode only"
- DMA Access Mode shows "Enabled"
- DMA Data Width is "Word (32 bits)" for both

**Why these settings:**
- **Simultaneous mode:** Both ADCs sample at exact same instant (<10ns synchronization)
- **DMA Access Enabled:** Activates Common Data Register (CDR) that packs both results into 32-bit word: `[ADC2(31:16) | ADC1(15:0)]`
- **32-bit DMA:** Single DMA transfer captures both voltage and current in one operation

---

### Step 8: Configure USART2 for Data Transmission

**In STM32CubeMX:**
1. Navigate to **Connectivity → USART2**
2. Mode: **Asynchronous**
3. Configuration → **Parameter Settings:**
   - **Baud Rate:** 921600 Bits/s
   - **Word Length:** 8 Bits
   - **Parity:** None
   - **Stop Bits:** 1
   - **Data Direction:** Transmit Only (or Receive and Transmit)
   - **Over Sampling:** 16 Samples

**Verification:**
- Mode = "Asynchronous"
- Baud Rate = "921600"
- Word Length = "8 Bits"

**Why 921600 baud:**
- Data rate: ~40 KB/s (dual channel @ 10kHz × 2 bytes × 2 channels)
- 921600 baud ≈ 92 KB/s theoretical, ~80 KB/s practical
- Provides ~2× safety margin

**Note:** USART2 uses PA2 (TX) and PA3 (RX), auto-connected to ST-Link Virtual COM Port

---

### Step 9: Configure DMA for USART2

**In STM32CubeMX:**
1. In USART2 configuration, click **"DMA Settings"** tab
2. Click **"Add"** button
3. Configure DMA Request:
   - **Request:** USART2_TX
   - **Channel:** (auto-assigned)
   - **Direction:** Memory to Peripheral
   - **Priority:** Medium
4. Expand DMA settings:
   - **Mode:** Normal (not circular)
   - **Increment Address:**
     - ☑ **Memory:** Enabled
     - ☐ **Peripheral:** Disabled
   - **Data Width:**
     - **Peripheral:** Byte
     - **Memory:** Byte

**Verification:**
- Mode = "Normal"
- Direction = "Memory to Peripheral"
- Data Width = "Byte" for both

**Why these settings:**
- **Normal mode:** Each transmission is discrete (start → complete → stop)
- **Byte width:** UART transmits 8-bit bytes
- **Memory increment:** Reads sequential bytes from buffer

---

### Step 10: Enable NVIC Interrupts

**In STM32CubeMX:**
1. Left sidebar: **System Core → NVIC**
2. **NVIC** tab - Enable these interrupts:
   - ☑ **DMA1 channel1 global interrupt** (or whichever stream assigned to ADC1)
   - ☑ **DMA1 channel7 global interrupt** (or whichever stream assigned to USART2_TX)
   - ☑ **USART2 global interrupt**
   - ☑ **ADC1 and ADC2 global interrupts**
3. **Set Preemption Priorities:**
   - **DMA interrupts:** Preemption Priority = **0** (highest)
   - **ADC interrupts:** Preemption Priority = **1**
   - **USART2:** Preemption Priority = **2**

**Verification:**
- All 4 interrupt types enabled (checkboxes checked)
- Priorities set correctly (DMA = 0, ADC = 1, USART = 2)

**Why these priorities:**
- DMA highest priority to prevent data loss
- ADC mid-priority for conversion complete callbacks
- USART lowest priority (non-critical timing)

---

### Step 11: Project Settings and Code Generation

**In STM32CubeMX:**
1. Click **"Project Manager"** tab
2. **Project** section:
   - **Project Name:** (your choice, e.g., "PowerMeter_L476RG")
   - **Toolchain/IDE:** STM32CubeIDE
   - **Project Location:** (verify correct path)
3. **Code Generator** tab:
   - ☑ Copy only necessary library files
   - ☑ Generate peripheral initialization as pair of .c/.h files
   - ☐ Keep user code when regenerating
4. **Advanced Settings** tab:
   - Verify all peripherals use **HAL** driver (not LL)
5. Click **"GENERATE CODE"** button (top right)

**Verification:**
- Code generation completes successfully
- No errors or warnings in console
- Source files created in `Core/Src/` and `Core/Inc/`

---

## Configuration Summary

### Pin Assignment Summary

| Pin | Function | ADC Channel | Purpose |
|-----|----------|-------------|---------|
| PA0 | ADC1_IN5 | Channel 5 | Voltage sensor input |
| PA1 | ADC2_IN6 | Channel 6 | Current sensor input |
| PA2 | USART2_TX | - | Serial transmit to PC |
| PA3 | USART2_RX | - | Serial receive from PC |

### Peripheral Configuration Summary

| Peripheral | Setting | Value |
|------------|---------|-------|
| **System Clock** | SYSCLK | 80 MHz |
| | APB1 Timer Clock | 80 MHz |
| **TIM6** | Prescaler | 7 |
| | Counter Period | 974 |
| | Trigger Output | Update Event |
| **ADC1** | Resolution | 12 bits |
| | Trigger Source | Timer 6 TRGO |
| | Sampling Time | 12.5 cycles |
| | Clock Prescaler | /4 (20 MHz) |
| **ADC2** | Resolution | 12 bits |
| | Sampling Time | 12.5 cycles |
| | Clock Prescaler | /4 (20 MHz) |
| **Multi-Mode** | Mode | Dual simultaneous |
| | DMA Access | Enabled |
| **DMA (ADC1)** | Mode | Circular |
| | Data Width | Word (32-bit) |
| | Priority | High |
| **USART2** | Baud Rate | 921600 |
| | Word Length | 8 bits |
| | Parity | None |
| **DMA (USART2)** | Mode | Normal |
| | Data Width | Byte |
| | Priority | Medium |

### Calculated Timings

```
Sampling Rate:    10,256.4 Hz (per channel, simultaneous)
Sample Period:    97.5 µs
ADC Conv Time:    1.25 µs per channel
UART Tx Time:     ~44 ms per 1024-sample buffer (at 921600 baud)
Buffer Duration:  100 ms per half (1024 samples)
UART Bandwidth:   ~44% (safe for reliable operation)

IEC 61000-4-7 Standard Compliance for 50Hz grids:
  - 204.8 samples per cycle (10 cycles in 200ms)
  - 200ms window = 2,048 samples (2^11 - PERFECT for FFT)
  - Radix-2 FFT optimization (fastest possible)
  - Industry standard: Fluke 435-II, Hioki PW3198, Dranetz HDPQ
  - Class A power quality monitoring per IEC 61000-4-30
```

---

## Next Steps After CubeMX Configuration

1. ✅ CubeMX configuration complete
2. ✅ Code generated
3. [ ] Implement application code in `main.c`
4. [ ] Implement DMA callbacks for double buffering
5. [ ] Implement UART packet protocol
6. [ ] Build and flash firmware
7. [ ] Test with hardware and Python receiver

---

**Document Version:** 1.0  
**Last Updated:** January 19, 2026  
**Board:** NUCLEO-L476RG  
**Project:** Power Meter Dual ADC Acquisition
