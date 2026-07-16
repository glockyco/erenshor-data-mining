#!/usr/bin/env python3
"""Render approved wiki plots for Chant Control, Resonance, and physical critical mechanics.

Usage:
    uv run python src/tools/render_spell_scaling_plots.py
    uv run python src/tools/render_spell_scaling_plots.py --output-dir output/plots
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import cast, final

from PIL import Image, ImageDraw, ImageFont

from erenshor.tools.critical_strike_model import (
    CRIPPLING_BLOW_CRITICAL_MULTIPLIER,
    CRIPPLING_BLOW_PROC_CHANCE,
    MAX_PLAYER_LEVEL,
    RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER,
    STANDARD_CRITICAL_MULTIPLIER,
    CriticalProfile,
    crippling_blow_expected_critical_multiplier,
    critical_hit_chance,
    expected_damage_multiplier,
    verify_critical_model,
)

BUILD_LABEL = "build 24184286"
IMAGE_WIDTH = 1200
CRITICAL_DEX_MAX = 1_000
CRITICAL_DEX_TICK = 200
CRITICAL_CHANCE_MAX = 100
CRITICAL_CHANCE_TICK = 20

NORMAL_CAST_END = 1.0
OVERCHANT_FRACTION = 0.4
OVERCHANT_COEFFICIENT = 0.315
MAX_CAST_PROGRESS = NORMAL_CAST_END + OVERCHANT_FRACTION

ORDINARY_RESONANCE_SCALE = 0.30
CRITICAL_BLAST_MIN = 1.10
CRITICAL_BLAST_MAX = 1.30
ROARING_ECHO_THRESHOLD = 100
ROARING_ECHO_PROC_CHANCE_PER_RANK = 0.30
REPORTED_RESONANCE = 122

REPORTED_ORIGINAL = 33_335
REPORTED_ORIGINAL_CRITICAL = 39_805
REPORTED_ORDINARY_RESONANCE = 15_548
REPORTED_ORDINARY_CRITICAL = 17_669
REPORTED_ROARING_ECHO = 38_927
REPORTED_ROARING_ECHO_CRITICAL = 45_178
REPORTED_MAX_CHANT = 52_395

WHITE = "#ffffff"
INK = "#222222"
MUTED = "#444444"
GRID = "#dddddd"
BLUE = "#3977d4"
BLUE_DARK = "#244f91"
BLUE_SOFT = "#e4ecf8"
GREEN = "#27885a"
GREEN_DARK = "#17633f"
GREEN_SOFT = "#dff1e6"
AMBER = "#d17825"
AMBER_DARK = "#8a5315"
AMBER_SOFT = "#fff4e5"
PURPLE = "#7b5aa6"
PURPLE_DARK = "#67478f"
CALLOUT = "#f3f5f8"


@final
class Fonts:
    """Load the fonts used by the originally approved plot designs."""

    REGULAR_CANDIDATES = (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    BOLD_CANDIDATES = (
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    )

    def __init__(self) -> None:
        self._cache: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def get(self, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = (size, bold)
        if key not in self._cache:
            candidates = self.BOLD_CANDIDATES if bold else self.REGULAR_CANDIDATES
            for path in candidates:
                if path.is_file():
                    self._cache[key] = ImageFont.truetype(str(path), size=size)
                    break
            else:
                self._cache[key] = ImageFont.load_default(size=size)
        return self._cache[key]


FONTS = Fonts()


@dataclass(frozen=True)
class PlotArea:
    left: float
    top: float
    right: float
    bottom: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def x(self, value: float) -> float:
        ratio = (value - self.x_min) / (self.x_max - self.x_min)
        return self.left + ratio * (self.right - self.left)

    def y(self, value: float) -> float:
        ratio = (value - self.y_min) / (self.y_max - self.y_min)
        return self.bottom - ratio * (self.bottom - self.top)


@dataclass(frozen=True)
class CriticalSeries:
    """One exact physical-critical curve and its visual encoding."""

    values: tuple[float, ...]
    color: str
    dash_pattern: tuple[int, int] | None


@dataclass(frozen=True)
class CriticalClassStyle:
    """Visual encoding and model branch for one displayed class group."""

    label: str
    profile: CriticalProfile
    color: str
    dash_pattern: tuple[int, int] | None
    marker_shape: str


CRITICAL_CLASS_STYLES = (
    CriticalClassStyle(
        "Arcanist · Druid · Paladin · Reaver",
        CriticalProfile.ORDINARY,
        BLUE,
        None,
        "circle",
    ),
    CriticalClassStyle(
        "Stormcaller",
        CriticalProfile.STORMCALLER,
        GREEN,
        (18, 10),
        "square",
    ),
    CriticalClassStyle(
        "Windblade",
        CriticalProfile.WINDBLADE,
        AMBER,
        (7, 7),
        "diamond",
    ),
)


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    value: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    draw.text(xy, value, font=font, fill=fill)  # pyright: ignore[reportUnknownMemberType]


def text_bbox(
    draw: ImageDraw.ImageDraw,
    value: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), value, font=font)


def draw_vertical_label(
    image: Image.Image,
    value: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    left: int,
    center_y: float,
) -> None:
    probe = ImageDraw.Draw(image)
    bounds = text_bbox(probe, value, font)
    width = bounds[2] - bounds[0] + 16
    height = bounds[3] - bounds[1] + 12
    label = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    label_draw = ImageDraw.Draw(label)
    draw_text(label_draw, (8, 3 - bounds[1]), value, font=font, fill=INK)
    rotated = label.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    image.paste(rotated, (left, int(center_y - rotated.height / 2)), rotated)


def chant_multiplier(progress: float) -> float:
    """Return the Chant Control multiplier for normalized cast progress."""
    if not 0.0 <= progress <= MAX_CAST_PROGRESS:
        raise ValueError(f"Cast progress must be between 0 and {MAX_CAST_PROGRESS}")
    if progress <= NORMAL_CAST_END:
        return progress**2
    overchant_progress = (progress - NORMAL_CAST_END) / OVERCHANT_FRACTION
    return (NORMAL_CAST_END + OVERCHANT_COEFFICIENT * overchant_progress) ** 2


def ordinary_resonance_scale() -> float:
    return ORDINARY_RESONANCE_SCALE


def critical_range(scale: float) -> tuple[float, float]:
    return scale * CRITICAL_BLAST_MIN, scale * CRITICAL_BLAST_MAX


def roaring_echo_scale(resonance: float) -> float:
    if resonance <= ROARING_ECHO_THRESHOLD:
        raise ValueError("Roaring Echo scaling requires Resonance above 100")
    return resonance / 100.0


def derive_reported_components() -> tuple[float, float]:
    """Derive shared contribution A and scalable component B from the 122 RES samples."""
    echo_scale = roaring_echo_scale(REPORTED_RESONANCE)
    scalable = (REPORTED_ROARING_ECHO - REPORTED_ORIGINAL) / (echo_scale - 1.0)
    shared = REPORTED_ORIGINAL - scalable
    return shared, scalable


def predicted_damage(scale: float) -> float:
    shared, scalable = derive_reported_components()
    return shared + scale * scalable


def verify_values() -> None:
    """Fail before rendering if formulas or reported anchors drift."""
    verify_critical_model()
    anchors = {
        0.0: 0.0,
        0.5: 0.25,
        0.75: 0.5625,
        1.0: 1.0,
        1.2: 1.33980625,
        1.4: 1.729225,
    }
    for progress, expected in anchors.items():
        assert math.isclose(chant_multiplier(progress), expected, rel_tol=0.0, abs_tol=1e-9)

    assert math.isclose(ordinary_resonance_scale(), 0.30)
    assert all(
        math.isclose(actual, expected)
        for actual, expected in zip(critical_range(ORDINARY_RESONANCE_SCALE), (0.33, 0.39), strict=True)
    )
    assert math.isclose(roaring_echo_scale(REPORTED_RESONANCE), 1.22)
    assert all(
        math.isclose(actual, expected) for actual, expected in zip(critical_range(1.22), (1.342, 1.586), strict=True)
    )

    for normal, critical in (
        (REPORTED_ORIGINAL, REPORTED_ORIGINAL_CRITICAL),
        (REPORTED_ORDINARY_RESONANCE, REPORTED_ORDINARY_CRITICAL),
        (REPORTED_ROARING_ECHO, REPORTED_ROARING_ECHO_CRITICAL),
    ):
        assert CRITICAL_BLAST_MIN <= critical / normal <= CRITICAL_BLAST_MAX

    shared, scalable = derive_reported_components()
    assert round(shared) == 7_917
    assert round(scalable) == 25_418
    assert round(predicted_damage(ORDINARY_RESONANCE_SCALE)) == 15_542
    assert round(predicted_damage(1.22)) == REPORTED_ROARING_ECHO
    assert round(predicted_damage(chant_multiplier(MAX_CAST_PROGRESS))) == 51_871
    assert abs(REPORTED_ORDINARY_RESONANCE - round(predicted_damage(ORDINARY_RESONANCE_SCALE))) == 6
    assert _minimum_critical_dexterity(MAX_PLAYER_LEVEL, 5, CriticalProfile.ORDINARY, 0.955) == 5_280
    assert _minimum_critical_dexterity(MAX_PLAYER_LEVEL, 5, CriticalProfile.ORDINARY, 0.98) == 5_580
    assert _minimum_critical_dexterity(MAX_PLAYER_LEVEL, 20, CriticalProfile.STORMCALLER, 0.955) == 795
    assert _minimum_critical_dexterity(MAX_PLAYER_LEVEL, 20, CriticalProfile.STORMCALLER, 0.98) == 835
    assert _minimum_critical_dexterity(MAX_PLAYER_LEVEL, 40, CriticalProfile.WINDBLADE, 0.955) == 205
    assert _minimum_critical_dexterity(MAX_PLAYER_LEVEL, 40, CriticalProfile.WINDBLADE, 0.98) == 215


def draw_dashed_path(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    *,
    fill: str,
    width: int,
    dash_pattern: tuple[int, int] = (14, 8),
) -> None:
    """Draw a path with a stable dash phase across every segment."""
    if len(points) < 2:
        return
    dash_length, gap_length = dash_pattern
    if dash_length <= 0 or gap_length <= 0:
        raise ValueError("Dash and gap lengths must be positive")

    phase = 0.0
    draw_dash = True
    for start, end in pairwise(points):
        start_x, start_y = start
        end_x, end_y = end
        segment_length = math.hypot(end_x - start_x, end_y - start_y)
        if segment_length == 0:
            continue
        direction_x = (end_x - start_x) / segment_length
        direction_y = (end_y - start_y) / segment_length
        distance = 0.0
        while distance < segment_length:
            cycle_length = dash_length if draw_dash else gap_length
            remaining_cycle = cycle_length - phase
            step = min(remaining_cycle, segment_length - distance)
            if draw_dash:
                draw.line(
                    (
                        start_x + direction_x * distance,
                        start_y + direction_y * distance,
                        start_x + direction_x * (distance + step),
                        start_y + direction_y * (distance + step),
                    ),
                    fill=fill,
                    width=width,
                )
            distance += step
            phase += step
            if phase >= cycle_length:
                phase = 0.0
                draw_dash = not draw_dash


def draw_post_step_curve(
    draw: ImageDraw.ImageDraw,
    area: PlotArea,
    x_values: list[int],
    y_values: list[float],
    *,
    fill: str,
    width: int,
    dash_pattern: tuple[int, int] | None = None,
) -> None:
    """Draw exact post-step values, including every vertical transition."""
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise ValueError("A step curve needs matching x and y values")

    points = [(area.x(x_values[0]), area.y(y_values[0]))]
    current_value = y_values[0]
    for x_value, y_value in zip(x_values[1:], y_values[1:], strict=True):
        if y_value != current_value:
            points.append((area.x(x_value), area.y(current_value)))
            points.append((area.x(x_value), area.y(y_value)))
            current_value = y_value
    points.append((area.x(x_values[-1]), area.y(current_value)))

    if dash_pattern is None:
        draw.line(points, fill=fill, width=width)
    else:
        draw_dashed_path(draw, points, fill=fill, width=width, dash_pattern=dash_pattern)


def draw_marker(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    *,
    shape: str,
    fill: str,
    radius: float = 7,
) -> None:
    """Draw a redundant shape encoding for a plotted series."""
    center_x, center_y = center
    if shape == "circle":
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=fill,
            outline=WHITE,
            width=2,
        )
    elif shape == "square":
        draw.rectangle(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=fill,
            outline=WHITE,
            width=2,
        )
    elif shape == "diamond":
        draw.polygon(
            (
                (center_x, center_y - radius - 1),
                (center_x + radius + 1, center_y),
                (center_x, center_y + radius + 1),
                (center_x - radius - 1, center_y),
            ),
            fill=fill,
            outline=WHITE,
        )
    else:
        raise ValueError(f"Unknown marker shape: {shape}")


def draw_endpoint_label(
    draw: ImageDraw.ImageDraw,
    area: PlotArea,
    y_value: float,
    label: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    """Place a direct endpoint label in the reserved right-hand margin."""
    bounds = text_bbox(draw, label, font)
    label_height = bounds[3] - bounds[1]
    label_y = area.y(y_value) - label_height / 2
    draw_text(draw, (area.right + 18, label_y), label, font=font, fill=fill)


def draw_critical_panel_frame(
    draw: ImageDraw.ImageDraw,
    area: PlotArea,
    *,
    note: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    show_x_labels: bool,
) -> None:
    """Draw one panel in the shared physical-critical comparison frame."""
    for value in range(0, CRITICAL_DEX_MAX + 1, CRITICAL_DEX_TICK):
        x = area.x(value)
        draw.line((x, area.top, x, area.bottom), fill=GRID, width=1)
        if show_x_labels:
            label = f"{value:,}"
            bounds = text_bbox(draw, label, note)
            draw_text(
                draw,
                (x - (bounds[2] - bounds[0]) / 2, area.bottom + 8),
                label,
                font=note,
                fill=INK,
            )

    for value in (0, 50, 100):
        y = area.y(value)
        draw.line((area.left, y, area.right, y), fill=GRID, width=1)
        label = f"{value}%"
        bounds = text_bbox(draw, label, note)
        draw_text(
            draw,
            (area.left - 14 - (bounds[2] - bounds[0]), y - (bounds[3] - bounds[1]) / 2),
            label,
            font=note,
            fill=INK,
        )

    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)


def draw_critical_curves(
    draw: ImageDraw.ImageDraw,
    area: PlotArea,
    series: tuple[CriticalSeries, ...],
) -> None:
    """Draw exact post-step curves from declarative series data."""
    dex_values = list(range(CRITICAL_DEX_MAX + 1))
    for curve in series:
        if len(curve.values) != len(dex_values):
            raise ValueError("Critical series must contain one value for every displayed DEX")
        draw_post_step_curve(
            draw,
            area,
            dex_values,
            list(curve.values),
            fill=curve.color,
            width=4,
            dash_pattern=curve.dash_pattern,
        )


def draw_critical_legend(
    draw: ImageDraw.ImageDraw,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    left: float,
    y: float,
) -> None:
    """Draw one shared class legend for every proficiency panel."""
    cursor = left
    for style in CRITICAL_CLASS_STYLES:
        line_right = cursor + 42
        points = [(cursor, y), (line_right, y)]
        if style.dash_pattern is None:
            draw.line(points, fill=style.color, width=4)
        else:
            draw_dashed_path(
                draw,
                points,
                fill=style.color,
                width=4,
                dash_pattern=style.dash_pattern,
            )
        draw_marker(
            draw,
            ((cursor + line_right) / 2, y),
            shape=style.marker_shape,
            fill=style.color,
            radius=5,
        )
        label_x = line_right + 10
        bounds = text_bbox(draw, style.label, font)
        draw_text(
            draw,
            (label_x, y - (bounds[3] - bounds[1]) / 2 - bounds[1]),
            style.label,
            font=font,
            fill=INK,
        )
        cursor = label_x + bounds[2] - bounds[0] + 34


def render_chant_control(path: Path) -> None:
    """Render the originally approved detailed Chant Control plot."""
    image = Image.new("RGB", (IMAGE_WIDTH, 780), WHITE)
    draw = ImageDraw.Draw(image)
    font = FONTS.get(22)
    small = FONTS.get(18)
    title = FONTS.get(30, bold=True)
    area = PlotArea(155, 165, 1140, 675, 0, 145, 0, 195)

    draw.rectangle((area.x(100), area.top, area.x(140), area.bottom), fill=AMBER_SOFT)
    for value in range(0, 141, 20):
        x = area.x(value)
        draw.line((x, area.top, x, area.bottom), fill=GRID, width=1)
        label = str(value)
        box = text_bbox(draw, label, small)
        draw_text(draw, (x - (box[2] - box[0]) / 2, area.bottom + 10), label, font=small, fill="#333333")
    for value in range(0, 181, 20):
        y = area.y(value)
        draw.line((area.left, y, area.right, y), fill=GRID, width=1)
        label = str(value)
        box = text_bbox(draw, label, small)
        draw_text(
            draw,
            (area.left - 18 - (box[2] - box[0]), y - (box[3] - box[1]) / 2),
            label,
            font=small,
            fill="#333333",
        )

    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)

    linear_points = [(area.x(value), area.y(value)) for value in range(141)]
    for index in range(0, len(linear_points) - 1, 4):
        draw.line(
            (linear_points[index], linear_points[min(index + 2, len(linear_points) - 1)]),
            fill="#999999",
            width=2,
        )

    curve_points: list[tuple[float, float]] = []
    for index in range(701):
        progress = MAX_CAST_PROGRESS * index / 700
        curve_points.append((area.x(progress * 100), area.y(chant_multiplier(progress) * 100)))
    draw.line(curve_points, fill=BLUE, width=5, joint="curve")
    draw.line((area.x(100), area.top, area.x(100), area.bottom), fill=AMBER, width=3)
    anchors = ((50, 25.0), (75, 56.25), (100, 100.0), (120, 133.980625), (140, 172.9225))
    for progress, multiplier in anchors:
        x, y = area.x(progress), area.y(multiplier)
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=BLUE, outline=WHITE, width=2)
        draw_text(draw, (x + 10, y - 26), f"{multiplier:.1f}%", font=small, fill=BLUE_DARK)

    draw_text(draw, (area.left, 20), f"Chant Control scaling \N{EM DASH} {BUILD_LABEL}", font=title, fill="#111111")
    draw_text(
        draw,
        (area.left, 60),
        "p = elapsed time ÷ normal cast time     M = damage and base-cooldown multiplier",
        font=small,
        fill=MUTED,
    )
    draw.rectangle((450, 52, 1000, 85), fill=WHITE)
    draw_text(draw, (465, 60), "M = Chant Control multiplier", font=small, fill=MUTED)
    draw_text(draw, (area.left, 94), "Normal cast   0 ≤ p ≤ 1:   M = p²", font=font, fill=BLUE_DARK)
    draw_text(
        draw,
        (area.left + 430, 94),
        "Overchant   1 < p ≤ 1.4:   M = [1 + 0.315 \N{MULTIPLICATION SIGN} (p \N{MINUS SIGN} 1) ÷ 0.4]²",
        font=font,
        fill=AMBER_DARK,
    )

    legend_y = area.top + 8
    draw.rectangle((160, 167, 535, 202), fill=WHITE)
    draw.line((area.left + 15, legend_y + 10, area.left + 65, legend_y + 10), fill=BLUE, width=5)
    draw_text(draw, (area.left + 75, legend_y - 2), "Chant Control multiplier M", font=small, fill="#333333")
    draw.line((area.left + 390, legend_y + 10, area.left + 440, legend_y + 10), fill="#999999", width=2)
    draw_text(draw, (area.left + 450, legend_y - 2), "Linear reference", font=small, fill="#555555")

    x_label = "Release point (% of normal cast time)"
    box = text_bbox(draw, x_label, font)
    draw_text(
        draw,
        ((area.left + area.right - (box[2] - box[0])) / 2, 728),
        x_label,
        font=font,
        fill=INK,
    )
    draw_vertical_label(
        image,
        "Chant multiplier M (% of baseline)",
        font=font,
        left=28,
        center_y=(area.top + 620) / 2,
    )
    draw_text(draw, (area.x(112), area.y(18)), "40% overchant window", font=font, fill=AMBER_DARK)
    draw_text(draw, (area.x(101), area.y(188)), "OVERCHANT", font=small, fill="#9a5c13")
    image.save(path, format="PNG", compress_level=9)


def render_resonance(path: Path) -> None:
    """Render the originally approved detailed Resonance plot."""
    image = Image.new("RGB", (IMAGE_WIDTH, 820), WHITE)
    draw = ImageDraw.Draw(image)
    font = FONTS.get(22)
    small = FONTS.get(18)
    title = FONTS.get(30, bold=True)
    area = PlotArea(155, 215, 1140, 685, 0, 150, 0, 210)

    for value in range(0, 151, 25):
        x = area.x(value)
        draw.line((x, area.top, x, area.bottom), fill=GRID, width=1)
        label = str(value)
        box = text_bbox(draw, label, small)
        draw_text(draw, (x - (box[2] - box[0]) / 2, area.bottom + 10), label, font=small, fill="#333333")
    for value in range(0, 201, 25):
        y = area.y(value)
        draw.line((area.left, y, area.right, y), fill=GRID, width=1)
        label = str(value)
        box = text_bbox(draw, label, small)
        draw_text(
            draw,
            (area.left - 18 - (box[2] - box[0]), y - (box[3] - box[1]) / 2),
            label,
            font=small,
            fill="#333333",
        )
    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)

    for value in range(0, 150, 4):
        draw.line((area.x(value), area.y(100), area.x(min(value + 2, 150)), area.y(100)), fill="#999999", width=2)

    draw.rectangle((area.left, area.y(39), area.right, area.y(33)), fill=GREEN_SOFT)
    draw.line((area.left, area.y(30), area.right, area.y(30)), fill=GREEN, width=4)

    echo_values = [100 + 50 * index / 250 for index in range(251)]
    upper = [(area.x(value), area.y(1.3 * value)) for value in echo_values]
    lower = [(area.x(value), area.y(1.1 * value)) for value in reversed(echo_values)]
    draw.polygon(upper + lower, fill="#fde8c9")
    draw.line([(area.x(value), area.y(value)) for value in echo_values], fill=AMBER, width=4, joint="curve")

    x_resonance = area.x(REPORTED_RESONANCE)
    draw.line((x_resonance, area.top, x_resonance, area.bottom), fill=PURPLE, width=3)
    draw_text(draw, (x_resonance + 8, area.top + 8), "122 RES", font=small, fill=PURPLE_DARK)

    marker_values = (
        (30.0, GREEN),
        (33.0, GREEN),
        (39.0, GREEN),
        (122.0, AMBER),
        (134.2, AMBER),
        (158.6, AMBER),
    )
    for marker_value, color in marker_values:
        y = area.y(marker_value)
        draw.ellipse((x_resonance - 5, y - 5, x_resonance + 5, y + 5), fill=color, outline=WHITE, width=2)
    draw_text(draw, (x_resonance + 10, area.y(30) - 12), "30%", font=small, fill=GREEN_DARK)
    draw_text(
        draw,
        (x_resonance + 10, area.y(39) - 12),
        "33\N{EN DASH}39% critical range",
        font=small,
        fill=GREEN_DARK,
    )
    draw_text(draw, (x_resonance + 10, area.y(122) - 12), "122% Roaring Echo", font=small, fill="#9a5612")
    draw_text(
        draw,
        (x_resonance + 10, area.y(158.6) - 12),
        "134\N{EN DASH}159% critical range",
        font=small,
        fill="#9a5612",
    )

    draw_text(
        draw,
        (area.left, 18),
        f"Resonant recast scaling \N{EM DASH} {BUILD_LABEL}",
        font=title,
        fill="#111111",
    )
    draw_text(
        draw,
        (area.left, 58),
        (
            "R = Resonance stat     Values below are percentages of the "
            "spell\N{RIGHT SINGLE QUOTATION MARK}s scalable base component"
        ),
        font=small,
        fill=MUTED,
    )
    draw_text(draw, (area.left, 94), "Ordinary resonance:  30%", font=font, fill=GREEN_DARK)
    draw_text(
        draw,
        (area.left + 390, 94),
        "Critical blast:  33\N{EN DASH}39%  (\N{MULTIPLICATION SIGN}1.10\N{EN DASH}1.30)",
        font=font,
        fill=GREEN_DARK,
    )
    draw_text(draw, (area.left, 130), "Roaring Echo, R > 100:  R%", font=font, fill="#9a5612")
    draw_text(
        draw,
        (area.left + 390, 130),
        "Roaring Echo + critical:  1.10R\N{EN DASH}1.30R%",
        font=font,
        fill="#9a5612",
    )
    draw.rounded_rectangle((area.left, 166, area.right, 198), radius=7, fill=CALLOUT)
    draw_text(
        draw,
        (area.left + 14, 171),
        "Resonance chance is R% (guaranteed at R ≥ 100); Roaring Echo proc chance is 30% per ascension rank.",
        font=small,
        fill="#333b46",
    )

    legend_y = area.top + 8
    draw.line((area.left + 15, legend_y + 10, area.left + 65, legend_y + 10), fill=GREEN, width=4)
    draw_text(draw, (area.left + 75, legend_y - 2), "Ordinary resonance", font=small, fill="#333333")
    draw.line((area.left + 300, legend_y + 10, area.left + 350, legend_y + 10), fill=AMBER, width=4)
    draw_text(draw, (area.left + 360, legend_y - 2), "Roaring Echo", font=small, fill="#333333")
    draw.line((area.left + 545, legend_y + 10, area.left + 595, legend_y + 10), fill=PURPLE, width=3)
    draw_text(draw, (area.left + 605, legend_y - 2), "122 RES example", font=small, fill="#333333")

    x_label = "Resonance stat R"
    box = text_bbox(draw, x_label, font)
    draw_text(
        draw,
        ((area.left + area.right - (box[2] - box[0])) / 2, 738),
        x_label,
        font=font,
        fill=INK,
    )
    draw_vertical_label(
        image,
        "Resonant base component (% of original)",
        font=font,
        left=28,
        center_y=(area.top + area.bottom) / 2,
    )
    draw_text(draw, (area.x(5), area.y(100) - 25), "Original spell = 100%", font=small, fill="#666666")

    # Restore the final approved low-range annotations without overlapping the 122 RES guide.
    region_left = x_resonance - 9
    region_top = area.y(52)
    region_bottom = area.y(18)
    draw.rectangle((region_left, region_top, area.right, region_bottom), fill=WHITE)
    for value in (125, 150):
        x = area.x(value)
        if region_left <= x <= area.right:
            draw.line((x, region_top, x, region_bottom), fill=GRID, width=1)
    for value in (25, 50):
        y = area.y(value)
        draw.line((region_left, y, area.right, y), fill=GRID, width=1)
    draw.rectangle((region_left, area.y(39), area.right, area.y(33)), fill=GREEN_SOFT)
    draw.line((region_left, area.y(30), area.right, area.y(30)), fill=GREEN, width=4)
    draw.line((x_resonance, region_top, x_resonance, region_bottom), fill=PURPLE, width=3)

    bracket_x = x_resonance + 8
    draw.line((bracket_x, area.y(39), bracket_x, area.y(33)), fill=GREEN, width=2)
    draw.line((bracket_x - 4, area.y(39), bracket_x + 4, area.y(39)), fill=GREEN, width=2)
    draw.line((bracket_x - 4, area.y(33), bracket_x + 4, area.y(33)), fill=GREEN, width=2)
    draw_text(
        draw,
        (x_resonance + 18, area.y(48)),
        "33\N{EN DASH}39% critical range",
        font=small,
        fill=GREEN_DARK,
    )
    draw.ellipse(
        (x_resonance - 5, area.y(30) - 5, x_resonance + 5, area.y(30) + 5),
        fill=GREEN,
        outline=WHITE,
        width=2,
    )
    draw_text(
        draw,
        (x_resonance + 18, area.y(24)),
        "30% ordinary resonance",
        font=small,
        fill=GREEN_DARK,
    )
    image.save(path, format="PNG", compress_level=9)


def render_reported_results(path: Path) -> None:
    """Render the originally approved like-for-like Brax's Wrath results plot."""
    image = Image.new("RGB", (IMAGE_WIDTH, 780), WHITE)
    draw = ImageDraw.Draw(image)
    font = FONTS.get(22)
    small = FONTS.get(18)
    title = FONTS.get(30, bold=True)
    area = PlotArea(255, 205, 1135, 675, 0, 50_000, 0, 1)

    for value in range(0, 50_001, 10_000):
        x = area.x(value)
        draw.line((x, area.top, x, area.bottom), fill=GRID, width=1)
        label = f"{value:,}"
        box = text_bbox(draw, label, small)
        draw_text(draw, (x - (box[2] - box[0]) / 2, area.bottom + 12), label, font=small, fill="#333333")
    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)

    groups = (
        ("Original cast", REPORTED_ORIGINAL, REPORTED_ORIGINAL_CRITICAL, 285),
        ("Ordinary resonance", REPORTED_ORDINARY_RESONANCE, REPORTED_ORDINARY_CRITICAL, 425),
        ("Roaring Echo", REPORTED_ROARING_ECHO, REPORTED_ROARING_ECHO_CRITICAL, 565),
    )
    bar_height = 32
    for label, normal, critical, center_y in groups:
        box = text_bbox(draw, label, font)
        draw_text(
            draw,
            (area.left - 22 - (box[2] - box[0]), center_y - 17),
            label,
            font=font,
            fill=INK,
        )
        normal_y = center_y - 38
        draw.rounded_rectangle(
            (area.left, normal_y, area.x(normal), normal_y + bar_height),
            radius=5,
            fill=BLUE,
        )
        draw_text(draw, (area.x(normal) + 10, normal_y + 4), f"{normal:,}", font=small, fill=BLUE_DARK)

        critical_y = center_y + 8
        draw.rounded_rectangle(
            (area.left, critical_y, area.x(critical), critical_y + bar_height),
            radius=5,
            fill="#d18a24",
        )
        increase = (critical / normal - 1) * 100
        draw_text(
            draw,
            (area.x(critical) + 10, critical_y + 4),
            f"{critical:,}  (+{increase:.1f}%)",
            font=small,
            fill=AMBER_DARK,
        )

    draw_text(
        draw,
        (155, 20),
        "Brax\N{RIGHT SINGLE QUOTATION MARK}s Wrath at 122 Resonance \N{EM DASH} like-for-like results",
        font=title,
        fill="#111111",
    )
    draw_text(
        draw,
        (155, 62),
        "Each critical hit is compared with the non-critical result from the same damage path.",
        font=small,
        fill=MUTED,
    )
    draw.rounded_rectangle((155, 105, 1140, 171), radius=9, fill=CALLOUT)
    draw_text(
        draw,
        (173, 116),
        "Code check: normal 33,335 and Roaring Echo 38,927 imply an ordinary resonance of 15,542.",
        font=small,
        fill="#333b46",
    )
    draw_text(
        draw,
        (173, 142),
        "Observed ordinary resonance: 15,548 \N{EM DASH} a difference of only 6 damage.",
        font=small,
        fill=GREEN_DARK,
    )

    draw.rounded_rectangle((area.left, area.top + 8, area.left + 34, area.top + 34), radius=4, fill=BLUE)
    draw_text(draw, (area.left + 45, area.top + 9), "Non-critical", font=small, fill="#333333")
    draw.rounded_rectangle(
        (area.left + 190, area.top + 8, area.left + 224, area.top + 34),
        radius=4,
        fill="#d18a24",
    )
    draw_text(draw, (area.left + 235, area.top + 9), "Critical Blast", font=small, fill="#333333")

    x_label = "Damage"
    box = text_bbox(draw, x_label, font)
    draw_text(
        draw,
        ((area.left + area.right - (box[2] - box[0])) / 2, 730),
        x_label,
        font=font,
        fill=INK,
    )
    image.save(path, format="PNG", compress_level=9)


