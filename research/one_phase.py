import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# System parameters matching ADCReceiver
SAMPLING_FREQ = 10000  # Hz
NUM_SAMPLES = 1000
MAINS_FREQ = 50  # Hz


def generate_sine(
    amplitude: float,
    frequency: float,
    phase: float,
    sampling_freq: float,
    num_samples: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate a sinusoidal waveform.
    
    Args:
        amplitude: Peak amplitude
        frequency: Frequency (Hz)
        phase: Phase offset (radians)
        sampling_freq: Sampling frequency (Hz)
        num_samples: Number of samples to generate
    
    Returns:
        Tuple of (time_array, signal_array)
    """
    t = np.arange(num_samples) / sampling_freq
    signal = amplitude * np.sin(2 * np.pi * frequency * t + phase)
    return t, signal


def plot_waveforms(
    time: np.ndarray,
    voltage: np.ndarray,
    current: np.ndarray,
    title: str = "Voltage and Current Waveforms",
):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Voltage", "Current")
    )
    
    fig.add_trace(
        go.Scatter(x=time * 1000, y=voltage, mode='lines', name='Voltage', line=dict(color='blue')),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=time * 1000, y=current, mode='lines', name='Current', line=dict(color='red')),
        row=2, col=1
    )
    
    fig.update_xaxes(title_text="Time (ms)", row=2, col=1)
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=2, col=1)
    
    fig.update_layout(
        title_text=title,
        height=800,
        showlegend=False
    )
    
    fig.show()


if __name__ == "__main__":
    # Example usage
    t_v, voltage = generate_sine(
        amplitude=325,
        frequency=MAINS_FREQ,
        phase=0,
        sampling_freq=SAMPLING_FREQ,
        num_samples=NUM_SAMPLES,
    )  # 230V RMS → ~325V peak
    t_c, current = generate_sine(
        amplitude=14.14,
        frequency=MAINS_FREQ,
        phase=0,
        sampling_freq=SAMPLING_FREQ,
        num_samples=NUM_SAMPLES,
    )  # 10A RMS → ~14.14A peak
    
    plot_waveforms(t_v, voltage, current)
