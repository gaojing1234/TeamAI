# MCU Design Reference

## RTOS Selection Criteria

| Criterion | Weight | FreeRTOS | RT-Thread | Zephyr | µC/OS-III |
|-----------|--------|----------|-----------|--------|-----------|
| Safety certification | 30% | ★★★★★ (SAFERTOS) | ★★★ | ★★★★ | ★★★★ |
| RAM footprint | 20% | 6-10 KB | 3-8 KB | 8-16 KB | 6-20 KB |
| MCU vendor support | 20% | ★★★★★ | ★★★★ | ★★★★ | ★★★ |
| Community/ecosystem | 15% | ★★★★★ | ★★★★ | ★★★★ | ★★★ |
| IPC richness | 15% | ★★★ | ★★★★★ | ★★★★ | ★★★★ |

**Recommendation**: FreeRTOS for IEC 61508 path, RT-Thread for domestic ecosystem, Zephyr for multi-core AMP.

## Task Partitioning Template

```
Priority  Task Name           Period    WCET     Trigger     Description
--------  ------------------- --------- -------- ----------- ---------------------------
31        Protection_Task     Event     < 50µs   FPGA IRQ    Emergency stop, PWM shutdown
28        Fault_Monitor       1ms       < 1ms    Timer       Temp/voltage/current check
25        CAN_Comm            10ms      < 500µs  Timer       DSP data exchange
22        Modbus_Comm         20ms      < 2ms    Timer       HMI/host communication
20        Data_Storage        100ms     < 5ms    Queue       Event log, waveform capture
18        System_Monitor      1000ms    < 10ms   Timer       Watchdog, memory, health
```

## IPC Mechanism Selection

| Communication | Mechanism | Data Size | Blocking | Use Case |
|---------------|-----------|-----------|----------|----------|
| ISR → Task | Binary semaphore | N/A | 0 (immediate) | Interrupt notification |
| Task → Task (urgent) | Message queue | 8-64 B | 0 (non-blocking) | Fault events |
| Task → Task (bulk) | Message queue | 64-256 B | 10ms max | Data transfer |
| Task → Task (sync) | Event group | N/A | 0 (non-blocking) | Multi-task synchronization |
| Shared resource | Mutex | N/A | 5ms max | Resource protection |

## Fault Isolation Architecture

```
Layer 1: FPGA Hardware Protection (< 1µs)
  - Overcurrent, overvoltage, short circuit
  - Immediate PWM shutdown, trigger MCU interrupt

Layer 2: MCU Software Protection (< 1ms)
  - Over-temperature, undervoltage, communication timeout
  - Power derating, alarm, safe shutdown

Layer 3: DSP Control Protection (< 10ms)
  - Grid code violations, MPPT anomaly, PLL unlock
  - Control strategy switch, power limit, disconnection

Layer 4: Linux/HMI System Protection (< 100ms)
  - System-level anomaly, remote command, maintenance
  - Manual intervention, remote reset, firmware rollback
```

## Flash Partition Layout (2MB Example)

```
Address         Size    Partition           Purpose
0x0800_0000     64KB    Bootloader          Secure boot, OTA management
0x0801_0000     4KB     Boot_Params         Boot configuration, flags
0x0801_1000     512KB   App_Firmware_A      Primary application
0x0809_0000     8KB     App_Params_A        Application parameters
0x0809_2000     512KB   App_Firmware_B      Backup application (A/B)
0x0810_0000     256KB   OTA_Temp            OTA staging area
0x0814_0000     64KB    Param_Storage       LittleFS parameter filesystem
0x0815_0000     128KB   Event_Log           Circular event buffer
0x0817_0000     500KB   Reserved            Future use
```

## Bootloader State Machine

```
States:
  INIT        → Hardware init, clock configuration
  SELF_TEST   → RAM/Flash/CRC verification
  BOOT_SELECT → Choose firmware A or B
  VERIFY      → CRC32 + ECDSA-P256 signature check
  OTA_CHECK   → Check for pending OTA update
  OTA_INSTALL → Copy OTA temp to app partition
  JUMP        → Transfer control to application
  RECOVERY    → Rollback to backup firmware
  ERROR       → Safe state, wait for intervention

Transitions:
  INIT → SELF_TEST: Clock stable
  SELF_TEST → BOOT_SELECT: All tests pass
  SELF_TEST → ERROR: Test failure or timeout (10s)
  BOOT_SELECT → VERIFY: Firmware selected
  BOOT_SELECT → RECOVERY: Both firmware invalid
  VERIFY → OTA_CHECK: Signature valid
  VERIFY → BOOT_SELECT: Signature invalid (try other)
  OTA_CHECK → OTA_INSTALL: OTA flag set + valid
  OTA_CHECK → JUMP: No pending OTA
  OTA_INSTALL → VERIFY: Installation complete
  JUMP → (application): Jump successful
  RECOVERY → VERIFY: Backup firmware found
  RECOVERY → ERROR: No valid firmware
```

## Secure Boot Trust Chain

```
ROM Boot (Root of Trust)
  ├── Verify Bootloader signature (ECDSA-P256)
  │     └── Stored in OTP/eFuse: Root Public Key
  └── Bootloader
        ├── Verify Application signature (ECDSA-P256)
        │     └── Stored in Bootloader: App Public Key
        └── Application
              └── Runtime integrity checks
```

## CAN Protocol Frame Definition

| CAN ID | Priority | Direction | Description |
|--------|----------|-----------|-------------|
| 0x001 | Highest | MCU→DSP | Emergency stop |
| 0x100 | High | Bidirectional | Heartbeat (1s) |
| 0x200 | Medium | DSP→MCU | Realtime data (10ms) |
| 0x201 | Medium | MCU→DSP | Status report (10ms) |
| 0x300 | Medium | MCU→DSP | Fault report |
| 0x400 | Low | HMI→MCU | Parameter read |
| 0x401 | Low | HMI→MCU | Parameter write |

## Memory Management

- Static allocation for all task stacks and IPC objects
- Memory pool (64B blocks × 32) for dynamic message passing
- Stack watermark monitoring for overflow detection
- Heap usage tracking with fragmentation alert at >70%