def physical_critical_class_series(
    level: int,
    proficiency: int,
) -> tuple[CriticalSeries, ...]:
    """Build the three class-branch curves for one proficiency panel."""
    return tuple(
        CriticalSeries(
            values=tuple(
                100.0 * critical_hit_chance(level, dexterity, proficiency, style.profile)
                for dexterity in range(CRITICAL_DEX_MAX + 1)
            ),
            color=style.color,
            dash_pattern=style.dash_pattern,
        )
        for style in CRITICAL_CLASS_STYLES
    )


def render_physical_critical_chance(path: Path) -> None:
    """Render a compact class comparison at four Finesse values."""
    image_height = 810
    image = Image.new("RGB", (IMAGE_WIDTH, image_height), WHITE)
    draw = ImageDraw.Draw(image)
    title_font = FONTS.get(28, bold=True)
    font = FONTS.get(21)
    note = FONTS.get(17)
    formula_font = FONTS.get(18)
    panel_font = FONTS.get(19, bold=True)
    proficiencies = (10, 20, 30, 40)
    panel_lefts = (115, 660)
    panel_tops = (190, 455)
    panel_width = 480
    panel_height = 225
    panels: list[PlotArea] = []

    for index, proficiency in enumerate(proficiencies):
        row, column = divmod(index, 2)
        area = PlotArea(
            panel_lefts[column],
            panel_tops[row],
            panel_lefts[column] + panel_width,
            panel_tops[row] + panel_height,
            0,
            CRITICAL_DEX_MAX,
            0,
            CRITICAL_CHANCE_MAX,
        )
        panels.append(area)
        draw_critical_panel_frame(
            draw,
            area,
            note=note,
            show_x_labels=row == 1,
        )
        draw_critical_curves(
            draw,
            area,
            physical_critical_class_series(MAX_PLAYER_LEVEL, proficiency),
        )

        panel_label = f"F={proficiency}"
        bounds = text_bbox(draw, panel_label, panel_font)
        label_right = area.left + 13 + bounds[2] - bounds[0]
        label_bottom = area.top + 9 + bounds[3] - bounds[1]
        draw.rounded_rectangle(
            (area.left + 6, area.top + 5, label_right + 6, label_bottom + 5),
            radius=5,
            fill=WHITE,
            outline=GRID,
            width=1,
        )
        draw_text(
            draw,
            (area.left + 13, area.top + 9 - bounds[1]),
            panel_label,
            font=panel_font,
            fill=INK,
        )

    draw_text(
        draw,
        (115, 18),
        f"Physical critical chance by Finesse and class \N{EM DASH} {BUILD_LABEL}",
        font=title_font,
        fill="#111111",
    )
    draw_text(
        draw,
        (115, 60),
        f"L={MAX_PLAYER_LEVEL}     D=Dexterity     F=Finesse     "
        + "n=floor(D \N{MULTIPLICATION SIGN} F/100)+1 for shown F     p=L/(100\N{MINUS SIGN}F)",
        font=formula_font,
        fill=BLUE_DARK,
    )
    draw_text(
        draw,
        (115, 96),
        "Ordinary: n trials at p     Stormcaller: ordinary + n trials at 0.4p     "
        + "Windblade: ordinary + n trials at p",
        font=note,
        fill=MUTED,
    )
    draw_critical_legend(draw, font=note, left=115, y=150)

    x_label = "Dexterity"
    bounds = text_bbox(draw, x_label, font)
    draw_text(
        draw,
        ((panels[2].left + panels[3].right - (bounds[2] - bounds[0])) / 2, 750),
        x_label,
        font=font,
        fill=INK,
    )
    draw_vertical_label(
        image,
        "Physical critical chance",
        font=font,
        left=16,
        center_y=(panels[0].top + panels[2].bottom) / 2,
    )
    image.save(path, format="PNG", compress_level=9)


