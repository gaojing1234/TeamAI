# Linux Application Architecture Reference

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        User Space                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  HMI App    │  │  Data Logger│  │  Cloud Agent│  │  OTA Manager│   │
│  │  (Qt/Web)   │  │  (SQLite)   │  │  (MQTT)     │  │  (SWUpdate) │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │           │
│         ▼                ▼                ▼                ▼           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Middleware Layer                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │   │
│  │  │ Modbus  │  │ IEC 104 │  │ MQTT    │  │ OPC UA  │           │   │
│  │  │ Stack   │  │ Stack   │  │ Client  │  │ Server  │           │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                        Kernel Space                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  SPI Driver │  │  UART Driver│  │  CAN Driver │  │  GPIO Driver│   │
│  │  (MCU comm) │  │  (Debug)    │  │  (DSP comm) │  │  (Control)  │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                        Hardware                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │   MCU   │  │   DSP   │  │   FPGA  │  │  Flash  │  │  RAM    │     │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Process Partitioning

### Critical Process List

| Process | Priority | Scheduling | Period | Description |
|---------|----------|------------|--------|-------------|
| rt_control | 99 | SCHED_FIFO | 1ms | Real-time control adjunct |
| data_acq | 90 | SCHED_FIFO | 10ms | Data acquisition from MCU/DSP |
| fault_handler | 85 | SCHED_FIFO | Event | Fault detection and response |
| hmi_server | 50 | SCHED_RR | 50ms | HMI web server / display |
| data_logger | 40 | SCHED_OTHER | 100ms | Historical data recording |
| cloud_agent | 30 | SCHED_OTHER | 1s | MQTT/cloud communication |
| ota_manager | 20 | SCHED_OTHER | Event | Firmware update management |
| system_mon | 10 | SCHED_OTHER | 5s | System health monitoring |

### Process Communication

```
┌─────────────┐     Shared      ┌─────────────┐
│ rt_control  │◄───Memory───────│ data_acq    │
│             │   (lock-free)   │             │
└──────┬──────┘                 └──────┬──────┘
       │                               │
       │ UNIX socket                   │ UNIX socket
       ▼                               ▼
┌─────────────┐                 ┌─────────────┐
│fault_handler│                 │ data_logger │
│             │                 │  (SQLite)   │
└──────┬──────┘                 └─────────────┘
       │
       │ D-Bus / UNIX socket
       ▼
┌─────────────┐     MQTT        ┌─────────────┐
│  hmi_server │────────────────►│ cloud_agent │
└─────────────┘                 └─────────────┘
```

## Driver Framework

### SPI Driver (MCU Communication)

```c
// Device tree binding
&spi0 {
    status = "okay";
    mcu@0 {
        compatible = "inverter,mcu-spi";
        reg = <0>;
        spi-max-frequency = <10000000>;
        interrupt-parent = <&gpio1>;
        interrupts = <5 IRQ_TYPE_EDGE_FALLING>;
    };
};

// Driver structure
static struct spi_driver mcu_spi_driver = {
    .driver = {
        .name = "mcu-spi",
        .of_match_table = mcu_spi_of_match,
    },
    .probe = mcu_spi_probe,
    .remove = mcu_spi_remove,
};

// Data exchange protocol
struct mcu_data_frame {
    uint16_t voltage_dc;      // 0.1V
    uint16_t current_dc;      // 0.1A
    uint16_t voltage_ac;      // 0.1V
    uint16_t current_ac;      // 0.1A
    uint16_t power_active;    // W
    uint16_t power_reactive;  // var
    uint16_t frequency;       // 0.01Hz
    uint16_t temperature;     // 0.1C
    uint32_t fault_code;
    uint16_t status;
    uint16_t crc16;
} __packed;
```

### CAN Driver (DSP Communication)

