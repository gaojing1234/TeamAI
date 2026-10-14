# DSP Control Architecture Reference

## Control Mode Architecture

### Dual-Mode Operation: PQ (Grid-Connected) vs VSG (Island/Weak Grid)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mode Decision Logic                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │ Grid Detect │────►│ Mode Select │────►│ Controller  │       │
│  │ (PLL Status)│     │ (PQ / VSG)  │     │   Switch    │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
└─────────────────────────────────────────────────────────────────┘

PQ Mode (Grid-Connected):
  - Active power P ref → Current loop Id ref
  - Reactive power Q ref → Current loop Iq ref
  - PLL tracks grid voltage angle θ
  - Current loop controls d-axis and q-axis currents

VSG Mode (Island/Weak Grid):
  - Swing equation: J(dω/dt) = (Pm - Pe - DΔω) / ω
  - Virtual inertia J, damping coefficient D
  - Voltage amplitude regulation via reactive power droop
  - Frequency regulation via active power droop
```

## PLL Architecture Options

| Type | Lock Time | THD Rejection | Complexity | Use Case |
|------|-----------|---------------|------------|----------|
| SRF-PLL | 20-50ms | Medium | Low | Standard grid |
| DDSRF-PLL | 10-30ms | High | Medium | Unbalanced grid |
| DSOGI-PLL | 15-40ms | High | Medium | Distorted grid |
| FLL | 5-15ms | Medium | Low | Fast tracking |
| ADALINE-PLL | 10-25ms | Very High | High | Harsh conditions |

### SRF-PLL Implementation

```
Vα ──┐
     ├──► Park Transform ──► Vd ──┐
Vβ ──┘      (θ)            Vq ──┼──► PI Controller ──► Δω ──► ∫ ──► θ
                                 │                              │
                                 └──────────────────────────────┘
                                     (feedback loop)

Bandwidth: 10-50 Hz (configurable)
Damping ratio: 0.707 (critical damping)
```

## Current Loop Topology

### Cascaded PI Control (dq frame)

```
Id_ref ──►[PI]──► Vd_ff ──►[+]──► Decoupling ──► PWM ──► Inverter
              ↑              │        │
              │              │        ├── LωIq (cross-coupling)
              │              │        └── Vd_ff (feedforward)
              │              │
              └──────────────┘
                   Id_feedback

Iq_ref ──►[PI]──► Vq_ff ──►[+]──► Decoupling ──► PWM ──► Inverter
              ↑              │        │
              │              │        ├── LωId (cross-coupling)
              │              │        └── Vq_ff (feedforward)
              │              │
              └──────────────┘
                   Iq_feedback
```

### Current Loop Bandwidth

| Parameter | Value | Notes |
|-----------|-------|-------|
| Current loop bandwidth | 1-5 kHz | 1/10 to 1/5 of switching frequency |
| Voltage loop bandwidth | 100-500 Hz | 1/10 of current loop |
| PLL bandwidth | 10-50 Hz | 1/10 of voltage loop |
| Sampling rate | Equal to switching frequency | Single or double update |

## MPPT Algorithms

| Algorithm | Speed | Complexity | Oscillation | Use Case |
|-----------|-------|------------|-------------|----------|
| P&O | Medium | Low | Yes | Standard PV |
| INC | Medium | Low | Low | Standard PV |
| FLC | Fast | High | Low | Partial shading |
| PSO | Fast | High | None | Multi-peak |
| Beta method | Fast | Medium | Low | Wide range |

### P&O Flowchart

```
Start
  │
  ▼
Measure V(k), I(k)
  │
  ▼
Calculate P(k) = V(k) × I(k)
  │
  ▼
ΔP = P(k) - P(k-1)
ΔV = V(k) - V(k-1)
  │
  ▼
┌─────────────┐
│ ΔP/ΔV > 0? │
└──────┬──────┘
       │
   ┌───┴───┐
   Yes     No
   │       │
   ▼       ▼
┌─────┐  ┌─────┐
│ΔV>0?│  │ΔV>0?│
└──┬──┘  └──┬──┘
   │        │
┌──┴──┐  ┌──┴──┐
Yes No  Yes  No
│   │   │    │
▼   ▼   ▼    ▼
V+  V-  V-   V+
│   │   │    │
└───┴───┴────┘
       │
       ▼
    Update Vref
       │
       ▼
     Return
```

## Switching Frequency & Dead Time

### Switching Frequency Selection

| Application | fsw Range | Trade-off |
|-------------|-----------|-----------|
| PV string inverter | 16-32 kHz | Efficiency vs THD |
| Central inverter | 2-8 kHz | Loss vs filter size |
| UPS | 10-20 kHz | THD vs switching loss |
| Motor drive | 4-16 kHz | Torque ripple vs loss |

### Dead Time Compensation

```
Vref ──►[Dead Time Comp]──► PWM Generator ──► Gate Driver
              │
              ├── Current polarity detection
              ├── Voltage error estimation
              └── Feedforward correction

Dead time range: 0.5-5 µs (typically 1-3 µs)
Compensation methods:
  - Current sign-based (simple, effective)
  - Observer-based (accurate, complex)
  - Learning-based (adaptive)
```

## Control Loop Timing

```
Switching Period (1/fsw)
  │
  ├── ADC Sampling (center-aligned)
  │     └── < 1 µs acquisition time
  │
  ├── Control Calculation
  │     ├── Clarke/Park transform: < 2 µs
  │     ├── Current loop PI: < 3 µs
  │     ├── Voltage loop PI: < 3 µs
  │     ├── Decoupling: < 1 µs
  │     └── MPPT (if applicable): < 5 µs
  │
  ├── PWM Update
  │     └── < 1 µs
  │
  └── Total: < 15 µs (must be < Tsw/2)
```

## Protection Parameters

| Protection | Threshold | Response Time | Action |
|------------|-----------|---------------|--------|
| Overcurrent (HW) | 1.5 × Inom | < 1 µs | PWM shutdown |
| Overcurrent (SW) | 1.2 × Inom | < 100 µs | Current limit |
| Overvoltage | 1.1 × Vnom | < 1 ms | Power derating |
| Undervoltage | 0.85 × Vnom | < 10 ms | LVRT operation |
| Overfrequency | 50.5 Hz | < 100 ms | Power ramp down |
| Underfrequency | 49.5 Hz | < 100 ms | Power ramp up |
| DC injection | < 0.5% Inom | Continuous | DC offset correction |
| THD | < 5% | Continuous | Harmonic compensation |

## State Machine: Operating Modes

```
States:
  INIT          → Parameter load, self-test
  STANDBY       → Waiting for start command
  PRECHARGE     → DC bus charging
  GRID_SYNC     → PLL lock, voltage matching
  PQ_RUNNING    → Grid-connected power injection
  VSG_RUNNING   → Virtual synchronous generator mode
  FAULT         → Fault detected, safe shutdown
  RECOVERY      → Fault cleared, restart sequence

Transitions:
  INIT → STANDBY: Self-test pass
  STANDBY → PRECHARGE: Start command + conditions met
  PRECHARGE → GRID_SYNC: DC bus voltage stable
  GRID_SYNC → PQ_RUNNING: PLL locked + grid normal
  GRID_SYNC → VSG_RUNNING: Island detected / weak grid
  PQ_RUNNING → VSG_RUNNING: Grid abnormal / islanding
  VSG_RUNNING → PQ_RUNNING: Grid restored + sync
  * → FAULT: Protection triggered
  FAULT → RECOVERY: Fault cleared + cooldown
  RECOVERY → STANDBY: Restart conditions met
```