def _minimum_critical_dexterity(
    level: int,
    finesse: int,
    profile: CriticalProfile,
    target: float,
) -> int:
    """Return the first Dexterity value whose critical chance reaches target."""
    if not 0.0 < target < 1.0:
        raise ValueError("target must be greater than 0 and less than 1")

    lower = 0
    upper = 1
    while critical_hit_chance(level, upper, finesse, profile) < target:
        upper *= 2
    while lower < upper:
        midpoint = (lower + upper) // 2
        if critical_hit_chance(level, midpoint, finesse, profile) >= target:
            upper = midpoint
        else:
            lower = midpoint + 1
    return lower


def render_physical_critical_dexterity_bands(path: Path) -> None:
    """Render level-35 Dexterity thresholds for 95.5% through 98% crit."""
    image = Image.new("RGB", (IMAGE_WIDTH, 1_120), WHITE)
    draw = ImageDraw.Draw(image)
    title_font = FONTS.get(28, bold=True)
    formula_font = FONTS.get(18)
    note = FONTS.get(17)
    axis_font = FONTS.get(19)
    label_font = FONTS.get(17, bold=True)
    table_header_font = FONTS.get(15, bold=True)
    table_header_small = FONTS.get(13, bold=True)
    table_font = FONTS.get(16)
    table_bold = FONTS.get(16, bold=True)

    finesse_values = tuple(range(5, 41))
    breakpoints = tuple(range(5, 41, 5))
    lower_target = 0.955
    upper_target = 0.98
    bands = {
        style.profile: (
            tuple(
                _minimum_critical_dexterity(MAX_PLAYER_LEVEL, finesse, style.profile, lower_target)
                for finesse in finesse_values
            ),
            tuple(
                _minimum_critical_dexterity(MAX_PLAYER_LEVEL, finesse, style.profile, upper_target)
                for finesse in finesse_values
            ),
        )
        for style in CRITICAL_CLASS_STYLES
    }
    soft_fills = {
        CriticalProfile.ORDINARY: BLUE_SOFT,
        CriticalProfile.STORMCALLER: GREEN_SOFT,
        CriticalProfile.WINDBLADE: AMBER_SOFT,
    }

    area = PlotArea(125, 235, 1_135, 675, 5, 46, 0, 1)
    log_min = math.log2(180)
    log_max = math.log2(6_600)

    def dexterity_y(value: int) -> float:
        ratio = (math.log2(value) - log_min) / (log_max - log_min)
        return area.bottom - ratio * (area.bottom - area.top)

    for finesse in range(5, 41):
        x = area.x(finesse)
        draw.line(
            (x, area.top, x, area.bottom),
            fill=GRID if finesse % 5 == 0 else "#eeeeee",
            width=1,
        )
    for value in (200, 400, 800, 1_600, 3_200, 6_400):
        y = dexterity_y(value)
        draw.line((area.left, y, area.right, y), fill=GRID, width=1)
        label = f"{value:,}"
        bounds = text_bbox(draw, label, note)
        draw_text(
            draw,
            (area.left - 14 - (bounds[2] - bounds[0]), y - (bounds[3] - bounds[1]) / 2 - bounds[1]),
            label,
            font=note,
            fill=INK,
        )
    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)

    for finesse in breakpoints:
        x = area.x(finesse)
        label = str(finesse)
        bounds = text_bbox(draw, label, note)
        draw_text(
            draw,
            (x - (bounds[2] - bounds[0]) / 2, area.bottom + 12),
            label,
            font=note,
            fill=INK,
        )

    for style in CRITICAL_CLASS_STYLES:
        lower, upper = bands[style.profile]
        lower_points = [
            (area.x(finesse), dexterity_y(value)) for finesse, value in zip(finesse_values, lower, strict=True)
        ]
        upper_points = [
            (area.x(finesse), dexterity_y(value)) for finesse, value in zip(finesse_values, upper, strict=True)
        ]
        draw.polygon(lower_points + list(reversed(upper_points)), fill=soft_fills[style.profile])
        draw.line(lower_points, fill=style.color, width=4)
        draw_dashed_path(draw, upper_points, fill=style.color, width=4, dash_pattern=(9, 6))

        for finesse in breakpoints:
            index = finesse - finesse_values[0]
            x = area.x(finesse)
            draw_marker(
                draw,
                (x, dexterity_y(lower[index])),
                shape="circle",
                fill=style.color,
                radius=4,
            )
            draw_marker(
                draw,
                (x, dexterity_y(upper[index])),
                shape="diamond",
                fill=style.color,
                radius=4,
            )

        plot_label = style.label
        if style.profile is CriticalProfile.ORDINARY:
            plot_label = "Arcanist · Druid\nPaladin · Reaver"
        label_x = area.x(40.55)
        label_y = dexterity_y(round(math.sqrt(lower[-1] * upper[-1])))
        bounds = draw.multiline_textbbox((0, 0), plot_label, font=label_font, spacing=0)
        draw.rounded_rectangle(
            (
                label_x - 4,
                label_y - (bounds[3] - bounds[1]) / 2 - 3,
                label_x + bounds[2] - bounds[0] + 5,
                label_y + (bounds[3] - bounds[1]) / 2 + 3,
            ),
            radius=4,
            fill=WHITE,
        )
        draw.multiline_text(
            (label_x, label_y - (bounds[3] - bounds[1]) / 2 - bounds[1]),
            plot_label,
            font=label_font,
            fill=style.color,
            spacing=0,
        )

    draw_text(
        draw,
        (125, 28),
        f"Dexterity needed for 95.5\N{EN DASH}98% physical crit \N{EM DASH} {BUILD_LABEL}",
        font=title_font,
        fill="#111111",
    )
    draw_text(
        draw,
        (125, 78),
        "L=35     D=Dexterity     F=Finesse     c=physical crit chance",
        font=formula_font,
        fill=BLUE_DARK,
    )
    draw_text(
        draw,
        (125, 116),
        "Arcanist, Druid, Paladin, Reaver: 1 full-strength group     "
        + "Stormcaller: +0.4-strength group     Windblade: +1 full-strength group",
        font=note,
        fill=MUTED,
    )
    draw_text(
        draw,
        (125, 153),
        "Bands mark minimum D for c≥95.5% (solid) and c≥98% (dashed). " + "A finite 100% breakpoint does not exist.",
        font=note,
        fill=MUTED,
    )

    x_label = "Finesse"
    bounds = text_bbox(draw, x_label, axis_font)
    draw_text(
        draw,
        ((area.left + area.right - (bounds[2] - bounds[0])) / 2, 712),
        x_label,
        font=axis_font,
        fill=INK,
    )
    draw_vertical_label(
        image,
        "Required Dexterity (base-2 log scale; each grid step doubles)",
        font=axis_font,
        left=20,
        center_y=(area.top + area.bottom) / 2,
    )

    table_left = 125
    table_right = 1_135
    table_top = 815
    table_bottom = 1_075
    draw_text(
        draw,
        (table_left, 770),
        "Dexterity bands at 5-Finesse breakpoints",
        font=axis_font,
        fill=INK,
    )
    table_note = "Each range: 95.5% threshold \N{EN DASH} 98% threshold"
    bounds = text_bbox(draw, table_note, note)
    draw_text(
        draw,
        (table_right - (bounds[2] - bounds[0]), 773),
        table_note,
        font=note,
        fill=MUTED,
    )

    column_edges = (table_left, 247, 559, 842, table_right)
    column_centers = tuple((left + right) / 2 for left, right in pairwise(column_edges))
    row_height = (table_bottom - table_top) / 9
    headers = ("Finesse", *(style.label for style in CRITICAL_CLASS_STYLES))
    header_colors = (INK, *(style.color for style in CRITICAL_CLASS_STYLES))
    draw.line((table_left, table_top, table_right, table_top), fill=INK, width=2)
    for column, (center, label, color) in enumerate(zip(column_centers, headers, header_colors, strict=True)):
        font = table_header_small if column == 1 else table_header_font
        bounds = text_bbox(draw, label, font)
        draw_text(
            draw,
            (
                center - (bounds[2] - bounds[0]) / 2,
                table_top + (row_height - (bounds[3] - bounds[1])) / 2 - bounds[1],
            ),
            label,
            font=font,
            fill=color,
        )
    draw.line(
        (table_left, table_top + row_height, table_right, table_top + row_height),
        fill="#888888",
        width=1,
    )

    for row, finesse in enumerate(breakpoints, start=1):
        row_top = table_top + row * row_height
        row_bottom = row_top + row_height
        if row % 2 == 0:
            draw.rectangle((table_left, row_top, table_right, row_bottom), fill=CALLOUT)
        values = [str(finesse)]
        finesse_index = finesse - finesse_values[0]
        for style in CRITICAL_CLASS_STYLES:
            lower, upper = bands[style.profile]
            values.append(f"{lower[finesse_index]:,}\N{EN DASH}{upper[finesse_index]:,}")
        for column, (center, cell_value) in enumerate(zip(column_centers, values, strict=True)):
            font = table_bold if column == 0 else table_font
            bounds = text_bbox(draw, cell_value, font)
            draw_text(
                draw,
                (
                    center - (bounds[2] - bounds[0]) / 2,
                    row_top + (row_height - (bounds[3] - bounds[1])) / 2 - bounds[1],
                ),
                cell_value,
                font=font,
                fill=INK,
            )
        draw.line((table_left, row_bottom, table_right, row_bottom), fill=GRID, width=1)
    for edge in column_edges[1:-1]:
        draw.line((edge, table_top, edge, table_bottom), fill=GRID, width=1)

    image.save(path, format="PNG", compress_level=9)


