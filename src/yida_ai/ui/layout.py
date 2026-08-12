from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WindowMetrics:
    width: int
    height: int
    min_width: int
    min_height: int


def dpi_scaled_preferred_size(
    tk_scaling: float,
    width: int,
    height: int,
    *,
    baseline: float = 96 / 72,
) -> tuple[int, int]:
    """Scale the preferred physical window for 125–200% Tk text scaling."""
    factor = max(1.0, min(2.0, tk_scaling / baseline))
    return round(width * factor), round(height * factor)


def responsive_window_metrics(
    screen_width: int,
    screen_height: int,
    *,
    preferred_width: int,
    preferred_height: int,
    normal_min_width: int,
    normal_min_height: int,
    margin: int = 80,
) -> WindowMetrics:
    """Keep the requested and minimum sizes inside the current logical desktop."""
    available_width = max(640, screen_width - margin)
    available_height = max(420, screen_height - margin)
    width = min(preferred_width, available_width)
    height = min(preferred_height, available_height)
    return WindowMetrics(
        width=width,
        height=height,
        min_width=min(normal_min_width, width),
        min_height=min(normal_min_height, height),
    )
