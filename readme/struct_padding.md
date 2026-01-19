# Struct Padding and Alignment - Complete Guide

## Understanding Memory Alignment in C

### Basic Concept

Computer memory has addresses like house numbers: 0, 1, 2, 3, 4, 5...

ARM Cortex-M4 CPU reads memory **fastest** when data starts at specific addresses:
- `uint8_t` (1 byte): Any address (0, 1, 2, 3...)
- `uint16_t` (2 bytes): Even addresses (0, 2, 4, 6...)
- `uint32_t` (4 bytes): Multiples of 4 (0, 4, 8, 12...)

---

## Compiler Padding Behavior

### Example 1: Mixed Types (Padding Added)

```c
struct Mixed {
    uint8_t  a;     // 1 byte
    uint16_t b;     // 2 bytes
    uint8_t  c;     // 1 byte
};
```

**Memory layout WITHOUT `packed`:**
```
Offset: 0    1    2    3    4    5
       [a ][PAD][b0][b1][c ][PAD]
Total: 6 bytes (2 bytes padding added)

Why?
- a at offset 0 ✅
- Compiler adds 1 byte padding
- b at offset 2 ✅ (even address for uint16_t)
- c at offset 4 ✅
- Compiler adds 1 byte padding for struct alignment
```

### Example 2: Same Types (No Padding)

```c
struct AllSame {
    uint16_t field1;   // 2 bytes
    uint16_t field2;   // 2 bytes
    uint16_t field3;   // 2 bytes
};
```

**Memory layout (automatic):**
```
Offset: 0    2    4    6
       [f1 ][f2 ][f3 ]
Total: 6 bytes (NO padding needed!)

Why?
- field1 at offset 0 ✅ (even)
- field2 at offset 2 ✅ (even, 0+2=2)
- field3 at offset 4 ✅ (even, 2+2=4)
- All uint16_t naturally aligned!
```

---

## The `__attribute__((packed))` Directive

### What It Does

Tells compiler: "Don't add ANY padding!"

```c
struct Mixed {
    uint8_t  a;
    uint16_t b;
    uint8_t  c;
} __attribute__((packed));
```

**Memory layout WITH `packed`:**
```
Offset: 0    1    2    3
       [a ][b0][b1][c ]
Total: 4 bytes (saves 2 bytes!)

But now:
- a at offset 0 ✅
- b at offset 1 ⚠️ (ODD address - slower access!)
- c at offset 3 ✅
```

**Trade-offs:**
- ✅ Smaller memory footprint
- ✅ Matches wire protocols (network packets)
- ❌ Slower CPU access (misaligned reads)
- ❌ DMA may reject misaligned data

---

## The `__attribute__((aligned(N)))` Directive

### What It Does

Forces start address to be multiple of N.

### On Struct Type
```c
struct Example {
    uint16_t data;
} __attribute__((aligned(32)));

struct Example var1;  // Compiler aligns to 32-byte boundary
struct Example var2;  // Also aligned to 32-byte boundary
```

### On Variable Declaration
```c
struct Example {
    uint16_t data;
};

struct Example var1;  // Normal alignment
struct Example var2 __attribute__((aligned(32)));  // This one aligned to 32 bytes
```

---

## Power Meter Packet Structure - Case Study

### The Packet

```c
typedef struct {
  uint16_t start_marker;           // 2 bytes
  uint16_t sequence;               // 2 bytes
  uint16_t count;                  // 2 bytes
  uint16_t voltage_data[1000];     // 2000 bytes
  uint16_t current_data[1000];     // 2000 bytes
  uint16_t checksum;               // 2 bytes
  uint16_t end_marker;             // 2 bytes
} PacketData;
```

### Memory Layout Analysis

```
Offset: 0     2     4     6     8     ...  2006  2008  ...  4006  4008  4010
       [SM  ][SEQ ][CNT ][V[0]][V[1]]...[V[999]][I[0]]...[I[999]][CRC ][END ]
        └2B─┘└2B─┘└2B─┘└2B──┘         └2B───┘└2B──┘       └2B───┘└2B─┘└2B─┘

All offsets: 0, 2, 4, 6, 8, 10, 12... (ALL EVEN!)
Total size: 4010 bytes
```