def simple_critical_chance_percent(
    level: int,
    dexterity: int,
    finesse: int,
    profile: CriticalProfile,
) -> float:
    """Return the copy-and-paste calculator approximation as a percentage."""
    opportunities = dexterity * finesse // 100 + 1
    trial_chance = level / (100 - finesse)
    if profile is CriticalProfile.ORDINARY:
        class_factor = 1.0
    elif profile is CriticalProfile.STORMCALLER:
        class_factor = 1.4
    else:
        class_factor = 2.0
    return min(100.0, opportunities * trial_chance * class_factor)


def critical_calculator_error_series(
    level: int,
    finesse: int,
) -> tuple[CriticalSeries, ...]:
    """Build calculator-overestimate curves for one Finesse panel."""
    return tuple(
        CriticalSeries(
            values=tuple(
                simple_critical_chance_percent(level, dexterity, finesse, style.profile)
                - 100.0 * critical_hit_chance(level, dexterity, finesse, style.profile)
                for dexterity in range(CRITICAL_DEX_MAX + 1)
            ),
            color=style.color,
            dash_pattern=style.dash_pattern,
        )
        for style in CRITICAL_CLASS_STYLES
    )


def draw_critical_error_panel_frame(
    draw: ImageDraw.ImageDraw,
    area: PlotArea,
    *,
    note: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    show_x_labels: bool,
) -> None:
    """Draw one panel for calculator error in percentage points."""
    for value in range(0, CRITICAL_DEX_MAX + 1, CRITICAL_DEX_TICK):
        x = area.x(value)
        draw.line((x, area.top, x, area.bottom), fill=GRID, width=1)
        if show_x_labels:
            label = f"{value:,}"
            bounds = text_bbox(draw, label, note)
            draw_text(
                draw,
                (x - (bounds[2] - bounds[0]) / 2, area.bottom + 8),
                label,
                font=note,
                fill=INK,
            )

    for error_tick in (0.0, 1.0, 2.0, 3.0):
        y = area.y(error_tick)
        draw.line((area.left, y, area.right, y), fill=GRID, width=1)
        label = "0" if error_tick == 0 else f"{error_tick:.0f} pp"
        bounds = text_bbox(draw, label, note)
        draw_text(
            draw,
            (area.left - 14 - (bounds[2] - bounds[0]), y - (bounds[3] - bounds[1]) / 2),
            label,
            font=note,
            fill=INK,
        )

    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)