```c
// CAN frame types
enum dsp_can_id {
    CAN_ID_HEARTBEAT    = 0x100,
    CAN_ID_REALTIME     = 0x200,
    CAN_ID_COMMAND      = 0x300,
    CAN_ID_PARAMETER    = 0x400,
    CAN_ID_FAULT        = 0x500,
};

// SocketCAN interface
struct can_frame frame;
frame.can_id = CAN_ID_COMMAND;
frame.can_dlc = 8;
memcpy(frame.data, &command, 8);
write(can_socket, &frame, sizeof(frame));
```

## Communication Stack

### Modbus TCP/RTU Gateway

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  HMI / SCADA│────►│ Modbus TCP  │────►│ Modbus RTU  │
│  (Ethernet) │     │ Server      │     │ (RS485)     │
└─────────────┘     │ (port 502)  │     │             │
                    └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │ Register    │
                    │ Mapping     │
                    │ Table       │
                    └─────────────┘

Register map:
  3xxxx: Input registers (read-only measurements)
  4xxxx: Holding registers (read-write parameters)
  0xxxx: Coils (read-write digital outputs)
  1xxxx: Discrete inputs (read-only digital inputs)
```

### IEC 60870-5-104 Implementation

```
States:
  IDLE          → No connection
  CONNECTING    → TCP handshake
  STARTDT_WAIT  → Waiting for STARTDT act
  RUNNING       → Data exchange
  STOPDT_WAIT   → Waiting for STOPDT act
  DISCONNECTING → Graceful close

Timers:
  T0: Connection timeout (30s)
  T1: Send/test timeout (15s)
  T2: Acknowledge timeout (10s)
  T3: Test frame timeout (20s)

ASDU types:
  M_ME_NC_1: Measured value, short floating point
  M_SP_TB_1: Single point with time tag
  C_SC_NA_1: Single command
  C_SE_NC_1: Set point command, short floating point
```

### MQTT Client

```c
// Topics structure
"device/{device_id}/telemetry"    → Periodic data upload
"device/{device_id}/alarm"        → Alarm notifications
"device/{device_id}/command"      → Remote commands
"device/{device_id}/config"       → Configuration updates
"device/{device_id}/firmware/ota" → OTA trigger

// QoS selection
Telemetry: QoS 0 (fire and forget)
Alarm:     QoS 1 (at least once)
Command:   QoS 1 (at least once)
OTA:       QoS 2 (exactly once)
```

## Storage Architecture

### Filesystem Layout

```
/
├── boot/           → Kernel, DTB, boot scripts (read-only)
├── rootfs/         → Root filesystem (read-only, squashfs)
├── overlay/        → Writable overlay (ext4, journaled)
│   ├── etc/        → Configuration files
│   ├── var/        → Logs, temporary data
│   └── home/       → User data
├── data/           → Application data partition (ext4)
│   ├── db/         → SQLite databases
│   ├── logs/       → System logs
│   ├── firmware/   → OTA images
│   └── backup/     → Configuration backups
└── recovery/       → Recovery partition (read-only)
```

### Data Logger (SQLite Schema)

```sql
-- Real-time measurements (circular buffer)
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,  -- Unix timestamp
    voltage_dc REAL,
    current_dc REAL,
    voltage_ac REAL,
    current_ac REAL,
    power_active REAL,
    power_reactive REAL,
    frequency REAL,
    temperature REAL
);
CREATE INDEX idx_measurements_ts ON measurements(timestamp);

-- Event log
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    event_type TEXT NOT NULL,  -- 'alarm', 'warning', 'info', 'fault'
    source TEXT NOT NULL,      -- 'mcu', 'dsp', 'fpga', 'linux'
    code INTEGER NOT NULL,
    description TEXT,
    value REAL,
    acknowledged INTEGER DEFAULT 0
);
CREATE INDEX idx_events_ts ON events(timestamp);
CREATE INDEX idx_events_type ON events(event_type);

