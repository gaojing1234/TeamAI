# FPGA Design Reference

## Top-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FPGA Top Level                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  ADC        │  │  PWM        │  │  Protection │  │  Comm       │   │
│  │  Interface  │  │  Generator  │  │  Logic      │  │  Interface  │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │           │
│         ▼                ▼                ▼                ▼           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Data Path Pipeline                           │   │
│  │  ADC → CIC → FIR → RMS → Park → Protection → Status            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         │                │                │                │           │
│         ▼                ▼                ▼                ▼           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Clock &    │  │  Reset      │  │  Register   │  │  Interrupt  │   │
│  │  PLL        │  │  Manager    │  │  Bank       │  │  Controller │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Clock & Reset Architecture

### Clock Domain Planning

| Domain | Source | Frequency | Purpose | Crossing Strategy |
|--------|--------|-----------|---------|-------------------|
| clk_adc | ADC oscillator | 10-100 MHz | ADC sampling | Source domain |
| clk_sys | System PLL | 50-200 MHz | Processing logic | Primary domain |
| clk_pwm | PWM timer | 10-150 MHz | PWM generation | Async FIFO |
| clk_comm | Comm PLL | 10-50 MHz | SPI/UART/CAN | Async FIFO |
| clk_mem | Memory ctrl | 100-400 MHz | External RAM | Native interface |

### Clock Domain Crossing (CDC)

```
Single-bit signal:
  src_clk ──► [FF] ──► [FF] ──► [FF] ──► dst_clk
               │         │         │
               └─────────┴─────────┘
               3-stage synchronizer (MTBF > 10^9 hours)

Multi-bit signal:
  src_clk ──► [Gray Encode] ──► [Sync] ──► [Gray Decode] ──► dst_clk
               │                                    │
               └──── Async FIFO (gray-coded ptr) ───┘
```

### Reset Architecture

```
Power-on ──► [POR] ──► [Reset Sync] ──► [Global Reset]
                    │
                    ├── clk_adc domain reset
                    ├── clk_sys domain reset
                    ├── clk_pwm domain reset
                    └── clk_comm domain reset

Reset sequence:
  1. Power stable (POR threshold)
  2. Clock locked (PLL lock signal)
  3. Release reset (synchronized to each domain)
  4. Initialization complete flag
```

## Data Path Pipeline

### Decimation Filter (CIC + FIR)

```
ADC Data (fs = 10 MHz)
    │
    ▼
┌─────────────┐
│ CIC Filter  │  Decimation factor M = 16
│ (N=3, R=16) │  Output rate = fs/M = 625 kHz
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ FIR Compens │  Compensation for CIC droop
│ (23 taps)   │  Passband ripple < 0.01 dB
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Half-band   │  Decimation factor = 2
│ FIR Filter  │  Output rate = 312.5 kHz
└──────┬──────┘
       │
       ▼
Filtered Data (for RMS, protection, DSP interface)
```

### RMS Calculation

```
Input x(n)
    │
    ▼
┌─────────────┐
│ x(n)^2      │  Square input
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Moving Avg  │  N-point averaging (N = samples/cycle)
│ Σ/N         │  Typically 128-256 samples
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ √ (sqrt)    │  Square root (CORDIC or LUT)
└──────┬──────┘
       │
       ▼
RMS output (updated every cycle)

Latency: N samples + pipeline depth
Precision: 16-bit input → 32-bit intermediate → 16-bit output
```

## Hardware Protection Logic

### Fault Detection & Latch

```
┌─────────────────────────────────────────────────────────────────┐
│                    Protection Logic Block                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ADC_ch0 ──►[Compare]──► Overcurrent ──┐                       │
│              (threshold)                │                       │
│                                         ▼                       │
│  ADC_ch1 ──►[Compare]──► Overvoltage ──[OR]──►[Latch]──► FAULT │
│              (threshold)                │       ▲               │
│                                         │       │               │
│  ADC_ch2 ──►[Compare]──► Undervoltage ─┘       │               │
│              (threshold)                        │               │
│                                                 │               │
│  External ──►[Debounce]──► HW_TRIP ─────────────┘               │
│              (10µs)                                              │
│                                                                 │
│  MCU_CLR ──►[AND Gate]──► Latch Clear                           │
│              (requires MCU acknowledge)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Latch behavior:
  - Set on any fault condition (1 clock cycle)
  - Clear only by MCU acknowledge + fault condition removed
  - Fault status readable by MCU via register bus
```

### Protection Timing Budget

| Stage | Latency | Cumulative |
|-------|---------|------------|
| ADC acquisition | 100 ns | 100 ns |
| Decimation filter | 200 ns | 300 ns |
| Threshold comparison | 10 ns | 310 ns |
| Fault latch | 10 ns | 320 ns |
| PWM shutdown | 50 ns | 370 ns |
| **Total** | | **< 500 ns** |

