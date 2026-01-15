# STM32H755ZI-Q CubeMX Configuration Guide

**Board:** NUCLEO-H755ZI-Q  
**Project:** Power Meter - Dual ADC Data Acquisition  

---

## Hardware Connections

```
CN9 (Analog Inputs):
├─ Pin 1 (A0/PA0_C) → Voltage Sensor (ZMPT101B) → ADC1_INP16
├─ Pin 6 (A5/PC0)   → Current Sensor (ACS712)   → ADC2_INP10
└─ Pin 8 (GND)      → Common Ground

CN8 (Power):
├─ +3.3V → Sensor Power
└─ GND   → Ground
```

---

## CubeMX Step-by-Step Configuration

### Step 1: Create New Project

**Actions:**
1. Launch STM32CubeIDE
2. File → New → STM32 Project
3. **Board Selector** tab
4. Commercial Part Number: **NUCLEO-H755ZI-Q**
5. Select "NUCLEO-H755ZI-Q" and click "Next"
6. Project Name: "PowerMeter_H755ZIQ"
7. **⚠️ CRITICAL:** On the next screen, **UNCHECK** the following:
   - [ ] Initialize all peripherals with their default Mode? → **NO**
   - [ ] Download firmware? → **NO**
8. Click "Finish"

**Important Settings:**
- [ ] Initialize all peripherals in default mode: **No**
- [ ] Generate peripheral initialization as pair of .c/.h: **Yes**

**Why Uncheck BSP Initialization?**
- Board Selector includes BSP (Board Support Package) by default
- BSP can lock certain pins (like PD8/PD9 for ST-Link VCP) making them unavailable
- Unchecking "Initialize all peripherals" prevents automatic BSP inclusion
- Gives more control over pin assignments

**Expected Result:**
- Project created with .ioc file opened in CubeMX perspective
- Pinout view showing NUCLEO-H755ZI-Q board layout

**Verification:**
- Check that "Boot CPU" shows M7
- Verify .ioc file is open
- In Pinout view, pins should be mostly unassigned (not green with BSP functions)

---

### Step 2: Enable HSE Clock Source

**Actions:**
1. Go to "Pinout & Configuration" tab
2. Left sidebar: **System Core** → **RCC**
3. In Mode section:
   - **HSE:** Select "Crystal/Ceramic Resonator"
   - (Leave LSE disabled)

**Why:**
- Enables the 25 MHz crystal already built into the Nucleo board (X3)
- Required before HSE can be used as PLL source
- Provides stable, accurate clock for high-speed operation

**Verification:**
- HSE mode shows "Crystal/Ceramic Resonator"

---

### Step 3: Configure Clock System (200 MHz for M7)

**Actions:**
1. Click "Clock Configuration" tab (top)
2. Configure PLL1 (main system clock):
   - HSE (Input): **25 MHz** (board crystal - already enabled)
   - PLL Source: **HSE** (dropdown should now be active)
   - **DIVM1:** **5** → VCO input = 5 MHz
   - **DIVN1:** **160** → VCO = 800 MHz
   - **DIVP1:** **2** → PLL1P = 400 MHz
3. Set System Clock Mux to **PLL1P** (or PLLCLK)
4. Configure Domain Prescalers:
   - **D1CPRE:** **/2** → SYSCLK = 200 MHz
   - **HPRE:** **/1** (AHB/AXI prescaler)
   - **D1PPRE (APB3):** **/2** → APB3 = 100 MHz
   - **D2PPRE1 (APB1):** **/4** → APB1 = 50 MHz
   - **D2PPRE2 (APB2):** **/2** → APB2 = 100 MHz

**Clock Targets:**
- VCO: 800 MHz
- PLL1P: 400 MHz
- SYSCLK (M7): **200 MHz** (green)
- APB1: **50 MHz** (green) - required for USART2 @ 921600 baud
- APB1 Timers: **100 MHz** (green)
- APB2: **100 MHz** (green)
- APB3: **100 MHz** (green)
- **APB1 Timer clocks: 200 MHz** ← Critical for TIM6 calculations