def render_physical_critical_calculator_error(path: Path) -> None:
    """Render the error introduced by the simple critical-chance formula."""
    image_height = 810
    image = Image.new("RGB", (IMAGE_WIDTH, image_height), WHITE)
    draw = ImageDraw.Draw(image)
    title_font = FONTS.get(28, bold=True)
    font = FONTS.get(21)
    note = FONTS.get(17)
    formula_font = FONTS.get(20, bold=True)
    panel_font = FONTS.get(19, bold=True)
    proficiencies = (10, 20, 30, 40)
    panel_lefts = (125, 665)
    panel_tops = (190, 455)
    panel_width = 475
    panel_height = 225
    panels: list[PlotArea] = []

    for index, finesse in enumerate(proficiencies):
        row, column = divmod(index, 2)
        area = PlotArea(
            panel_lefts[column],
            panel_tops[row],
            panel_lefts[column] + panel_width,
            panel_tops[row] + panel_height,
            0,
            CRITICAL_DEX_MAX,
            0,
            3.5,
        )
        panels.append(area)
        draw_critical_error_panel_frame(
            draw,
            area,
            note=note,
            show_x_labels=row == 1,
        )
        series = critical_calculator_error_series(MAX_PLAYER_LEVEL, finesse)
        draw_critical_curves(draw, area, series)

        for curve, style in zip(series, CRITICAL_CLASS_STYLES, strict=True):
            peak_error = max(curve.values)
            if peak_error < 0.1:
                continue
            peak_dexterity = curve.values.index(peak_error)
            peak_x = area.x(peak_dexterity)
            peak_y = area.y(peak_error)
            draw_marker(
                draw,
                (peak_x, peak_y),
                shape=style.marker_shape,
                fill=style.color,
                radius=6,
            )
            peak_label = f"{peak_error:.2f}"
            bounds = text_bbox(draw, peak_label, note)
            label_x = peak_x + 8
            if peak_dexterity > 850:
                label_x = peak_x - (bounds[2] - bounds[0]) - 8
            draw_text(
                draw,
                (label_x, max(area.top + 3, peak_y - 22)),
                peak_label,
                font=note,
                fill=style.color,
            )

        panel_label = f"F={finesse}"
        bounds = text_bbox(draw, panel_label, panel_font)
        label_right = area.left + 13 + bounds[2] - bounds[0]
        label_bottom = area.top + 9 + bounds[3] - bounds[1]
        draw.rounded_rectangle(
            (area.left + 6, area.top + 5, label_right + 6, label_bottom + 5),
            radius=5,
            fill=WHITE,
            outline=GRID,
            width=1,
        )
        draw_text(
            draw,
            (area.left + 13, area.top + 9 - bounds[1]),
            panel_label,
            font=panel_font,
            fill=INK,
        )

    draw_text(
        draw,
        (125, 18),
        f"Simple critical calculator overestimate \N{EM DASH} {BUILD_LABEL}",
        font=title_font,
        fill="#111111",
    )
    draw_text(
        draw,
        (125, 60),
        "Simple crit % = min(100, (floor(D \N{MULTIPLICATION SIGN} F/100)+1) "
        + "\N{MULTIPLICATION SIGN} L/(100\N{MINUS SIGN}F) \N{MULTIPLICATION SIGN} C)",
        font=formula_font,
        fill=BLUE_DARK,
    )
    draw_text(
        draw,
        (125, 96),
        "D=Dexterity     F=Finesse     " + "C=1 ordinary, 1.4 Stormcaller, 2 Windblade     L=35",
        font=note,
        fill=MUTED,
    )
    draw_critical_legend(draw, font=note, left=125, y=150)

    x_label = "Dexterity"
    bounds = text_bbox(draw, x_label, font)
    draw_text(
        draw,
        ((panels[2].left + panels[3].right - (bounds[2] - bounds[0])) / 2, 750),
        x_label,
        font=font,
        fill=INK,
    )
    draw_vertical_label(
        image,
        "Calculator overestimate",
        font=font,
        left=15,
        center_y=(panels[0].top + panels[2].bottom) / 2,
    )
    draw_text(
        draw,
        (125, 782),
        "Error = simple formula \N{MINUS SIGN} exact game chance. Positive values overestimate; labels mark peaks.",
        font=note,
        fill=MUTED,
    )
    image.save(path, format="PNG", compress_level=9)


