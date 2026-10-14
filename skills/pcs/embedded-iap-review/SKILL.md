---
name: embedded-iap-review
description: >
  Use when reviewing IAP (In-Application Programming), BootLoader, OTA update,
  or dual-program firmware architecture. Covers flash partition layout, APP_BASE
  consistency, VTOR setup, interrupt cleanup, and image validation (CRC/signature).
  Triggers on bootloader, IAP, OTA, firmware update, dual-bank, flash programming review.
---

# IAP / BootLoader Code Review

This skill reviews firmware that supports In-Application Programming (IAP) —
bootloaders, OTA updaters, and dual-program architectures. It is a **review-only**
skill; do not include IAP logic during normal coding. Invoke this when:

- Reviewing a BootLoader implementation
- Reviewing OTA/dual-bank update logic
- Verifying flash partition integrity
- Checking application handoff correctness

---

## 1. Flash Partition Layout

### Expected Layout

```
FLASH_BASE ─── BootLoader Region   (small, no RTOS, minimal peripherals)
  ├── Vector Table
  ├── BootLoader Code
  └── Shared Config / Magic Flags (optional)

APP_BASE   ─── Application Region  (full firmware, RTOS, all features)
  ├── Vector Table
  ├── Application Code
  └── End of Flash
```

### Review Checklist

- [ ] Partition boundaries are defined as linker symbols or `#define` constants
- [ ] BootLoader and Application use the **same** `APP_BASE` value
- [ ] `APP_BASE` is aligned to flash page/sector boundary (check datasheet)
- [ ] BootLoader region is sized to fit actual code + vector table + config
- [ ] No overlap between BootLoader and Application regions
- [ ] Shared data region (if any) has defined protocol for read/write access
- [ ] Flash sector erase granularity is respected at partition boundaries

### Common Failure

```
// WRONG: BootLoader and Application disagree on APP_BASE
// BootLoader linker:  APP_BASE = 0x08004000
// Application linker: APP_BASE = 0x08008000
// Result: BootLoader jumps to wrong address → hard fault or garbage execution
```

**Verify:** Both projects' linker scripts (`.ld` / `.sct` / `.icf`) must define
the same `APP_BASE`. A mismatch silently boots the wrong image.

---

## 2. Application Vector Table (VTOR)

### Review Checklist

- [ ] Application sets `SCB->VTOR` as its **first action**, before enabling any interrupt
- [ ] `SCB->VTOR` points to the Application's vector table address (typically `APP_BASE`)
- [ ] VTOR is set in `Reset_Handler` or very early in `SystemInit()`, not in `main()`
- [ ] No interrupt is enabled before VTOR is set

### Correct Sequence

```c
// In Application's startup code or SystemInit():
void SystemInit(void)
{
    // 1. Set vector table to Application region
    SCB->VTOR = APP_BASE;

    // 2. Configure clocks, etc.
    // ...
}
```

### Common Failure

```c
// WRONG: VTOR set too late
int main(void)
{
    HAL_Init();              // ← SysTick interrupt fires here
    SystemClock_Config();    //   with BootLoader's vector table still active
    SCB->VTOR = APP_BASE;   // ← Too late! SysTick may have jumped to BootLoader handler
    // ...
}
```

---

## 3. BootLoader → Application Handoff

### Review Checklist

- [ ] Disable SysTick before jumping (`SysTick->CTRL = 0`)
- [ ] Mask all interrupts before jumping (`__disable_irq()`)
- [ ] De-init peripherals that Application will re-init (UART, SPI, I2C, DMA, timers)
- [ ] Set MSP (Main Stack Pointer) from Application's vector table
- [ ] Jump to Application's Reset_Handler (not `main()`)
- [ ] No stale interrupt flags left pending in NVIC

### Correct Handoff Sequence

```c
void boot_jump_to_app(uint32_t app_addr)
{
    // 1. Disable all interrupts
    __disable_irq();

    // 2. Disable SysTick
    SysTick->CTRL = 0;
    SysTick->VAL  = 0;

    // 3. De-init peripherals (HAL_DeInit or manual)
    HAL_DeInit();

    // 4. Clear all NVIC pending interrupts
    for (uint32_t i = 0; i < 8; i++) {
        NVIC->ICER[i] = 0xFFFFFFFF;  // Disable
        NVIC->ICPR[i] = 0xFFFFFFFF;  // Clear pending
    }

    // 5. Set MSP from Application's vector table
    uint32_t app_msp = *(volatile uint32_t *)app_addr;
    __set_MSP(app_msp);

    // 6. Set VTOR to Application
    SCB->VTOR = app_addr;

    // 7. Get Reset_Handler address (second word in vector table)
    uint32_t reset_handler = *(volatile uint32_t *)(app_addr + 4);

    // 8. Re-enable interrupts (Application will configure its own handlers)
    __enable_irq();

    // 9. Jump
    ((void (*)(void))reset_handler)();
}
```