**Calculations:**
```
VCO = 25 MHz / 5 × 160 = 800 MHz
PLL1P = 800 MHz / 2 = 400 MHz
SYSCLK = 400 MHz / 2 = 200 MHz ✓
APB1/2/3 = 200 MHz / 2 = 100 MHz
APB Timers = 100 MHz × 2 = 200 MHz (auto-doubled when prescaler ≠ 1)
```

**Verification:**
- **All clocks show green** (valid frequencies)
- SYSCLK shows 200 MHz
- APB Timer clocks show 200 MHz

---

### Step 4: Configure GPIO Pins for ADC and LEDs

**ADC Pins:**
1. Go to "Pinout & Configuration" tab
2. Find **PA0** pin on chip view (left side of chip diagram)
3. Click PA0 → Select **ADC1_INP16**
4. Find **PC0** pin on chip view
5. Click PC0 → Select **ADC2_INP10**

**LED Pins (onboard status indicators):**
6. Find **PB0** pin on chip view
   - Click PB0 → Select **GPIO_Output**
   - Right-click PB0 → Enter User Label: **LED_GREEN**
7. Find **PE1** pin on chip view
   - Click PE1 → Select **GPIO_Output**
   - Right-click PE1 → Enter User Label: **LED_YELLOW**
8. Find **PB14** pin on chip view
   - Click PB14 → Select **GPIO_Output**
   - Right-click PB14 → Enter User Label: **LED_RED**

**Pin Summary:**
- PA0: ADC1_INP16 (Voltage sensor - CN9 Pin 1 / A0)
- PC0: ADC2_INP10 (Current sensor - CN9 Pin 6 / A5)
- PB0: GPIO_Output (LED_GREEN - onboard LD1 Green LED)
- PE1: GPIO_Output (LED_YELLOW - onboard LD2 Yellow LED)
- PB14: GPIO_Output (LED_RED - onboard LD3 Red LED)

**Why This Step First:**
- Enabling GPIO pins activates ADC peripherals in CubeMX
- Unlocks ADC configuration options in next steps
- LEDs provide visual feedback for debugging and status indication

**Verification:**
- All five pins show green color
- PA0 shows ADC1_INP16, PC0 shows ADC2_INP10
- PB0, PE1, PB14 show GPIO_Output with respective LED labels

---

### Step 5: Enable and Configure ADC1 (Master)

**Actions:**
1. Left sidebar: **Analog** → **ADC1** → Expand
2. Mode section:
   - Enable **IN16 (PA0_C)** - should already show as enabled from GPIO step
   - Verify it's set to: **Single-ended**
3. Configuration → Parameter Settings:
   - Clock Prescaler: **Asynchronous clock / 4**
   - Resolution: **16 bits**
   - Scan Conversion Mode: **Disabled**
   - Continuous Conversion: **Disabled**
   - Discontinuous Conversion: **Disabled**

**Trigger Configuration:**
- External Trigger Conversion Source: **Timer 6 Trigger Out event**
- External Trigger Conversion Edge: **Rising edge**
- DMA Continuous Requests: **Enable** (checkbox may appear after DMA setup)

**Sampling Time:**
- Channel 16 Sampling Time: **64.5 cycles** (for 16-bit accuracy)

**Verification:**
- Resolution shows "16 bits"
- External trigger shows "Timer 6 Trigger Out event"
- IN16 is enabled and shows PA0_C

---

### Step 6: Enable and Configure ADC2 (Slave)

**Actions:**
1. Left sidebar: **Analog** → **ADC2** → Expand
2. Mode section:
   - Enable **IN10 (PC0)** - should already show as enabled from GPIO step
   - Verify it's set to: **Single-ended**
3. Configuration → Parameter Settings:
   - Clock Prescaler: **Asynchronous clock / 4** (same as ADC1)
   - Resolution: **16 bits** ✅
   - Data Alignment: **Right alignment**
   - Scan Conversion Mode: **Disabled**
   - Continuous Conversion: **Disabled**

**CRITICAL - No External Trigger:**
- **DO NOT** set external trigger for ADC2
- ADC2 is slave - triggered automatically by ADC1 via multi-mode
- Leave "External Trigger Conversion Source" as **Software Trigger** or disabled

**Sampling Time:**
- Channel 10 Sampling Time: **64.5 cycles** (match ADC1)

