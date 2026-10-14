---
name: embedded-doxygen
description: >
  Use when generating, reviewing, or bulk-adding Doxygen comments to embedded C/C++ code.
  Reads project templates, generates file headers, function comments with embedded-specific
  annotations (ISR safety, thread safety, parameter direction, hardware preconditions),
  and organizes modules with @defgroup. Triggers on Doxygen, code comments, documentation
  generation, file headers, function documentation.
---

# Embedded Doxygen Comment Generator

Generates Doxygen-style documentation comments for embedded C/C++ code. Optimized for
firmware conventions: parameter direction (`in`/`out`), ISR safety, thread safety,
hardware preconditions, and register documentation.

---

## 1. When to Invoke

- Adding file headers to new or existing `.c` / `.h` files
- Generating function documentation for public APIs
- Batch-adding Doxygen comments to an entire module
- Reviewing existing comments for completeness
- Creating `@defgroup` module organization

---

## 2. Configuration

### Doxyfile Settings for Embedded C

```
PROJECT_NAME           = "My Firmware"
OPTIMIZE_OUTPUT_FOR_C  = YES
EXTRACT_STATIC         = YES
EXTRACT_PRIVATE        = YES
GENERATE_TODOLIST      = YES
GENERATE_BUGLIST       = YES
PREDEFINED             = "STM32F4xx" "__weak=" "HAL_MODULE_ENABLED"
JAVADOC_AUTOBRIEF      = YES
```

### Template File (Optional)

If a project has `tools/doxygen_template.h`, read it first for project-specific
comment style. Otherwise use the defaults below.

---

## 3. File Header Template

### Standard

```c
/**
 * @file    filename.c
 * @brief   One-line description of this file's purpose.
 * @author  <name>
 * @date    <YYYY-MM-DD> (optional — VCS is source of truth)
 * @note    Datasheet reference, errata notes, or other important context.
 */
```

### With Module Grouping

```c
/**
 * @file    mpu6050_drv.c
 * @brief   MPU6050 IMU driver — accel/gyro sample read, FIFO drain.
 * @author  <name>
 * @ingroup MPU6050_Driver
 * @note    Datasheet rev 4.2; errata 3.1 sample-rate jitter workaround.
 */
```

---

## 4. Function Comment Template

### Basic (LV1)

```c
/**
 * @brief One-line description of what this function does.
 *
 * @param[in]  param1  Description, units, valid range.
 * @param[out] param2  Description of output.
 * @return Description of return value.
 */
```

### Full (LV2/LV3 — recommended)

```c
/**
 * @brief Read accelerometer XYZ samples from the FIFO.
 *
 * @details
 * Drains up to @p count samples from the MPU6050 hardware FIFO.
 * Each sample is 6 bytes (3 axes x 2 bytes, big-endian).
 * The buffer is populated with raw register values; apply
 * mpu6050_scale_accel() to convert to g-units.
 *
 * @param[out] buf    Destination buffer, must hold at least @p count * 6 bytes.
 *                    Caller owns the buffer. Valid until function returns.
 * @param[in]  count  Number of samples to read. Range: [1, 128].
 *                    Values outside this range return -EINVAL.
 *
 * @return Number of samples actually read, or negative error code.
 * @retval  >0   Number of samples successfully read.
 * @retval -EINVAL  buf is NULL or count is 0.
 * @retval -EIO     I2C bus error (NACK or timeout).
 * @retval -ENODATA FIFO is empty.
 *
 * @pre    I2C bus initialized via i2c_bus_init().
 * @pre    MPU6050 configured via mpu6050_configure().
 *
 * @note   NOT ISR-safe. Blocks on I2C transfer for up to 5 ms.
 * @note   NOT thread-safe. Caller must provide mutual exclusion if called
 *         from multiple tasks.
 *
 * @warning After wake from STOP mode, the MPU6050 may need re-initialization.
 *          Call mpu6050_probe() first to verify device is responsive.
 *
 * @see mpu6050_scale_accel(), mpu6050_configure()
 */
int16_t mpu6050_read_accel(int16_t *buf, uint8_t count);
```

---

## 5. Embedded-Specific Annotations

Use these annotations consistently across the project:

### Parameter Direction

| Tag | Meaning | When to Use |
|-----|---------|-------------|
| `@param[in]` | Input only, function reads it | Buffers, config structs, scalar values |
| `@param[out]` | Output only, function writes it | Result buffers, status pointers |
| `@param[in,out]` | Both read and written | Buffers that are modified in place |

**Rule:** Every parameter must have a direction tag. No exceptions.

### ISR Safety

| Annotation | Meaning |
|------------|---------|
| `@note ISR-safe.` | Can be called from interrupt context |
| `@note NOT ISR-safe.` | Must NOT be called from interrupt context |
| `@note ISR-safe only with FromISR variant.` | Use the `*_FromISR()` version in ISR |

### Thread Safety

