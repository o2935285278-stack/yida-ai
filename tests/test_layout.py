from yida_ai.ui.layout import dpi_scaled_preferred_size, responsive_window_metrics


def _main_metrics(width: int, height: int):
    return responsive_window_metrics(
        width,
        height,
        preferred_width=1240,
        preferred_height=900,
        normal_min_width=900,
        normal_min_height=620,
    )


def test_main_window_fits_1366_by_768_and_full_hd():
    compact = _main_metrics(1366, 768)
    full_hd = _main_metrics(1920, 1080)
    assert (compact.width, compact.height) == (1240, 688)
    assert compact.min_width <= compact.width
    assert compact.min_height <= compact.height
    assert (full_hd.width, full_hd.height) == (1240, 900)


def test_window_minimum_does_not_exceed_scaled_logical_desktop():
    # Approximate the logical workspace exposed by a 1366×768 display at 150%.
    scaled = _main_metrics(911, 512)
    assert scaled.width <= 911
    assert scaled.height <= 512
    assert scaled.min_width <= scaled.width
    assert scaled.min_height <= scaled.height


def test_preferred_window_scales_from_100_through_200_percent():
    assert dpi_scaled_preferred_size(96 / 72, 1240, 900) == (1240, 900)
    assert dpi_scaled_preferred_size((96 / 72) * 1.25, 1240, 900) == (1550, 1125)
    assert dpi_scaled_preferred_size((96 / 72) * 1.5, 1240, 900) == (1860, 1350)
    assert dpi_scaled_preferred_size((96 / 72) * 2.0, 1240, 900) == (2480, 1800)