**Verification:**
- Resolution shows "16 bits"
- NO external trigger configured (stays at Software Trigger)
- Sampling time matches ADC1 (64.5 cycles)
- IN10 is enabled and shows PC0

---

### Step 7: Configure ADC Multi-Mode (Dual Simultaneous)

**Actions:**
1. Go to **ADC1** configuration (not ADC2!)
2. In the **Mode** section (at the top), find the multi-mode dropdown
3. Select: **"Dual mode combined regular simultaneous"** or **"Dual ADC mode - Regular simultaneous mode only"**
   - Look for option with **"simultaneous"** in the name
   - Do NOT select "interleaved" modes
4. **Delay between 2 sampling phases:** Keep at **1.5 cycle** (minimum delay)
5. Look for **"DMA Access Mode for Multi mode"** setting:
   - Set to: **"Enabled"** or **"DMA mode 1 enabled"**

**Why Multi-Mode:**
- Synchronizes ADC1 and ADC2 hardware
- Both ADCs sample at exact same instant (<10 ns with 1.5 cycle delay)
- Results packed into single 32-bit word: [ADC2(31:16) | ADC1(15:0)]
- Critical for accurate power measurements (voltage × current at same time)

**Why Simultaneous (not Interleaved):**
- Simultaneous: Both ADCs sample same moment - for two separate signals
- Interleaved: ADCs alternate for faster sampling of ONE signal - not what we need

**Why 1.5 Cycle Delay:**
- Minimum hardware delay for true simultaneous operation
- Keeps ADC1 and ADC2 synchronized within nanoseconds
- Larger delays would desynchronize voltage and current measurements

**Verification:**
- Mode shows "Dual mode...simultaneous"
- Delay shows "1.5 cycle"
- DMA Access Mode shows "Enabled"

---

### Step 8: Configure ADC Clock (Now Available)

**Actions:**
1. Go to **Clock Configuration** tab
2. Find **ADC Clock** section (should now be active)
3. Configure:
   - **ADC Clock Mux:** Select **per_ck** (peripheral clock)

**Expected ADC Clock:**
- Result: **64 MHz** (actual value from H7 clock tree)
- Excellent for 16-bit @ 3.6 MSPS max

**Calculations:**
```
ADC Clock = 64 MHz ✓
At 64.5 cycles sampling time:
Conversion Time = (64.5 + 16.5) / 64 MHz = 1.27 µs per sample
At 10 kHz trigger rate (100 µs period): plenty of margin!
```

**Why 64 MHz (not 50 MHz):**
- H7 per_ck routing gives 64 MHz (depends on clock domain configuration)
- Well within ADC specifications (max ~80-100 MHz for 16-bit)
- Faster conversion = more margin = better

**Verification:**
- ADC Clock Mux shows "per_ck"
- ADC clock shows **64 MHz** in green
- No red warnings

---

### Step 8b: Configure USART Clock Source (CRITICAL!)

**⚠️ IMPORTANT:** This step prevents UART data corruption at 921600 baud.

**Actions:**
1. Stay in **Clock Configuration** tab
2. Find **USART2,3,4,5,7,8 Clock Mux** (or similar - may be labeled as "USART234578 Mux")
3. Click the dropdown (default shows "PCLK1 (D2)")
4. Select: **HSI** (64 MHz)

**Why This Matters:**
- **Default (PCLK1)**: 50 MHz (APB1 / 4) → Cannot achieve accurate 921600 baud
  - Error rate too high → Corrupted data transmission
- **HSI**: 64 MHz → Works perfectly at 921600 baud
  - Clean divisor: 64,000,000 / 921,600 ≈ 69.44 (acceptable error)

**Before vs After:**
```
Before (PCLK1):  50 MHz → USART → Baud Error ~3% ❌
After (HSI):     64 MHz → USART → Baud Error <1% ✅
```

**What Happens If You Skip This:**
- UART transmits garbage data (only values like 0x1c, 0xe0, 0xfc, 0x00)
- No sync markers (0xAA55) visible in output
- Repeating corrupted patterns
- **Must manually edit `usart.c` after every code generation**