**Key observations:**
1. All fields are `uint16_t` (2 bytes)
2. Every addition: 0+2=2, 2+2=4, 4+2=6... → always even
3. **Compiler adds ZERO padding** - naturally compact!
4. `sizeof(PacketData) == 4010` (verified at compile time)

### Why NO `packed` Needed?

```c
// ❌ UNNECESSARY:
typedef struct {
    uint16_t fields...
} __attribute__((packed)) PacketData;

// ✅ ALREADY PERFECT:
typedef struct {
    uint16_t fields...  // All same type = naturally aligned
} PacketData;
```

**No padding exists to remove!**

### Why `aligned(4)` on Variable?

```c
static PacketData tx_packet __attribute__((aligned(4)));
```

**Purpose:** Ensure struct **starts** at DMA-friendly address

```
Without aligned(4):
tx_packet could start at 0x20000001, 0x20000002, etc. (any address)

With aligned(4):
tx_packet starts at 0x20000000, 0x20000004, 0x20000008... (multiple of 4)
                    ↑ DMA controller prefers this!
```

**Why 4, not 2?**
- STM32 DMA works in 32-bit (4-byte) chunks
- Starting at multiple of 4 enables efficient burst transfers
- Still safe for uint16_t (4 is multiple of 2)

---

## Common Mistakes

### ❌ Mistake 1: Contradictory Attributes
```c
struct __attribute__((packed)) __attribute__((aligned(32))) {
    uint16_t data[1000];
} MyStruct;
```

**Problem:** 
- `packed` = "ignore alignment rules inside struct"
- `aligned(32)` = "respect strict alignment"
- Contradiction! STM32 HAL DMA rejects this

### ❌ Mistake 2: Packed When Not Needed
```c
typedef struct {
    uint16_t field1;
    uint16_t field2;
    uint16_t field3;
} __attribute__((packed)) AllSame;
```

**Problem:**
- All fields already aligned naturally
- `packed` signals "I have alignment problems" when you don't
- May confuse strict DMA checks

### ✅ Correct Approach
```c
// Struct definition: natural alignment
typedef struct {
    uint16_t field1;
    uint16_t field2;
    uint16_t field3;
} AllSame;

// Variable: aligned for DMA
static AllSame buffer __attribute__((aligned(4)));
```

---

## When to Use Each

| Attribute | Use Case | Example |
|-----------|----------|---------|
| `packed` on struct | Mixed types, network protocols | TCP header (uint8_t + uint16_t + uint32_t) |
| NO `packed` | All same-sized fields | All uint16_t or all uint32_t |
| `aligned(N)` on struct | All instances need alignment | DMA descriptor arrays |
| `aligned(N)` on variable | One specific buffer for DMA | TX/RX packet buffer |

---

## Verification Techniques

### 1. Compile-Time Size Check
```c
_Static_assert(sizeof(PacketData) == 4010, "Unexpected padding!");
```
Compile fails if compiler added padding.

### 2. Runtime Offset Check
```c
#include <stddef.h>

printf("start_marker offset: %zu\n", offsetof(PacketData, start_marker));
printf("voltage_data offset: %zu\n", offsetof(PacketData, voltage_data));
printf("checksum offset: %zu\n", offsetof(PacketData, checksum));
```

Expected output:
```
start_marker offset: 0
voltage_data offset: 6
checksum offset: 4006
```

### 3. Alignment Check
```c
printf("tx_packet address: %p\n", (void*)&tx_packet);
printf("Is 4-byte aligned: %s\n", 
       ((uintptr_t)&tx_packet % 4 == 0) ? "YES" : "NO");
```

---

## Summary

**For Power Meter PacketData:**

1. ✅ All fields `uint16_t` → naturally aligned → **no `packed` needed**
2. ✅ Variable has `aligned(4)` → DMA-compatible start address
3. ✅ Total size 4010 bytes → no padding added
4. ✅ STM32 HAL DMA accepts it → clean, simple, efficient

**General Rule:**
- Same-type structs: Skip `packed`, use `aligned(N)` on variable
- Mixed-type structs: Use `packed` on struct + `aligned(N)` on variable
- Network protocols: Always `packed` (defined specification)
- DMA buffers: Always `aligned(4)` or `aligned(32)` on variable
