# Global sensor configuration shared across simulator and receiver
# Adjust these values based on actual hardware and calibration

ADC_CONFIG = {
    "bits": 16,  # ADC resolution (16-bit for H755ZI-Q)
    "max_value": 65535,  # Maximum ADC value (2^16 - 1)
    "vref": 3.3,  # ADC reference voltage (V)
    "sampling_freq": 10000,  # Sampling frequency (Hz)
    "samples_per_packet": 1000,  # Samples per channel per packet
}

# Voltage sensor configuration (ZMPT101B default)
VOLTAGE_SENSOR = {
    "name": "ZMPT101B",
    "scaling_factor": 1.0 / 230.0,  # V_sensor / V_mains (1.0V output for 230V input)
    "dc_bias": 1.65,  # V (sensor output DC bias - typically VCC/2)
    "max_value": 250.0,  # V AC (maximum safe input voltage)
}

# Current sensor configuration (ACS712-05B default)
CURRENT_SENSOR = {
    "name": "ACS712-05B",
    "sensitivity": 0.185,  # V/A (185 mV per Ampere)
    "dc_bias": 1.65,  # V (sensor output DC bias - typically VCC/2)
    "max_value": 5.0,  # A (±5A range)
}
