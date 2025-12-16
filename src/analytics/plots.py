"""
Plotting functions for power analysis visualization.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_power_analysis(
    time: np.ndarray,
    voltage: np.ndarray,
    current: np.ndarray,
    power: np.ndarray,
    p_avg: float,
    title: str = "Power Analysis",
):
    """
    Plot voltage, current, and instantaneous power.

    Args:
        time: Time array (s)
        voltage: Voltage samples (V)
        current: Current samples (A)
        power: Instantaneous power p(t) (W)
        p_avg: Average active power (W)
        title: Plot title
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=("Voltage", "Current", "Instantaneous Power p(t)"),
    )

    # Voltage
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=voltage,
            mode="lines",
            name="Voltage",
            line=dict(color="blue"),
        ),
        row=1,
        col=1,
    )

    # Current
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=current,
            mode="lines",
            name="Current",
            line=dict(color="red"),
        ),
        row=2,
        col=1,
    )

    # Instantaneous Power
    fig.add_trace(
        go.Scatter(
            x=time * 1000, y=power, mode="lines", name="p(t)", line=dict(color="green")
        ),
        row=3,
        col=1,
    )

    # Average Power line
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=[p_avg] * len(time),
            mode="lines",
            name=f"P_avg = {p_avg:.2f}W",
            line=dict(color="orange", dash="dash"),
        ),
        row=3,
        col=1,
    )

    fig.update_xaxes(title_text="Time (ms)", row=3, col=1)
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=2, col=1)
    fig.update_yaxes(title_text="Power (W)", row=3, col=1)

    fig.update_layout(title_text=title, height=1000, showlegend=True)

    fig.show()


def plot_three_phase_waveforms(
    time: np.ndarray,
    v1_t: np.ndarray,
    v2_t: np.ndarray,
    v3_t: np.ndarray,
    i1_t: np.ndarray,
    i2_t: np.ndarray,
    i3_t: np.ndarray,
    p1_t: np.ndarray,
    p2_t: np.ndarray,
    p3_t: np.ndarray,
    p_total: float,
    title: str = "Three-Phase Power Analysis",
):
    """
    Plot three-phase voltages, currents, and instantaneous power.

    Args:
        time: Time array (s)
        v1_t, v2_t, v3_t: Voltage samples for phases 1, 2, 3 (V)
        i1_t, i2_t, i3_t: Current samples for phases 1, 2, 3 (A)
        p1_t, p2_t, p3_t: Instantaneous power per phase (W)
        p_total: Total average active power (W)
        title: Plot title
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            "Three-Phase Voltages",
            "Three-Phase Currents",
            "Instantaneous Power per Phase",
        ),
    )

    # Voltages
    phase_colors = ["blue", "green", "red"]
    for i, (v, name, color) in enumerate(
        zip([v1_t, v2_t, v3_t], ["V1", "V2", "V3"], phase_colors)
    ):
        fig.add_trace(
            go.Scatter(
                x=time * 1000, y=v, mode="lines", name=name, line=dict(color=color)
            ),
            row=1,
            col=1,
        )

    # Currents (same colors as voltages for each phase)
    for i, (current, name, color) in enumerate(
        zip([i1_t, i2_t, i3_t], ["I1", "I2", "I3"], phase_colors)
    ):
        fig.add_trace(
            go.Scatter(
                x=time * 1000,
                y=current,
                mode="lines",
                name=name,
                line=dict(color=color),
            ),
            row=2,
            col=1,
        )

    # Instantaneous Power
    colors_p = ["cyan", "lime", "orange"]
    for i, (power, name, color) in enumerate(
        zip([p1_t, p2_t, p3_t], ["P1(t)", "P2(t)", "P3(t)"], colors_p)
    ):
        fig.add_trace(
            go.Scatter(
                x=time * 1000, y=power, mode="lines", name=name, line=dict(color=color)
            ),
            row=3,
            col=1,
        )

    # Total average power line
    fig.add_trace(
        go.Scatter(
            x=time * 1000,
            y=[p_total] * len(time),
            mode="lines",
            name=f"P_total_avg = {p_total:.2f}W",
            line=dict(color="black", dash="dash", width=2),
        ),
        row=3,
        col=1,
    )

    fig.update_xaxes(title_text="Time (ms)", row=3, col=1)
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=2, col=1)
    fig.update_yaxes(title_text="Power (W)", row=3, col=1)

    fig.update_layout(title_text=title, height=1000, showlegend=True)

    fig.show()
