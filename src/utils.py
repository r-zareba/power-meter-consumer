"""Utility functions for performance monitoring and instrumentation"""

import os
import time
from functools import wraps

import numpy as np

PRINT_STATS = os.getenv("PRINT_STATS", "").lower() in ("1", "true", "yes")

# Storage for timing data (always defined, only populated when stats enabled)
_time_stats = {}

# Define decorator based on environment - zero overhead in production
if PRINT_STATS:

    def measure_time(func):
        """Decorator to measure function execution time"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000

            operation = func.__name__
            if operation not in _time_stats:
                _time_stats[operation] = []
            _time_stats[operation].append(duration_ms)

            return result

        return wrapper
else:
    # Production mode - absolute zero overhead
    def measure_time(func):
        return func  # Direct passthrough, no wrapper


def print_performance_stats():
    """Print detailed timing statistics"""
    if not _time_stats:
        return

    # Define display order
    ordered_operations = [
        "read_packet_bytes",
        "parse_packet",
        "process_analysis_window",
    ]

    print("\n" + "=" * 80)
    print("Performance Statistics (milliseconds):")
    print("=" * 80)
    print(
        f"{'Operation':<30} {'Mean':>8} {'Min':>8} {'Max':>8} {'P95':>8} {'Count':>8}"
    )
    print("-" * 80)

    total_mean = 0.0
    total_count = 0

    # Print in specified order
    for operation in ordered_operations:
        if operation in _time_stats:
            timings = _time_stats[operation]
            arr = np.array(timings)
            mean_val = np.mean(arr)
            total_mean += mean_val
            total_count = len(arr)  # Assuming all operations have same count
            
            print(
                f"{operation:<30} "
                f"{mean_val:8.2f} "
                f"{np.min(arr):8.2f} "
                f"{np.max(arr):8.2f} "
                f"{np.percentile(arr, 95):8.2f} "
                f"{len(arr):8d}"
            )

    # Print remaining operations (if any)
    for operation, timings in sorted(_time_stats.items()):
        if operation not in ordered_operations:
            arr = np.array(timings)
            print(
                f"{operation:<30} "
                f"{np.mean(arr):8.2f} "
                f"{np.min(arr):8.2f} "
                f"{np.max(arr):8.2f} "
                f"{np.percentile(arr, 95):8.2f} "
                f"{len(arr):8d}"
            )

    # Print total
    if total_mean > 0:
        print("-" * 80)
        print(
            f"{'TOTAL (per cycle)':<30} "
            f"{total_mean:8.2f} "
            f"{'':>8} "
            f"{'':>8} "
            f"{'':>8} "
            f"{total_count:8d}"
        )
    
    print("=" * 80)
