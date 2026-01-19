# STM32H755ZI-Q Required Fixes

## Critical: DMA + D-Cache Coherency

### The Problem
The H755 has a 16KB D-Cache that causes DMA coherency issues:
- **DMA writes bypass the cache** → When ADC DMA writes new samples to RAM, the CPU's cache still contains old values from previous reads. The CPU reads stale data from cache instead of fresh ADC samples.
- **CPU writes go to cache** → When CPU prepares the UART packet in cache, those writes may not be immediately flushed to RAM. DMA reads the old RAM contents and transmits corrupted/incomplete packet data.
- **Result**: ADC readings appear frozen or incorrect, UART transmits garbled data with wrong samples or checksums, system behavior is unpredictable and timing-dependent.

The cache operates independently from DMA - neither knows about the other's data modifications, creating two inconsistent views of the same memory location.

**Why this happens:** By default, CubeMX places variables in **D1 SRAM (0x24000000)**, which is **cacheable** by the Cortex-M7. The cache stores frequently accessed data for speed, but DMA transfers bypass it entirely, accessing RAM directly. When both CPU and DMA access the same buffer, their views become desynchronized - this is called a cache coherency problem.

### Possible Solutions

1. **Use D2/D3 SRAM (NOT cacheable)** ✅ **RECOMMENDED**
   - D2 SRAM (0x30000000) and D3 SRAM (0x38000000) are **NOT cached by default**
   - No MPU configuration needed, no manual cache operations
   - ST's official approach in examples
   - Simple and reliable

2. **Use MPU to mark D1 SRAM regions as non-cacheable** ⚠️ More complex
   - Requires MPU configuration to mark specific D1 regions non-cacheable
   - Wastes an MPU region, more error-prone
   - Only needed if you must use D1 SRAM

3. **Manual cache invalidate/clean operations** ❌ NOT RECOMMENDED
   - Call `SCB_InvalidateDCache_by_Addr()` before reading DMA data
   - Call `SCB_CleanDCache_by_Addr()` before DMA writes
   - Error-prone, slower, easy to forget operations

### The Solution: Use D2 SRAM (Non-Cacheable)

Place DMA buffers in **D2 SRAM (0x30000000)** which is **NOT cacheable by default**. This provides automatic cache coherency with zero overhead.

**STM32H7 SRAM Regions:**
- **D1 SRAM (0x24000000)**: 512 KB, **cacheable** → Cache issues with DMA ❌
- **D2 SRAM (0x30000000)**: 288 KB, **NOT cacheable** → Perfect for DMA ✅
- **D3 SRAM (0x38000000)**: 64 KB, **NOT cacheable** → Also suitable ✅

## Required Post-CubeMX Fixes

After generating code with STM32CubeMX, apply these **mandatory** fixes:

### 1. Add DMA Buffer Section to Linker Script

**File:** `CM7/STM32H755ZITX_FLASH.ld`

Add this section after `.bss` (around line 170):

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

⚠️ **CubeMX does NOT generate this section** - you must add it manually.

### 2. Place DMA Buffers in D2 SRAM

**File:** `CM7/Core/Src/main.c`

```c
// OLD (causes cache corruption):
uint32_t adc_buffer[BUFFER_SIZE] __attribute__((aligned(32)));
static PacketData tx_packet __attribute__((aligned(32)));

// NEW (cache-safe):
uint32_t adc_buffer[BUFFER_SIZE] 
  __attribute__((section(".dma_buffer"))) 
  __attribute__((aligned(32)));

static PacketData tx_packet 
  __attribute__((section(".dma_buffer"))) 
  __attribute__((aligned(32)));
```

**No MPU configuration needed!** The `section` attribute automatically places variables in D2 SRAM.

### 3. Fix USART Clock Source

**File:** `CM7/Core/Src/usart.c`

Change USART3 clock from D2PCLK1 (50 MHz) to HSI (64 MHz) for accurate 921600 baud:

```c
void HAL_UART_MspInit(UART_HandleTypeDef* uartHandle) {
  if(uartHandle->Instance==USART3) {
    // Configure USART3 clock
    PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_USART3;
    PeriphClkInitStruct.Usart234578ClockSelection = RCC_USART234578CLKSOURCE_HSI; // ← Change this!
    HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct);
    // ...
  }
}
```

**Alternative:** Configure in CubeMX: Clock Configuration tab → USART2,3,4,5,7,8 Mux → **HSI**

### 4. Enable ADC Circular DMA Mode

**File:** `CM7/Core/Src/adc.c` (around line 60)

```c
// Change from:
hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DMA_ONESHOT;

// To:
hadc1.Init.ConversionDataManagement = ADC_CONVERSIONDATA_DMA_CIRCULAR;
```

### 5. Start Timer Trigger

**File:** `CM7/Core/Src/main.c` in `USER CODE BEGIN 2`

```c
/* USER CODE BEGIN 2 */
HAL_TIM_Base_Start(&htim6);  // Start ADC trigger timer
/* USER CODE END 2 */
```

## Hardware Configuration Summary

### USART3 (ST-Link VCP)
- **TX**: PD8, **RX**: PD9
- **Baud**: 921600 (requires HSI clock source)
- **DMA**: TX only, circular mode

### ADC (Dual Simultaneous Mode)
- **ADC1 (Voltage)**: PA0_C (CN11 pin 28) - **16-bit native**
- **ADC2 (Current)**: PC0 (CN9 pin 2, labeled A1) - **16-bit native**
- **Trigger**: TIM6 @ 10 kHz
- **DMA**: Circular, dual mode (32-bit packed)

### TIM6 Configuration
For 10 kHz sampling with 200 MHz timer clock:
- **Prescaler (PSC)**: 19
- **Auto-Reload (ARR)**: 999
- **Frequency**: 200 MHz / (20 × 1000) = 10 kHz

## Quick Verification Checklist

After applying fixes, verify:

- [ ] `.dma_buffer` section exists in linker script
- [ ] DMA buffers use `__attribute__((section(".dma_buffer")))`
- [ ] USART3 clock source is HSI (64 MHz)
- [ ] ADC uses `ADC_CONVERSIONDATA_DMA_CIRCULAR`
- [ ] TIM6 is started with `HAL_TIM_Base_Start(&htim6)`
- [ ] Build completes without errors
- [ ] UART outputs valid data (starts with `0xFFFF`)

## Why These Fixes Matter

| Fix | Without It | With It |
|-----|------------|---------|
| D2 SRAM buffers | Random data corruption | Perfect DMA coherency ✅ |
| HSI clock source | Wrong baud rate, garbled data | Accurate 921600 baud ✅ |
| Circular DMA | Single-shot, stops after first buffer | Continuous streaming ✅ |
| TIM6 start | No ADC sampling | 10 kHz sampling ✅ |

