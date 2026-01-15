# STM32H755ZI-Q Power Meter Implementation

## Overview

This directory contains the power meter implementation for the **STM32H755ZI-Q** Nucleo board. The H755 is a dual-core MCU (Cortex-M7 + Cortex-M4) with advanced features including D-Cache, which requires special handling for DMA operations.

## Key Differences from STM32L476RG

### Hardware Advantages
- **CPU**: 480 MHz Cortex-M7 (vs 80 MHz Cortex-M4 on L476)
- **ADC**: Native 16-bit resolution @ 64 MHz (vs 12-bit on L476)
- **D-Cache**: 16KB data cache for performance (L476 has no cache)
- **Dual Core**: M7 + M4 cores (only M7 used in this project)

### Implementation Challenges
- **D-Cache Coherency**: DMA bypasses cache, causing data corruption if not handled properly
- **UART Clock**: Requires faster clock source (HSI 64MHz) for 921600 baud
- **Complexity**: More configuration required than L476

## Critical Configuration for DMA + Cache

### The Problem
On STM32H7 series, the D-Cache can cause DMA coherency issues:

```
CPU writes to buffer → Data goes to D-Cache (fast)
DMA reads buffer → Reads from RAM directly (bypasses cache, sees stale data)

CPU reads from buffer → Reads from D-Cache (may be stale)
DMA writes to buffer → Writes to RAM directly (bypasses cache)
```

**Result**: Transmitted data is corrupted, received data is stale.

### The Solution: Use D2 SRAM (Non-Cacheable)

The **simplest and most reliable** solution is to place DMA buffers in **D2 SRAM** (0x30000000), which is **not cacheable by default**. This avoids all cache coherency issues without any MPU configuration.

#### Implementation (in main.c)

```c
// DMA buffers in D2 SRAM (0x30000000) - NOT cacheable, no MPU needed!
uint32_t adc_buffer[BUFFER_SIZE] 
  __attribute__((section(".dma_buffer"))) 
  __attribute__((aligned(32)));

static PacketData tx_packet 
  __attribute__((section(".dma_buffer"))) 
  __attribute__((aligned(32)));
```

The linker script already has the `.dma_buffer` section configured:

```ld
/* In STM32H755ZITX_FLASH.ld */
.dma_buffer (NOLOAD) :
{
  . = ALIGN(32);
  *(.dma_buffer)
  *(.dma_buffer*)
  . = ALIGN(32);
} >RAM_D2
```

**Note:** CubeMX does NOT generate this section by default. You must add it manually to the linker script (`CM7/STM32H755ZITX_FLASH.ld`).

**Where to add it:**
Place this section after the `.bss` section and before `._user_heap_stack`:

```ld
  /* Uninitialized data section */
  .bss :
  {
    /* ... existing .bss content ... */
  } >RAM_D1

  /* DMA buffers in D2 SRAM - not cached, perfect for DMA */
  .dma_buffer (NOLOAD) :
  {
    . = ALIGN(32);
    *(.dma_buffer)
    *(.dma_buffer*)
    . = ALIGN(32);
  } >RAM_D2

  /* User_heap_stack section */
  ._user_heap_stack :
  {
    /* ... existing heap/stack content ... */
  } >RAM_D1
```

**That's it!** No MPU configuration, no cache operations, no complexity.

#### Why This Works

**STM32H7 Memory Map:**
- **D1 AXI SRAM (0x24000000)**: 512 KB, **cacheable** by default → Cache issues with DMA
- **D2 AHB SRAM (0x30000000)**: 288 KB, **NOT cacheable** → Perfect for DMA buffers
- **D3 SRAM (0x38000000)**: 64 KB, **NOT cacheable** → Also good for DMA

When variables are in D2/D3 SRAM, the D-Cache never caches them, so CPU and DMA always see the same data.

#### Benefits of D2 SRAM Approach
✅ **Simplest solution** - Just add `section` attribute  
✅ **No MPU configuration** needed - Zero extra code  
✅ **No manual cache operations** - Automatic coherency  
✅ **ST's official approach** - Used in ST examples  
✅ **Same performance** - D2 SRAM is fast AHB bus  
✅ **More flexible** - Saves MPU regions for other uses  

