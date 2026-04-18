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

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


@dataclass(frozen=True)
class QualityScores:
    sharpness: float
    lighting: float
    composition: float
    expression: float | None
    people: float | None
    scenery: float
    face_count: int
    overall: float


def score_image(image: "Image.Image") -> QualityScores:
    if ImageFilter is None or ImageOps is None or ImageStat is None:
        return QualityScores(0.0, 0.0, 0.0, None, None, 0.0, 0, 0.0)

    prepared = ImageOps.exif_transpose(image).convert("RGB")
    thumbnail = prepared.copy()
    thumbnail.thumbnail((512, 512))
    grayscale = thumbnail.convert("L")

    sharpness = sharpness_score(grayscale)
    lighting = lighting_score(grayscale)
    composition = composition_score(grayscale)
    face_count, face_presence, expression = face_expression_signals(thumbnail)
    people = people_quality_score(face_presence, expression, sharpness, lighting)
    scenery = scenery_quality_score(thumbnail, grayscale, sharpness, lighting, composition, face_presence)

    if expression is None:
        overall = (sharpness * 0.42) + (lighting * 0.33) + (composition * 0.25)
    else:
        overall = (sharpness * 0.34) + (lighting * 0.27) + (composition * 0.20) + (expression * 0.19)
    return QualityScores(
        sharpness=round(sharpness, 3),
        lighting=round(lighting, 3),
        composition=round(composition, 3),
        expression=expression,
        people=round(people, 3) if people is not None else None,
        scenery=round(scenery, 3),
        face_count=face_count,
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


def face_expression_signals(image: "Image.Image") -> tuple[int, float | None, float | None]:
    if cv2 is None or np is None:
        return 0, None, None

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
    if face_cascade.empty() or smile_cascade.empty():
        return 0, None, None

    cv_image = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(36, 36))
    if len(faces) == 0:
        return 0, None, None

    scores: list[float] = []
    image_area = gray.shape[0] * gray.shape[1]
    face_presence_scores: list[float] = []
    for x, y, width, height in faces:
        face_area_ratio = (width * height) / image_area
        face_presence_scores.append(clamp(face_area_ratio * 8))
        face_gray = gray[y : y + height, x : x + width]
        lower_face = face_gray[height // 2 :, :]
        smiles = smile_cascade.detectMultiScale(
            lower_face,
            scaleFactor=1.7,
            minNeighbors=18,
            minSize=(max(18, width // 5), max(8, height // 12)),
        )
        if len(smiles) == 0:
            scores.append(0.25)
            continue

        best = max(smiles, key=lambda smile: smile[2] * smile[3])
        smile_width_ratio = best[2] / width
        natural_width = 1 - abs(smile_width_ratio - 0.42) / 0.42
        face_size_score = clamp(face_area_ratio * 8)
        scores.append(clamp((natural_width * 0.75) + (face_size_score * 0.25)))

    return len(faces), round(max(face_presence_scores), 3), round(max(scores), 3)


def people_quality_score(
    face_presence: float | None,
    expression: float | None,
    sharpness: float,
    lighting: float,
) -> float | None:
    if face_presence is None:
        return None
    smile = expression if expression is not None else 0.25
    return clamp((face_presence * 0.35) + (smile * 0.30) + (sharpness * 0.20) + (lighting * 0.15))


def scenery_quality_score(
    image: "Image.Image",
    grayscale: "Image.Image",
    sharpness: float,
    lighting: float,
    composition: float,
    face_presence: float | None,
) -> float:
    richness = color_richness_score(image)
    dynamic_range = dynamic_range_score(grayscale)
    face_penalty = 0.18 * (face_presence or 0.0)
    return clamp(
        (richness * 0.28)
        + (dynamic_range * 0.22)
        + (composition * 0.20)
        + (sharpness * 0.15)
        + (lighting * 0.15)
        - face_penalty
    )


def color_richness_score(image: "Image.Image") -> float:
    sample = image.convert("HSV").resize((96, 96))
    pixel_data = sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata()
    pixels = list(pixel_data)
    if not pixels:
        return 0.0
    saturation = mean(pixel[1] for pixel in pixels) / 255
    value = mean(pixel[2] for pixel in pixels) / 255
    natural_saturation = 1 - abs(saturation - 0.48) / 0.48
    return clamp((natural_saturation * 0.65) + (value * 0.35))


def dynamic_range_score(grayscale: "Image.Image") -> float:
    stat = ImageStat.Stat(grayscale)
    contrast = clamp(stat.stddev[0] / 72)
    histogram = grayscale.histogram()
    total = sum(histogram) or 1
    clipped = (sum(histogram[:6]) + sum(histogram[250:])) / total
    return clamp(contrast - (clipped * 2.5))


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