-- Fault waveform recording
CREATE TABLE waveforms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    trigger_code INTEGER,
    pre_trigger_ms INTEGER,
    sample_rate INTEGER,
    channel_count INTEGER,
    data BLOB  -- Compressed waveform data
);
```

## OTA Update Strategy

### SWUpdate Configuration

```yaml
# sw-description
software = {
    version = "1.0.0";
    description = "Inverter firmware update";

    images: (
        {
            filename = "uImage";
            device = "/dev/mmcblk0p1";
            type = "raw";
        },
        {
            filename = "rootfs.squashfs";
            device = "/dev/mmcblk0p2";
            type = "raw";
        },
        {
            filename = "mcu_firmware.bin";
            device = "/dev/mmcblk0p5";  # MCU OTA partition
            type = "raw";
        }
    );

    scripts: (
        {
            filename = "postinstall.sh";
            type = "shellscript";
        }
    );

    bootloader: (
        {
            name = "bootcount";
            value = "3";  # Max boot attempts before rollback
        }
    );
}
```

### OTA State Machine

```
States:
  IDLE            → No update in progress
  CHECKING        → Checking for updates (HTTP/MQTT)
  DOWNLOADING     → Downloading update package
  VERIFYING       → Verifying checksum and signature
  INSTALLING      → Installing to inactive partition
  MCU_UPDATING    → Updating MCU firmware via SPI
  REBOOTING       → Rebooting to new firmware
  CONFIRMING      → Waiting for health check
  ROLLING_BACK    → Rolling back to previous version
  ERROR           → Update failed

Transitions:
  IDLE → CHECKING: Periodic check or manual trigger
  CHECKING → DOWNLOADING: Update available
  CHECKING → IDLE: No update
  DOWNLOADING → VERIFYING: Download complete
  DOWNLOADING → ERROR: Download failed
  VERIFYING → INSTALLING: Checksum valid + signature verified
  VERIFYING → ERROR: Verification failed
  INSTALLING → MCU_UPDATING: Linux partitions installed
  MCU_UPDATING → REBOOTING: MCU firmware transferred
  REBOOTING → CONFIRMING: System booted successfully
  CONFIRMING → IDLE: Health check passed
  CONFIRMING → ROLLING_BACK: Health check failed / timeout
  ROLLING_BACK → REBOOTING: Previous version restored
  ERROR → IDLE: Error acknowledged
```

## System Monitoring

### Health Check Metrics

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU usage | > 90% for 30s | Log warning |
| Memory usage | > 85% | Restart non-critical processes |
| Disk usage | > 90% | Purge old logs |
| Temperature | > 75°C | Derate, alert |
| Process crash | 3 times in 5min | Enter safe mode |
| Watchdog timeout | 30s | Hard reboot |

### Watchdog Implementation

```c
// Hardware watchdog
int wdt_fd = open("/dev/watchdog", O_RDWR);
ioctl(wdt_fd, WDIOC_SETTIMEOUT, &timeout);  // 30 seconds

// Software watchdog thread
void *watchdog_thread(void *arg) {
    while (1) {
        // Check all critical processes
        if (all_processes_healthy()) {
            write(wdt_fd, "\0", 1);  // Kick watchdog
        }
        sleep(10);
    }
}
```

## HMI Architecture

### Web-Based HMI Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Client)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Dashboard   │  │  Trends     │  │  Alarms     │             │
│  │ (React/Vue) │  │  (Chart.js) │  │  (Table)    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│                        REST API / WebSocket                     │
├─────────────────────────────────────────────────────────────────┤
│                        Server (Node.js / Go)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Auth        │  │ Data API    │  │ WebSocket   │             │
│  │ (JWT)       │  │ (CRUD)      │  │ (Realtime)  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│                        Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ SQLite      │  │ Redis       │  │ File System │             │
│  │ (History)   │  │ (Cache)     │  │ (Config)    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Page Structure

| Page | Content | Refresh Rate |
|------|---------|--------------|
| Dashboard | Power, voltage, current, status | 1s (WebSocket) |
| Trends | Historical curves (30 days) | On-demand |
| Alarms | Active/historical alarms | 5s |
| Parameters | System configuration | Manual |
| Maintenance | Diagnostics, calibration | Manual |
| OTA Update | Firmware upload, status | Manual |