## UART Configuration Fix

### Issue
The default USART3 clock source (`D2PCLK1`) runs at 50 MHz on this H7 configuration:
- SYSCLK = 400 MHz / 2 = 200 MHz
- APB1 = 200 MHz / 4 = **50 MHz**

At 50 MHz, the UART cannot achieve accurate 921600 baud rate, causing data corruption.

### Solution
Change USART3 clock source to **HSI (64 MHz)** in `usart.c`:

```c
void HAL_UART_MspInit(UART_HandleTypeDef* uartHandle) {
  if(uartHandle->Instance==USART3) {
    // Configure USART3 clock
    PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_USART3;
    PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_HSI; // 64 MHz HSI
    HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct);
    // ...
  }
}
```

**Before**: `RCC_USART234578CLKSOURCE_D2PCLK1` (50 MHz) → Wrong baud rate  
**After**: `RCC_USART234578CLKSOURCE_HSI` (64 MHz) → Correct 921600 baud ✅

## Hardware Configuration

### USART3 (ST-Link VCP)
- **TX**: PD8
- **RX**: PD9
- **Baud**: 921600
- **Mode**: 8N1, TX-only with DMA

### ADC (Dual Simultaneous Mode)
- **ADC1 (Voltage)**: PA0 (CN11 pin 28)
- **ADC2 (Current)**: PC0 (CN11 pin 38)
- **Resolution**: 16-bit native
- **Trigger**: TIM6 @ 10 kHz
- **DMA**: Circular mode, dual mode packing (both ADCs in one 32-bit word)

### LEDs
- **Green (PB0)**: UART transmission activity
- **Yellow (PE1)**: ADC DMA half/complete callbacks
- **Red (PB14)**: Error indication

### Timers
- **TIM6**: 10 kHz ADC trigger (IEC 61000-4-7 compliant)

## Memory Map

### STM32H755 SRAM Regions
- **D1 SRAM (0x24000000)**: 512 KB, AXI bus, **cacheable by default**
- **D2 SRAM (0x30000000)**: 288 KB, AHB bus
- **D3 SRAM (0x38000000)**: 64 KB, backup domain, non-cacheable

**DMA buffers**: Placed in D1 SRAM (0x24000000), marked non-cacheable via MPU.

## Packet Format

Same as L476RG implementation:

```
Offset  | Size | Field         | Description
--------|------|---------------|---------------------------
0       | 2    | start_marker  | 0xAA55
2       | 2    | sequence      | Packet counter (wraps at 65535)
4       | 2    | count         | Number of samples per channel (1000)
6       | 2000 | voltage_data  | ADC1 samples (1000 × uint16_t)
2006    | 2000 | current_data  | ADC2 samples (1000 × uint16_t)
4006    | 2    | checksum      | CRC16-MODBUS
4008    | 2    | end_marker    | 0x55AA
--------|------|---------------|---------------------------
Total: 4010 bytes
```

## Testing

### Verify UART Output
```bash
# Windows
python -c "import serial; s=serial.Serial('COM5', 921600); print(s.read(100).hex())"

# Linux
stty -F /dev/ttyACM0 921600 raw -echo
cat /dev/ttyACM0 | hexdump -C | head -20
```

Expected output should start with:
```
00000000  55 aa 00 00 e8 03 [voltage samples...] [current samples...] [CRC] aa 55
```

### Run Python Receiver
```bash
cd /home/rafal/PROJECTS/power-meter-consumer
uv run src/main.py --port COM5 --baud 921600
```

## CubeMX Project Settings

If regenerating code from CubeMX:

### USART3
- **Mode**: Asynchronous
- **Baud**: 921600
- **Hardware Flow Control**: Disabled
- **DMA**: TX only, Normal mode
- ⚠️ **Clock Source**: Must manually change to HSI in `usart.c` after code generation

### ADC1/ADC2
- **Mode**: Dual Mode, Regular Simultaneous
- **Resolution**: 16-bit
- **Trigger**: Timer 6 TRGO
- **DMA**: Circular, both ADCs packed into 32-bit words
- **Post-Gen Fix**: Change `ADC_CONVERSIONDATA_DMA_ONESHOT` to `ADC_CONVERSIONDATA_DMA_CIRCULAR` in `adc.c`