**Verification:**
- USART2,3,4,5,7,8 Clock Mux shows **"HSI"**
- USART clock frequency shows **64 MHz** (should be in green)

**Note:** If you forget this step, you'll need to manually change this line in `CM7/Core/Src/usart.c` after code generation:
```c
// Change this:
PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_D2PCLK1;
// To this:
PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_HSI;
```

---

### Step 9: Configure TIM6 for 10 kHz ADC Triggering

**Actions:**
1. Go to "Pinout & Configuration" tab
2. Left sidebar: **Timers** → **TIM6**
3. Mode section:
   - Check **"Activated"** ✓
4. Configuration → Parameter Settings:
   - **Prescaler (PSC):** **49**
   - **Counter Period (ARR):** **199**
   - **Counter Mode:** Up
   - **Auto-reload preload:** **Enable**
5. Configuration → Trigger Output (TRGO) Parameters:
   - **Trigger Event Selection (Master Mode):** **Update Event**

**Calculations:**
```
Timer Clock = 100 MHz (APB1 Timer clock from Step 3)
Trigger Freq = Timer_Clock / ((PSC+1) × (ARR+1))
10,000 Hz = 100,000,000 / ((49+1) × (199+1))
10,000 Hz = 100,000,000 / 10,000 ✓
```

**Why TIM6:**
- Basic timer designed specifically for triggering ADC/DAC
- No GPIO pins needed (internal trigger only)
- Update Event generates TRGO signal every 100 µs (10 kHz)
- Simple configuration, leaves other timers available

**Why TRGO = Update Event:**
- TRGO (Trigger Output) is internal signal that triggers ADC1
- Update Event occurs when timer counter reaches ARR and resets to 0
- Creates precise, periodic 10 kHz trigger pulse
- ADC1 configured to start conversion on each rising edge

**Why Auto-reload Preload:**
- Prevents glitches if timer parameters updated during runtime
- New ARR value takes effect only at next update event
- Ensures continuous, uninterrupted triggering

**Verification:**
- TIM6 shows "Activated"
- PSC = 49, ARR = 199
- Master Mode (TRGO) = Update Event

---

### Step 10: Configure DMA for ADC1

**Actions:**
1. Go to ADC1 configuration
2. Click "DMA Settings" tab
3. Click "Add" button
4. Configure DMA Request:
   - Request: **ADC1**
   - Stream: (auto-assigned)
   - Direction: **Peripheral to Memory**
   - Priority: **Very High**
5. Click on the added DMA request to expand settings:
   - Mode: **Circular**
   - Increment Address:
     - ☑ Memory: **Enabled**
     - ☐ Peripheral: **Disabled**
   - Data Width:
     - Peripheral: **Word (32-bit)** ⚠️ Critical for dual mode
     - Memory: **Word (32-bit)**

**Why 32-bit:**
- Dual ADC packs both results in 32-bit word
- [ADC2_data(31:16) | ADC1_data(15:0)]

**Verification:**
- DMA mode shows "Circular"
- Data width is "Word" for both

---

### Step 11: Configure USART3 for Data Transmission

**⚠️ CRITICAL: Pin Configuration for ST-Link Virtual COM Port**

**Actions:**
1. Left sidebar: Connectivity → **USART3**
2. Mode: **Asynchronous**
3. Configuration → Parameter Settings:
   - Baud Rate: **921600 Bits/s**
   - Word Length: **8 Bits**
   - Parity: **None**
   - Stop Bits: **1**
   - Data Direction: **Transmit Only**
   - Over Sampling: **16 Samples**
4. **Pin Configuration (Pinout View):**
   - **If PD8/PD9 already show USART3 (yellow):** Perfect! Leave them as-is
   - **If not assigned:** Click **PD8** → Select **USART3_TX**, Click **PD9** → Select **USART3_RX**
   - For TX-only mode, you can leave PD9 (RX) assigned but it won't be used

**Why USART3 (not USART2)?**
- Board Selector pre-assigns PD8/PD9 to USART3 (even with BSP unchecked)
- NUCLEO-H755ZI-Q has ST-Link Virtual COM Port hardwired to **PD8** (TX) and **PD9** (RX)
- Using USART3 on these pins allows USB cable to serve as both power + data
- No external USB-Serial adapter needed
- This is the onboard USB port labeled "ST-LINK" (not "USB USER")

