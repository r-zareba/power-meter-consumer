"""Utility functions for ADC data processing"""


def calculate_stats(samples):
    """Calculate basic statistics for a sample array"""
    n = len(samples)
    mean_val = sum(samples) / n
    min_val = min(samples)
    max_val = max(samples)
    variance = sum((x - mean_val) ** 2 for x in samples) / n
    std_val = variance**0.5

    return {
        "mean": mean_val,
        "min": min_val,
        "max": max_val,
        "std": std_val,
    }
