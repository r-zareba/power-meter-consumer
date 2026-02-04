"""
STM32 Power Meter Simulator

Simulates the STM32 UART data transmission with dual-channel ADC data.
Generates synthetic voltage and current waveforms using the exact same
packet protocol as the real STM32 H755ZI-Q board.
"""

from .simulator import STM32Simulator

__all__ = ["STM32Simulator"]
