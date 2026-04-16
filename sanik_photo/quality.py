from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

try:
    from PIL import Image, ImageFilter, ImageOps, ImageStat
except ImportError:
    Image = None
    ImageFilter = None
    ImageOps = None
    ImageStat = None


@dataclass(frozen=True)
class QualityScores:
    sharpness: float
    lighting: float
    composition: float
    expression: float | None
    overall: float


def score_image(image: "Image.Image") -> QualityScores:
    if ImageFilter is None or ImageOps is None or ImageStat is None:
        return QualityScores(0.0, 0.0, 0.0, None, 0.0)

    prepared = ImageOps.exif_transpose(image).convert("RGB")
    thumbnail = prepared.copy()
    thumbnail.thumbnail((512, 512))
    grayscale = thumbnail.convert("L")

    sharpness = sharpness_score(grayscale)
    lighting = lighting_score(grayscale)
    composition = composition_score(grayscale)
    expression = None

    # Expression stays neutral until local face/eye analysis is added.
    overall = (sharpness * 0.42) + (lighting * 0.33) + (composition * 0.25)
    return QualityScores(
        sharpness=round(sharpness, 3),
        lighting=round(lighting, 3),
        composition=round(composition, 3),
        expression=expression,
        overall=round(overall, 3),
    )


def sharpness_score(grayscale: "Image.Image") -> float:
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    edge_mean = stat.mean[0] / 255
    edge_std = stat.stddev[0] / 128
    return clamp((edge_mean * 1.8) + (edge_std * 0.8))


def lighting_score(grayscale: "Image.Image") -> float:
    stat = ImageStat.Stat(grayscale)
    brightness = stat.mean[0]
    contrast = stat.stddev[0]

    brightness_score = 1 - abs(brightness - 128) / 128
    contrast_score = clamp(contrast / 64)

    histogram = grayscale.histogram()
    total = sum(histogram) or 1
    clipped_dark = sum(histogram[:8]) / total
    clipped_light = sum(histogram[248:]) / total
    clipping_penalty = clamp((clipped_dark + clipped_light) * 4)

    return clamp((brightness_score * 0.55) + (contrast_score * 0.45) - clipping_penalty)


def composition_score(grayscale: "Image.Image") -> float:
    small = grayscale.resize((32, 32))
    edges = small.filter(ImageFilter.FIND_EDGES)
    pixel_data = edges.get_flattened_data() if hasattr(edges, "get_flattened_data") else edges.getdata()
    pixels = list(pixel_data)

    total_energy = sum(pixels)
    if total_energy <= 0:
        return 0.25

    width, height = small.size
    center_energy = region_energy(pixels, width, 10, 10, 22, 22)
    third_points = (
        region_energy(pixels, width, 8, 8, 14, 14),
        region_energy(pixels, width, 18, 8, 24, 14),
        region_energy(pixels, width, 8, 18, 14, 24),
        region_energy(pixels, width, 18, 18, 24, 24),
    )
    border_energy = total_energy - region_energy(pixels, width, 4, 4, 28, 28)

    focus_score = clamp(max(center_energy, max(third_points)) / total_energy * 3.2)
    border_penalty = clamp(border_energy / total_energy * 2.5)
    balance = horizontal_balance_score(pixels, width, height)

    return clamp((focus_score * 0.55) + (balance * 0.35) + 0.15 - (border_penalty * 0.25))


def horizontal_balance_score(pixels: list[int], width: int, height: int) -> float:
    left = region_energy(pixels, width, 0, 0, width // 2, height)
    right = region_energy(pixels, width, width // 2, 0, width, height)
    total = left + right
    if total <= 0:
        return 0.5
    return 1 - abs(left - right) / total


def region_energy(
    pixels: list[int],
    width: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> float:
    values: list[int] = []
    for y in range(top, bottom):
        offset = y * width
        values.extend(pixels[offset + left : offset + right])
    if not values:
        return 0.0
    return mean(values) * len(values)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
