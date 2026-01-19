# STM32 Simulator

Simulates STM32 UART data transmission for testing the receiver application without real hardware.

## Purpose

- Develop and test receiver code without STM32 or sensors
- Generate known test signals with ground truth for validation
- Test different power scenarios (resistive, inductive, harmonics)
- Faster iteration during development

## Configuration

### Sensor Configuration (Global)

Sensor parameters are defined in `src/config.py` and shared across the entire project (simulator, receiver, analytics):

```python
# src/config.py

# Voltage sensor (ZMPT101B default)
VOLTAGE_SENSOR = {
    "name": "ZMPT101B",
    "scaling_factor": 1.0 / 230.0,  # V_sensor/V_mains
    "dc_bias": 1.65,                # V (VCC/2)
    "max_input": 250.0,             # V AC
}

# Current sensor (ACS712-05B default)
CURRENT_SENSOR = {
    "name": "ACS712-05B",
    "sensitivity": 0.185,  # V/A
    "dc_bias": 1.65,       # V (VCC/2)
    "max_current": 5.0,    # ±A
}
```

**To change sensor hardware globally:** Edit `src/config.py` and both simulator and receiver will use the new settings.

### Waveform Configuration (Simulator Only)

Waveform parameters are in `src/scripts/simulator_config.py`:
# Voltage channel (ADC1, PA0)
VOLTAGE = {
    "rms": 1.0,           # V RMS at sensor output (~230V mains)
    "harmonic_3": 0.0,    # 3rd harmonic (0.0-1.0 fraction)
    "harmonic_5": 0.0,    # 5th harmonic
    # ... up to harmonic_17
}

# Current channel (ADC2, PA1)
CURRENT = {
    "rms": 0.37,          # V RMS at sensor output (~2A at 0.185V/A)
    "phase_shift": 0.0,   # Degrees (negative=lag, positive=lead)
    "harmonic_3": 0.0,    # 3rd harmonic (0.0-1.0 fraction)
    "harmonic_5": 0.0,    # 5th harmonic
    # ... up to harmonic_17
}
```

## Quick Start

**Terminal 1 - Create virtual serial ports:**
```bash
./scripts/setup_virtual_ports.sh
```

Note the port numbers from output (e.g., `/dev/pts/29` and `/dev/pts/30`)

**Terminal 2 - Run simulator:**
```bash
python src/scripts/run_stm32_simulator.py --port /dev/pts/29
```

**Terminal 3 - Run receiver:**
```bash
python src/main.py --port /dev/pts/30 --baud 921600
```

## Usage

### Command Line Arguments

```bash
python src/scripts/run_stm32_simulator.py --port <port> [--baud <rate>] [--duration <seconds>]
```

- `--port` (required): Serial port path (e.g., `/dev/pts/3`, `COM3`)
- `--baud`: Baud rate (default: 921600)
- `--duration`: Duration in seconds (default: infinite, stop with Ctrl+C)

## Test Scenarios

Edit `src/scripts/simulator_config.py` to create different load scenarios. Several presets are provided:

### Load Type Scenarios

#### Resistive Load (PF=1.0, in phase)
```python
VOLTAGE["rms"] = 1.0
CURRENT["rms"] = 0.37
CURRENT["phase_shift"] = 0.0
```
Expected: 460W, PF=1.0

#### Inductive Load (PF=0.87, lagging)
```python
CURRENT["phase_shift"] = -30.0  # Current lags by 30°
```
Expected: 400W, PF=0.87 (typical motor)

#### Non-linear Load with Harmonics
```python
CURRENT["harmonic_3"] = 0.20  # 20% 3rd harmonic
CURRENT["harmonic_5"] = 0.10  # 10% 5th harmonic
```
Expected: THD ~22% (switch-mode PSU)

#### Low Power Load
```python
CURRENT["rms"] = 0.0185  # 0.1A × 0.185 V/A
```
Expected: 23W (tests resolution)

### Custom Sensor Scenarios

**Note:** For permanent sensor changes that apply to both simulator and receiver, edit `src/config.py` instead of these presets.

#### Testing ACS712-20A (Temporarily in Simulator)
```python
CURRENT_SENSOR["name"] = "ACS712-20A"
CURRENT_SENSOR["sensitivity"] = 0.100  # 100 mV/A
CURRENT_SENSOR["max_current"] = 20.0
CURRENT["rms"] = 0.200  # 2A at 0.100 V/A
```

#### ACS712-30A (Even Higher Range)
```python
CURRENT_SENSOR["name"] = "ACS712-30A"
CURRENT_SENSOR["sensitivity"] = 0.066  # 66 mV/A
CURRENT_SENSOR["max_current"] = 30.0
CURRENT["rms"] = 0.132  # 2A at 0.066 V/A
```

#### Custom Voltage Sensor
```python
VOLTAGE_SENSOR["scaling_factor"] = 0.01  # 2.3V for 230V input
VOLTAGE["rms"] = 2.3
```

## Sensor Parameters

**ZMPT101B Voltage Sensor (default):**
- Scaling: 1.0V output for 230V AC input (1:230 ratio)
- DC bias: 1.65V (centered for 0-3.3V ADC)
- Max input: 250V AC

**ACS712-05B Current Sensor (default):**
- Sensitivity: 0.185 V/A (185 mV per Ampere)
- DC bias: 1.65V (centered for bidirectional measurement)
- Range: ±5A

**Other ACS712 Variants:**
- ACS712-20A: 0.100 V/A, ±20A range
- ACS712-30A: 0.066 V/A, ±30A range

## Harmonic Configuration

Harmonic amplitudes are fractions of the fundamental (0.0-1.0):
- `0.0` = No harmonic (clean sine wave)
- `0.1` = 10% of fundamental
- `1.0` = 100% of fundamental (very distorted)

**Typical values:**
- Clean load: All harmonics = 0
- Mild distortion (modern PSU): 3rd=0.05, 5th=0.03
- Severe distortion (old rectifier): 3rd=0.40, 5th=0.25

## Examples

**Run indefinitely (stop with Ctrl+C):**
```bash
python src/scripts/run_stm32_simulator.py --port /dev/pts/29
```

**Run for 60 seconds:**
```bash
python src/scripts/run_stm32_simulator.py --port /dev/pts/29 --duration 60
```

**Custom baud rate:**
```bash
python src/scripts/run_stm32_simulator.py --port /dev/pts/29 --baud 115200
```

## Data Flow

- Packets sent every 100ms (10 packets/second)
- Each packet: 1000 voltage + 1000 current samples
- Exact same protocol and timing as real STM32
- Analysis windows: 200ms (2000 samples, IEC 61000-4-7 compliant)

## Troubleshooting

**No data received:**
- Check port numbers match socat output (they change each restart)
- Try swapping ports between simulator and receiver
- Verify socat is still running in Terminal 1

**Port already in use:**
- Close other serial connections
- Restart socat (Terminal 1)