## Communication IP Selection

### IP Comparison

| Protocol | Latency | Bandwidth | Complexity | Use Case |
|----------|---------|-----------|------------|----------|
| SPI Slave | < 1 µs | 10-50 Mbps | Low | MCU interface |
| UART | < 10 µs | 115.2 kbps-1 Mbps | Low | Debug/monitor |
| CAN 2.0B | < 100 µs | 1 Mbps | Medium | DSP interface |
| EtherCAT | < 1 ms | 100 Mbps | High | Industrial comm |
| Custom serial | < 500 ns | 10-100 Mbps | Low | DSP high-speed |

### SPI Slave Interface

```
MCU (Master)          FPGA (Slave)
  SCLK ─────────────────► SCLK
  MOSI ─────────────────► MOSI
  MISO ◄───────────────── MISO
  CS_n ─────────────────► CS_n

Register map:
  0x00: Status (RO)        - Fault flags, PLL lock, etc.
  0x04: Fault_code (RO)    - Fault identification
  0x08: Control (RW)       - Enable, mode select
  0x0C: Threshold_0 (RW)   - Overcurrent threshold
  0x10: Threshold_1 (RW)   - Overvoltage threshold
  0x14: Data_0 (RO)        - RMS current
  0x18: Data_1 (RO)        - RMS voltage
  0x1C: Data_2 (RO)        - Active power
  0x20: Debug (RO)         - Pipeline status
```

## IP-XACT Component Description

```xml
<?xml version="1.0" encoding="UTF-8"?>
<spirit:component xmlns:spirit="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009">
  <spirit:vendor>xilinx</spirit:vendor>
  <spirit:library>inverter</spirit:library>
  <spirit:name>protection_logic</spirit:name>
  <spirit:version>1.0</spirit:version>

  <spirit:busInterfaces>
    <spirit:busInterface>
      <spirit:name>spi_slave</spirit:name>
      <spirit:busType spirit:vendor="xilinx" spirit:library="interface" spirit:name="spi" spirit:version="1.0"/>
      <spirit:slave/>
    </spirit:busInterface>
    <spirit:busInterface>
      <spirit:name>fault_output</spirit:name>
      <spirit:busType spirit:vendor="xilinx" spirit:library="interface" spirit:name="gpio" spirit:version="1.0"/>
      <spirit:master/>
    </spirit:busInterface>
  </spirit:busInterfaces>

  <spirit:model>
    <spirit:ports>
      <spirit:port>
        <spirit:name>clk_sys</spirit:name>
        <spirit:wire><spirit:direction>in</spirit:direction></spirit:wire>
      </spirit:port>
      <spirit:port>
        <spirit:name>rst_n</spirit:name>
        <spirit:wire><spirit:direction>in</spirit:direction></spirit:wire>
      </spirit:port>
      <spirit:port>
        <spirit:name>adc_data</spirit:name>
        <spirit:wire><spirit:direction>in</spirit:direction><spirit:width>16</spirit:width></spirit:wire>
      </spirit:port>
      <spirit:port>
        <spirit:name>fault_out</spirit:name>
        <spirit:wire><spirit:direction>out</spirit:direction></spirit:wire>
      </spirit:port>
    </spirit:ports>
  </spirit:model>
</spirit:component>
```

## Resource Estimation

| Module | LUTs | FFs | BRAM | DSP | Fmax |
|--------|------|-----|------|-----|------|
| CIC filter | 500 | 300 | 0 | 4 | 200 MHz |
| FIR filter | 800 | 600 | 2 | 16 | 150 MHz |
| RMS calculator | 1200 | 800 | 1 | 8 | 180 MHz |
| Protection logic | 200 | 150 | 0 | 0 | 300 MHz |
| SPI slave | 300 | 200 | 0 | 0 | 100 MHz |
| Register bank | 400 | 500 | 0 | 0 | 200 MHz |
| **Total** | **3400** | **2550** | **3** | **28** | |

Target utilization: < 80% for timing closure margin

## Verilog Module Hierarchy

```
top_level
├── clk_rst_inst
│   ├── mmcm_pll (clock generation)
│   └── reset_sync (reset synchronizers)
├── adc_interface_inst
│   ├── lvds_receiver (if differential)
│   └── adc_data_align
├── data_path_inst
│   ├── cic_filter
│   ├── fir_compensator
│   ├── halfband_fir
│   ├── rms_calculator
│   └── park_transform (optional)
├── protection_inst
│   ├── threshold_compare
│   ├── fault_latch
│   └── debounce_logic
├── pwm_generator_inst
│   ├── dead_time_insert
│   └── pwm_counter
├── comm_interface_inst
│   ├── spi_slave
│   ├── register_bank
│   └── interrupt_controller
└── debug_inst
    ├── ila_probe (if Xilinx)
    └── vio_control (if Xilinx)
```