def render_physical_critical_expected_damage(path: Path) -> None:
    """Render long-run same-path damage multipliers from physical criticals."""
    image = Image.new("RGB", (IMAGE_WIDTH, 760), WHITE)
    draw = ImageDraw.Draw(image)
    font = FONTS.get(22)
    note = FONTS.get(20)
    title = FONTS.get(30, bold=True)
    area = PlotArea(145, 200, 930, 620, 0, 100, 1.0, 1.7)

    for value in range(0, 101, 10):
        x = area.x(value)
        draw.line((x, area.top, x, area.bottom), fill=GRID, width=1)
        label = f"{value}%"
        bounds = text_bbox(draw, label, note)
        draw_text(draw, (x - (bounds[2] - bounds[0]) / 2, area.bottom + 10), label, font=note, fill=INK)
    for index in range(8):
        ratio_tick = 1.0 + 0.1 * index
        y = area.y(ratio_tick)
        draw.line((area.left, y, area.right, y), fill=GRID, width=1)
        label = f"{ratio_tick:.1f}x"
        bounds = text_bbox(draw, label, note)
        draw_text(
            draw,
            (area.left - 18 - (bounds[2] - bounds[0]), y - (bounds[3] - bounds[1]) / 2),
            label,
            font=note,
            fill=INK,
        )
    draw.line((area.left, area.top, area.left, area.bottom), fill=INK, width=3)
    draw.line((area.left, area.bottom, area.right, area.bottom), fill=INK, width=3)

    crippling_multiplier = crippling_blow_expected_critical_multiplier()
    reckless_multiplier = RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER
    series = (
        (
            "Standard",
            STANDARD_CRITICAL_MULTIPLIER,
            BLUE,
            BLUE_DARK,
            None,
            "circle",
        ),
        (
            "Crippling",
            crippling_multiplier,
            GREEN,
            GREEN_DARK,
            (18, 10),
            "square",
        ),
        (
            "Reckless",
            reckless_multiplier,
            AMBER,
            AMBER_DARK,
            (7, 7),
            "diamond",
        ),
    )
    plotted: list[tuple[str, list[float], str, str, str]] = []
    for label, critical_multiplier, color, label_color, dash_pattern, marker_shape in series:
        ratios = [
            expected_damage_multiplier(critical_chance / 100.0, critical_multiplier) for critical_chance in range(101)
        ]
        plotted.append((label, ratios, color, label_color, marker_shape))
        points = [(area.x(index), area.y(ratio)) for index, ratio in enumerate(ratios)]
        if dash_pattern is None:
            draw.line(points, fill=color, width=4, joint="curve")
        else:
            draw_dashed_path(draw, points, fill=color, width=4, dash_pattern=dash_pattern)
        draw_marker(draw, (area.x(100), area.y(ratios[-1])), shape=marker_shape, fill=color, radius=8)
        draw_endpoint_label(
            draw,
            area,
            ratios[-1],
            f"{label}: {ratios[-1]:.2f}x",
            font=note,
            fill=label_color,
        )

    x_anchor = area.x(50)
    draw_dashed_path(
        draw,
        [(x_anchor, area.top), (x_anchor, area.bottom)],
        fill="#8a8a8a",
        width=2,
        dash_pattern=(9, 7),
    )
    for _, ratios, color, _, marker_shape in plotted:
        y_anchor = area.y(ratios[50])
        draw_marker(draw, (x_anchor, y_anchor), shape=marker_shape, fill=color, radius=8)
    draw_text(
        draw,
        (area.left, 158),
        "At c=50%: Standard 1.25x     Crippling 1.325x     Reckless 1.15x",
        font=note,
        fill=INK,
    )

    draw_text(
        draw,
        (area.left, 18),
        f"Long-run same-path damage from physical criticals \N{EM DASH} {BUILD_LABEL}",
        font=title,
        fill="#111111",
    )
    draw_text(
        draw,
        (area.left, 58),
        "c = physical critical chance     Ratio = long-run same-path damage \N{DIVISION SIGN} non-critical damage",
        font=font,
        fill=MUTED,
    )
    draw_text(
        draw,
        (area.left, 96),
        (
            f"Before rounding: Standard 1 + {STANDARD_CRITICAL_MULTIPLIER - 1:.2f}c     "
            f"Crippling* 1 + {crippling_multiplier - 1:.2f}c     "
            f"Reckless relative 1 + {RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER - 1:.2f}c"
        ),
        font=font,
        fill=BLUE_DARK,
    )
    draw_text(
        draw,
        (area.left, 132),
        (
            f"*Eligible auto-melee. Crippling inputs: {CRIPPLING_BLOW_PROC_CHANCE:.0%} proc chance; "
            f"{CRIPPLING_BLOW_CRITICAL_MULTIPLIER:.1f}x proc critical multiplier."
        ),
        font=note,
        fill=MUTED,
    )

    x_label = "Physical critical chance c"
    bounds = text_bbox(draw, x_label, font)
    draw_text(
        draw,
        ((area.left + area.right - (bounds[2] - bounds[0])) / 2, 660),
        x_label,
        font=font,
        fill=INK,
    )
    draw_vertical_label(image, "Expected damage ratio", font=font, left=26, center_y=(area.top + area.bottom) / 2)
    draw_text(
        draw,
        (area.left, 704),
        (
            "Scope: physical same-path criticals only "
            + "\N{EM DASH} excludes Critical Blast, DOT/heal/backstab, misses, "
            + "and changing inputs."
        ),
        font=note,
        fill=MUTED,
    )
    draw_text(
        draw,
        (area.left, 732),
        "Long-run ratio; per-hit rounding and downstream processing can move observed results.",
        font=note,
        fill=MUTED,
    )
    image.save(path, format="PNG", compress_level=9)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render approved Chant Control, Resonance, and physical critical mechanics wiki plots."
    )
    _ = parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("wiki/mechanics/images"),
        help="directory for generated PNGs (default: wiki/mechanics/images)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = cast("Path", args.output_dir)
    verify_values()
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = (
        ("chant-control-scaling.png", render_chant_control),
        ("resonance-scaling.png", render_resonance),
        ("resonance-observed-results.png", render_reported_results),
        ("physical-critical-chance-by-class.png", render_physical_critical_chance),
        ("physical-critical-dexterity-band-by-finesse.png", render_physical_critical_dexterity_bands),
        ("physical-critical-calculator-error.png", render_physical_critical_calculator_error),
        ("physical-critical-expected-damage.png", render_physical_critical_expected_damage),
    )
    for filename, renderer in outputs:
        path = output_dir / filename
        renderer(path)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