**Verification:**
- Baud rate shows 921600
- Mode shows "Asynchronous"
- **PD8 assigned to USART3_TX** and **PD9 to USART3_RX** (check pinout view - should be yellow or green)

---

### Step 12: Configure DMA for USART3

**Actions:**
1. In USART3 configuration, click "DMA Settings" tab
2. Click "Add" button
3. Configure:
   - Request: **USART3_TX**
   - Stream: (auto-assigned)
   - Direction: **Memory to Peripheral**
   - Priority: **Medium**
4. Expand settings:
   - Mode: **Normal** (not circular)
   - Increment Address:
     - ☑ Memory: **Enabled**
     - ☐ Peripheral: **Disabled**
   - Data Width:
     - Peripheral: **Byte**
     - Memory: **Byte**

**Verification:**
- Mode is "Normal"
- Direction is Memory to Peripheral

---

### Step 13: Enable NVIC Interrupts

**Actions:**
1. Left sidebar: **System Core** → **NVIC**
2. **Enable these interrupts** (check the boxes):
   - ☑ **DMA1 stream0 global interrupt**
   - ☑ **DMA1 stream1 global interrupt** (or whichever DMA is assigned to USART3_TX)
   - ☑ **USART3 global interrupt**
   - ☑ **ADC1 and ADC2 global interrupts**

3. **Set Preemption Priorities** (lower number = higher priority):
   - **DMA1 stream0:** Preemption Priority = **0** (highest)
   - **DMA1 stream1:** Preemption Priority = **0** (highest)
   - **ADC1 and ADC2:** Preemption Priority = **1**
   - **USART3:** Preemption Priority = **2**
   - **Sub Priority:** Leave all at **0** (default)

**What are these interrupts:**
- DMA1 stream0/1: DMA channels for ADC1 and USART3 data transfers
- ADC1 and ADC2: ADC conversion complete and error events
- USART3: UART transmission/reception events

**Priority Explanation:**
- **Preemption Priority:** Main priority level (0 = highest, can interrupt lower priority)
- **Sub Priority:** Tie-breaker when same preemption priority (usually keep at 0)
- DMA gets highest priority to prevent data loss

**Verification:**
- All 4 interrupts enabled (checked)
- Preemption priorities set correctly
- DMA streams have priority 0

---

### Step 14: Project Settings and Code Generation

**Actions:**
1. Click "Project Manager" tab
2. Project Settings:
   - Project Name: **PowerMeter_H755ZIQ**
   - Toolchain/IDE: **STM32CubeIDE**
   - Project Location: (verify correct)
3. Code Generator tab:
   - ☑ Copy only necessary library files
   - ☑ Generate peripheral initialization as pair of .c/.h files
   - ☐ Keep user code when regenerating
4. Advanced Settings:
   - Check all peripherals use **HAL** (not LL or BSP)
   - Verify USART3 shows **HAL** driver
5. Click **"Generate Code"** button

**Verification:**
- Code generation successful
- No errors or warnings
- Source files created in CM7/Core/Src/

---

### Step 15: Post-Generation Code Fixes

**⚠️ CRITICAL: These manual fixes are required after code generation**

**Fix 1: Disable Dual-Core Boot Sync (if using M7 only)**

File: `CM7/Core/Src/main.c`

Find line ~44:
```c
#define DUAL_CORE_BOOT_SYNC_SEQUENCE
```

Change to (comment out):
```c
// #define DUAL_CORE_BOOT_SYNC_SEQUENCE  // DISABLED - M4 not used
```

**Why:** Prevents M7 from waiting forever for M4 core to boot

**Fix 2: USART Clock Source (Only if Step 8b was skipped)**

File: `CM7/Core/Src/usart.c`

**⚠️ SKIP THIS if you configured USART clock to HSI in CubeMX (Step 8b)!**

If you see corrupted UART data (only 0x1c, 0xe0, 0xfc bytes), find line ~85:
```c
PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_D2PCLK1;
```

Change to:
```c
PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_HSI;
```

