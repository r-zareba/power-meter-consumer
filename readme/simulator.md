# STM32 Simulator

Simulates STM32 UART data transmission for testing without real hardware.

## Quick Start

**Terminal 1 - Create virtual serial ports:**
```bash
./setup_virtual_ports.sh
```
Note the port numbers (e.g., `/dev/pts/29` and `/dev/pts/30`)

**Terminal 2 - Run simulator:**
```bash
uv run python src/run_stm32_simulator.py --port /dev/pts/29
```

**Terminal 3 - Run receiver:**
```bash
uv run python src/main.py --port /dev/pts/30
```

## Configuration

Edit `src/simulator/config.py` to configure waveforms:
```python
# DC bias for both channels (VCC/2)
DC_BIAS = 1.65  # V

# Voltage channel
VOLTAGE = {
    "rms": 1.0,           # V RMS at ADC input
    "harmonic_3": 0.0,    # 3rd harmonic (0.0-1.0)
    "harmonic_5": 0.0,    # 5th harmonic
    # ... up to harmonic_17
}

# Current channel
CURRENT = {
    "rms": 0.37,          # V RMS at ADC input
    "phase_shift": 0.0,   # Degrees (negative=lag, positive=lead)
    "harmonic_3": 0.0,    # 3rd harmonic (0.0-1.0)
    "harmonic_5": 0.0,    # 5th harmonic
    # ... up to harmonic_17
}
```

ADC configuration (bits, VREF, sampling rate) is in `src/config.py`.

## Usage

```bash
uv run python src/run_stm32_simulator.py --port <port> [--baud <rate>]
```

- `--port` (required): Serial port (e.g., `/dev/pts/3`)
- `--baud`: Baud rate (default: 921600)

**Stop with Ctrl+C**

## Presets

Edit `src/simulator/config.py` and uncomment presets:

**Resistive Load (PF=1.0):**
```python
VOLTAGE["rms"] = 1.0
CURRENT["rms"] = 0.37
CURRENT["phase_shift"] = 0.0
```

**Inductive Load (PF=0.87):**
```python
CURRENT["phase_shift"] = -30.0  # Current lags
```

**Non-linear Load (harmonics):**
```python
CURRENT["harmonic_3"] = 0.20  # 20% 3rd harmonic
CURRENT["harmonic_5"] = 0.10  # 10% 5th harmonic
```

## Harmonics

Values are fractions of fundamental (0.0-1.0):
- `0.0` = clean sine wave
- `0.1` = 10% of fundamental
- `0.2` = 20% of fundamental (significant distortion)