| Annotation | Meaning |
|------------|---------|
| `@note Thread-safe.` | Internal locking, safe from any task |
| `@note NOT thread-safe.` | Caller must provide mutual exclusion |
| `@note Thread-safe if @p mtx is provided.` | Takes a mutex parameter |

### Hardware Preconditions

| Annotation | Meaning |
|------------|---------|
| `@pre` | Hardware or software state required before calling |
| `@warning` | Hardware-specific caveats (timing, power, errata) |

### Common Precondition Examples

```
@pre I2C bus initialized via i2c_bus_init().
@pre GPIO pin configured as alternate function, open-drain.
@pre System clock >= 72 MHz for SPI baud rate requirement.
@pre Peripheral clock enabled for USART1 (RCC_APB2ENR_USART1EN).
```

---

## 6. Enum and Struct Documentation

### Enum

```c
/**
 * @brief MPU6050 gyroscope full-scale range.
 *
 * Maps to GYRO_CONFIG register bits [4:3].
 * Higher range = lower resolution but wider measurement window.
 */
typedef enum {
    MPU6050_GYRO_250DPS  = 0x00,  /**< +/- 250 deg/s,  sensitivity: 131 LSB/deg/s  */
    MPU6050_GYRO_500DPS  = 0x01,  /**< +/- 500 deg/s,  sensitivity: 65.5 LSB/deg/s  */
    MPU6050_GYRO_1000DPS = 0x02,  /**< +/- 1000 deg/s, sensitivity: 32.8 LSB/deg/s  */
    MPU6050_GYRO_2000DPS = 0x03,  /**< +/- 2000 deg/s, sensitivity: 16.4 LSB/deg/s  */
} mpu6050_gyro_range_t;
```

### Struct

```c
/**
 * @brief MPU6050 driver instance.
 *
 * One instance per physical device on the bus.
 * Caller allocates; driver fills @p config during mpu6050_init().
 *
 * @note Access from multiple tasks requires external mutex.
 */
typedef struct {
    i2c_bus_t    *bus;          /**< I2C bus handle (caller-provided).       */
    uint8_t       addr;         /**< 7-bit I2C address (0x68 or 0x69).      */
    mpu6050_gyro_range_t gyro;  /**< Current gyro full-scale setting.       */
    mpu6050_accel_range_t accel;/**< Current accel full-scale setting.      */
    bool          fifo_enabled; /**< true if FIFO drain mode is active.     */
} mpu6050_t;
```

---

## 7. Module Grouping with @defgroup

### In Header File

```c
/**
 * @defgroup MPU6050_Driver MPU6050 IMU Driver
 * @brief    Inertial measurement unit driver for InvenSense MPU6050.
 *
 * Communication over I2C. Supports single-sample and FIFO drain modes.
 *
 * @{
 */

// ... all public declarations ...

/** @} */ // end of MPU6050_Driver
```

### In Source File

```c
/**
 * @addtogroup MPU6050_Driver
 * @{
 */

// ... all implementations ...

/** @} */ // end of MPU6050_Driver
```

---

## 8. Batch Generation Workflow

When asked to add Doxygen comments to an entire file or module:

1. **Read the file** to understand its purpose and all public functions
2. **Identify the module** — what `@defgroup` does it belong to?
3. **Generate file header** with `@file`, `@brief`, `@ingroup`
4. **For each public function:**
   - Determine parameter directions (in/out/in,out)
   - Determine return semantics (success value, error codes)
   - Determine ISR safety (does it touch shared state? hardware?)
   - Determine thread safety (does it need a mutex?)
   - Add `@pre` for hardware prerequisites
   - Add `@warning` for errata or timing constraints
5. **For each enum/struct:** add brief description + member comments
6. **Wrap in @defgroup / @addtogroup** if not already grouped
7. **Do NOT add comments to static/private functions** unless they contain
   non-obvious logic (errata workaround, timing constraint, algorithm choice)

---

## 9. Comment Quality Rules

- **Write WHY, not WHAT.** `// Reset FIFO pointer` is noise. `// Reset FIFO to drain stale data after wake from sleep` is useful.
- **One-line @brief** — if you need two lines, the function is too complex.
- **No date in comments** — VCS tracks history.
- **No author in function comments** — VCS tracks authorship. Author goes in file header only.
- **No comments on getters/setters** unless they have side effects or constraints.
- **Every @param must have a description** — bare `@param buf` is worse than no comment.

---

## 10. Doxygen Don'ts

| Don't | Why |
|-------|-----|
| Add `@file` to every function | It belongs in the file header only |
| Use `@brief` inline (`/**< brief */`) for functions | Use the block form before the declaration |
| Document the obvious (`@param count number of items`) | Describe constraints, not names |
| Add `@return void` | Void functions have no return to document |
| Use `@throws` | C doesn't have exceptions. Use `@retval` for error codes |
| Put version history in comments | VCS is the source of truth |
| Document private/static functions unless non-obvious | Keep documentation surface small |