**Why:** 50 MHz D2PCLK1 cannot achieve accurate 921600 baud. HSI (64 MHz) works perfectly.

**Fix 3: Verify ADC DMA Mode**

File: `CM7/Core/Src/adc.c`

Find line ~60 in `MX_ADC1_Init()`:
```c
hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DR;
```

**If** it shows `ADC_CONVERSIONDATA_DR`, change to:
```c
hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DMA_CIRCULAR;
```

**Fix 3: Verify ADC DMA Mode**

File: `CM7/Core/Src/adc.c`

Find line ~60 in `MX_ADC1_Init()`:
```c
hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DR;
```

**If** it shows `ADC_CONVERSIONDATA_DR`, change to:
```c
hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DMA_CIRCULAR;
```

**Why:** Ensures ADC uses DMA in circular mode (CubeMX sometimes generates wrong value)

**Fix 4: Verify GPIO Init for LEDs**

File: `CM7/Core/Src/gpio.c`

Check that `MX_GPIO_Init()` includes all three LED pins:
```c
/* GPIO Ports Clock Enable */
__HAL_RCC_GPIOB_CLK_ENABLE();
__HAL_RCC_GPIOE_CLK_ENABLE();

/*Configure GPIO pin Output Level */
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0|GPIO_PIN_14, GPIO_PIN_RESET);
HAL_GPIO_WritePin(GPIOE, GPIO_PIN_1, GPIO_PIN_RESET);

/*Configure GPIO pins : PB0 PB14 */
GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_14;
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull = GPIO_NOPULL;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

/*Configure GPIO pin : PE1 */
GPIO_InitStruct.Pin = GPIO_PIN_1;
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull = GPIO_NOPULL;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);
```

**LED Control in Code:**
```c
// Turn ON LEDs
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_SET);   // Green LED ON
HAL_GPIO_WritePin(GPIOE, GPIO_PIN_1, GPIO_PIN_SET);   // Yellow LED ON
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);  // Red LED ON

// Turn OFF LEDs
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_RESET); // Green LED OFF
HAL_GPIO_WritePin(GPIOE, GPIO_PIN_1, GPIO_PIN_RESET); // Yellow LED OFF
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);// Red LED OFF

// Toggle LEDs
HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_0);   // Toggle Green
HAL_GPIO_TogglePin(GPIOE, GPIO_PIN_1);   // Toggle Yellow
HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);  // Toggle Red
```

**If missing:** Add manually in USER CODE section

**Verification After Fixes:**
- Code builds without errors
- No warnings about undefined references
- Ready for application code integration

---

### Step 16: Save Configuration

**Actions:**
1. Save .ioc file: **Ctrl+S**
2. Export configuration (optional):
   - File → Save As → Copy to `stm32/H755ZIQ/` folder
3. Commit to git if using version control

**Files to Keep:**
- PowerMeter_H755ZIQ.ioc (CubeMX configuration)
- This README_SETUP.md with all steps documented
- Generated code in CM7/Core/

---

## Configuration Summary

### Key Differences from L476RG:

| Parameter | L476RG | H755ZI-Q |
|-----------|--------|----------|
| ADC Resolution | 12-bit | **16-bit** ✅ |
| CPU Clock | 80 MHz | **200 MHz** |
| ADC Clock | 20 MHz | **64 MHz** |
| Timer Calculation | PSC=7, ARR=999 | **PSC=49, ARR=199** |
| Voltage Pin | PA0 (ADC1_IN5) | **PA0_C (ADC1_INP16)** |
| Current Pin | PA1 (ADC2_IN6) | **PC0 (ADC2_INP10)** |
| DMA Data Width | Word (32-bit) | **Word (32-bit)** (same) |

### Next Steps After Configuration:

1. ✅ Code generation complete
2. [ ] Implement DMA callbacks (HAL_ADC_ConvHalfCpltCallback, HAL_ADC_ConvCpltCallback)
3. [ ] Implement UART packet protocol
4. [ ] Add main.c initialization code
5. [ ] Build and test

---

## Notes

- Boot core is set to M7 only
- M4 core not used initially (can be added later)
- All settings based on 10 kHz dual-channel acquisition
- Compatible with existing Python receiver software