### TIM6
- **Period**: Calculate for 10 kHz: `(timer_clock / 10000) - 1`
- **TRGO**: Update Event

### GPIO
- **PB0**: Green LED
- **PE1**: Yellow LED
- **PB14**: Red LED

## Post-Generation Fixes

After generating code with CubeMX, these changes are required:

1. **ADC Circular Mode** (`adc.c` line ~60):
   ```c
   hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DMA_CIRCULAR;
   ```

2. **USART Clock Source** (`usart.c` line ~85):
   ```c
   PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_HSI;
   ```
   **Or configure in CubeMX:** Clock Configuration tab → USART2,3,4,5,7,8 Mux → **HSI**

3. **Linker Script - Add DMA Buffer Section** (`CM7/STM32H755ZITX_FLASH.ld`):
   
   Add after `.bss` section (around line 170):
   ```ld
   /* DMA buffers in D2 SRAM - not cached, perfect for DMA */
   .dma_buffer (NOLOAD) :
   {
     . = ALIGN(32);
     *(.dma_buffer)
     *(.dma_buffer*)
     . = ALIGN(32);
   } >RAM_D2
   ```
   
   **Important:** CubeMX does NOT generate this section - you must add it manually.

4. **DMA Buffers in D2 SRAM** (add to `main.c`):
   ```c
   // Place DMA buffers in D2 SRAM (non-cacheable)
   uint32_t adc_buffer[BUFFER_SIZE] 
     __attribute__((section(".dma_buffer"))) 
     __attribute__((aligned(32)));
   
   static PacketData tx_packet 
     __attribute__((section(".dma_buffer"))) 
     __attribute__((aligned(32)));
   ```

5. **TIM6 Start** (`main.c` USER CODE 2):
   ```c
   HAL_TIM_Base_Start(&htim6);
   ```

## Troubleshooting

### No UART Data or Corrupted Data
- ✅ Verify USART clock is HSI (64 MHz), not D2PCLK1
- ✅ Check baud rate on receiving side matches 921600
- ✅ Verify PD8/PD9 pins are correctly configured

### Wrong ADC Values
- ✅ Ensure TIM6 is started: `HAL_TIM_Base_Start(&htim6)`
- ✅ Check ADC calibration runs before starting DMA
- ✅ Verify circular DMA mode in `adc.c`

### System Hangs or Crashes
- ✅ MPU must be configured **before** `HAL_Init()`
- ✅ DMA buffers must be 32-byte aligned
- ✅ Check that buffers fit in 32KB MPU region

### LEDs Not Blinking
- ✅ Green LED: UART transmit working, check `transmit_buffer_uart()`
- ✅ Yellow LED: ADC DMA callbacks firing, check TIM6 trigger
- ✅ Red LED ON: Error occurred, check error handlers

## Performance

- **ADC Sampling**: 10 kHz per channel (IEC 61000-4-7 compliant)
- **Packet Rate**: 10 packets/second (100ms @ 10kHz)
- **UART Throughput**: ~392 kbps actual (4010 bytes × 10 Hz × 10 bits/byte)
- **CPU Load**: Low (<5% at 200 MHz with MPU cache optimization)

## References

- [STM32H755 Reference Manual (RM0399)](https://www.st.com/resource/en/reference_manual/rm0399-stm32h745755-and-stm32h747757-advanced-armbased-32bit-mcus-stmicroelectronics.pdf)
- [STM32H755 Datasheet](https://www.st.com/resource/en/datasheet/stm32h755zi.pdf)
- [AN4838: Managing memory protection unit in STM32 MCUs](https://www.st.com/resource/en/application_note/an4838-managing-memory-protection-unit-in-stm32-mcus-stmicroelectronics.pdf)
- [AN4839: Level 1 cache on STM32F7 and STM32H7 Series](https://www.st.com/resource/en/application_note/an4839-level-1-cache-on-stm32f7-series-and-stm32h7-series-stmicroelectronics.pdf)

## License

Same as main project (see root LICENSE file).