### Common Failures

- Jumping to `main()` instead of Reset_Handler — skips hardware init
- Not disabling SysTick — BootLoader's tick handler fires with Application's stack
- Leaving pending NVIC interrupts — stale interrupt fires immediately after jump
- Not setting MSP — Application starts with BootLoader's stack pointer

---

## 4. Image Validation

### Review Checklist

- [ ] Application image validated **before** jumping (magic number, CRC, or signature)
- [ ] Validation is done on the actual flash content, not a cached value
- [ ] CRC algorithm matches between writer and verifier
- [ ] If using signatures, the public key is stored in BootLoader (not derived from image)
- [ ] Invalid image → BootLoader enters recovery/upgrade mode, does NOT jump
- [ ] Validation failure is logged or reported (LED blink code, UART message, etc.)

### Validation Methods

#### Magic Number (basic)

```c
#define APP_MAGIC  0xAA55AA55

// At end of Application binary (placed by linker):
// const uint32_t app_magic __attribute__((section(".magic"))) = APP_MAGIC;

bool app_is_valid(void)
{
    // Find magic at known offset in Application region
    extern uint32_t __app_magic_addr;  // linker symbol
    return (*(volatile uint32_t *)&__app_magic_addr) == APP_MAGIC;
}
```

#### CRC32 (recommended)

```c
bool app_crc_valid(void)
{
    uint32_t stored_crc = *(volatile uint32_t *)APP_CRC_ADDR;
    uint32_t calc_crc   = crc32_compute((const uint8_t *)APP_BASE,
                                         APP_SIZE - 4);  // exclude CRC word itself
    return stored_crc == calc_crc;
}
```

#### Cryptographic Signature (LV3 / security-critical)

```c
bool app_signature_valid(void)
{
    const uint8_t *image = (const uint8_t *)APP_BASE;
    uint32_t image_size  = *(volatile uint32_t *)APP_SIZE_ADDR;
    const uint8_t *sig   = (const uint8_t *)APP_SIG_ADDR;

    return ed25519_verify(image, image_size, sig, bootloader_public_key);
}
```

---

## 5. Upgrade Flow

### Review Checklist

- [ ] Upgrade can be triggered by: key press, magic flag in shared RAM, external command
- [ ] New image is written to a staging area or directly to Application region
- [ ] Flash erase is done sector-by-sector (not all at once) to allow recovery
- [ ] Power loss during write → BootLoader detects incomplete image, enters recovery
- [ ] After successful write, image is validated before marking as bootable
- [ ] Rollback mechanism exists if new image fails validation at boot

### Recommended State Machine

```
IDLE → CHECK_UPDATE_FLAG → VALIDATE_NEW_IMAGE → ERASE_APP → WRITE_IMAGE
  → VERIFY_IMAGE → SET_BOOTABLE_FLAG → JUMP_TO_APP

At any step: failure → RECOVERY_MODE (LED blink + wait for new image via UART/USB)
```

---

## 6. Dual-Bank / A-B Update (LV3)

For MCUs with dual-bank flash (e.g., STM32H7 with dual-bank mode):

### Review Checklist

- [ ] Bank swapping is atomic (option byte or hardware flag)
- [ ] Active bank is always bootable during update of inactive bank
- [ ] Bank swap takes effect only after reset + validation
- [ ] Both banks have independent vector tables and VTOR settings
- [ ] Shared data between banks uses a dedicated region, not application flash

---

## 7. Security Considerations

### Review Checklist

- [ ] BootLoader flash is write-protected (option bytes / flash protection bits)
- [ ] Application cannot overwrite BootLoader region
- [ ] Debug access is restricted in production (read-out protection level 2 for STM32)
- [ ] Firmware update channel is authenticated (not just integrity-checked)
- [ ] Anti-rollback: version number checked, cannot flash older firmware
- [ ] Secure boot chain verified (if supported by MCU)

---

## Summary of What NOT to Review During Normal Coding

This entire skill is review-only. During normal application coding:

- Do NOT add IAP logic to application code
- Do NOT add BootLoader code to application project
- Do NOT reference `APP_BASE` or flash layout in application code
- Do NOT add `SCB->VTOR` manipulation unless you are writing startup code

IAP is a separate concern with its own project, its own build, and its own review cycle.
