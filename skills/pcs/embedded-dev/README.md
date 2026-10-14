# Embedded Full-Chain Development — Claude Code Skill

A [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills) covering the entire embedded development lifecycle: project scaffolding, architecture, coding, documentation, testing, code review, build, and flash deployment.

## Tier Rating System

Every section is tier-rated. Rate your target first, then apply only what matters:

| Tier | Chips | Flash | RAM | Example |
|------|-------|-------|-----|---------|
| **LV1** | 8051, STC, ATtiny, ATmega | < 64 KB | < 8 KB | STC89C52, ATmega328P |
| **LV2** | STM32F0/F1/F4, ESP32, nRF52 | 64 KB – 1 MB | 8 KB – 256 KB | STM32F103, ESP32 |
| **LV3** | STM32H7, i.MX RT, Linux SoC | > 1 MB | > 256 KB | STM32H743, i.MX RT1060 |

## What It Covers

| Section | Content |
|---------|---------|
| 1. Quick Tier Rating | 30-second chip classification |
| 2. Project Scaffolding | Directory structure (PlatformIO/ESP-IDF patterns) |
| 3. Architecture Layering | 5-layer model: APP/SERVICE/DRIVER/HAL/BSP |
| 4. Coding Standards | Naming, types, memory, macros, headers (tier-rated) |
| 5. Concurrency & ISR | Bare-metal → ISR+RTOS → full RTOS (tier-rated) |
| 6. Memory & Power | Layout, DMA, low-power modes |
| 7. Error Handling | Status codes, assert, peripheral probe retry |
| 8. Toolchain & Build | CMake, compiler flags, static analysis, unit tests |
| 9. Documentation | Doxygen templates, function comments, WHY-not-WHAT |
| 10. Code Review | Comprehensive checklist (tier-rated) |
| 11. Flash & Debug | probe-rs, OpenOCD, J-Link, esptool, avrdude, stcgal |
| 12. Common Mistakes | 20+ pitfalls with severity ratings |

## Companion Skills

| Skill | Purpose |
|-------|---------|
| `embedded-iap-review` | IAP/BootLoader code review (flash partition, VTOR, image validation) |
| `embedded-doxygen` | Doxygen comment generation with embedded-specific annotations |

## Installation

```bash
cd ~/.claude/skills
git clone https://github.com/YOUR_USERNAME/embedded-dev.git
```

Or copy `skill.md` to `~/.claude/skills/embedded-dev/skill.md`.

## Usage

Activates automatically when working on embedded C/C++ projects. No slash command needed.

## Architecture

The 5-layer model (replaces the old BSP/Driver/Middleware/System/Tasks that had conflicts):

```
APP/         Business logic, state machines, tasks
SERVICE/     Middleware wrappers (RTOS, lwIP, FatFS, LVGL)
DRIVER/      Peripheral drivers (I2C, SPI, UART, GPIO)
HAL/         Vendor SDK wrapped behind thin adapters
BSP/         Board init (clock, pin mux, NVIC)
```

Key: BSP is always bare-metal. DRIVER is RTOS-agnostic. SERVICE wraps RTOS for APP.

## References

- MISRA-C:2012, CERT-C, Barr Group Embedded C Coding Standard
- PlatformIO, ESP-IDF, Zephyr RTOS project patterns
- FreeRTOS coding conventions
- Embedded Artistry, Interrupt (Memfault)
- ThrowTheSwitch (Unity/CMock/Ceedling)

## License

MIT
