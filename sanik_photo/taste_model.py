from __future__ import annotations

import math
from dataclasses import dataclass
from time import time

from .database import PhotoDatabase
from .models import PhotoRecord


MODEL_SETTING_KEY = "taste_model_v1"
FEATURE_NAMES = (
    "quality",
    "sharpness",
    "lighting",
    "composition",
    "megapixels",
    "file_size",
)


@dataclass(frozen=True)
class TasteModelResult:
    trained: bool
    message: str
    model: dict | None = None


def train_taste_model(database: PhotoDatabase) -> TasteModelResult:
    rated = database.list_rated_photos()
    liked = [photo for photo in rated if photo.user_rating == 1]
    rejected = [photo for photo in rated if photo.user_rating == -1]

    if len(liked) < 2 or len(rejected) < 2:
        return TasteModelResult(
            trained=False,
            message="Mark at least 2 liked and 2 rejected photos to train the taste model.",
        )

    positive_mean = mean_vector([feature_vector(photo) for photo in liked])
    negative_mean = mean_vector([feature_vector(photo) for photo in rejected])
    weights = [positive - negative for positive, negative in zip(positive_mean, negative_mean)]
    midpoint = [(positive + negative) / 2 for positive, negative in zip(positive_mean, negative_mean)]
    intercept = -sum(weight * value for weight, value in zip(weights, midpoint))

    model = {
        "version": 1,
        "feature_names": list(FEATURE_NAMES),
        "weights": weights,
        "intercept": intercept,
        "liked_count": len(liked),
        "rejected_count": len(rejected),
        "trained_at": time(),
    }
    database.save_setting(MODEL_SETTING_KEY, model)
    return TasteModelResult(
        trained=True,
        message=f"Trained taste model from {len(liked)} liked and {len(rejected)} rejected photos.",
        model=model,
    )


def load_taste_model(database: PhotoDatabase) -> dict | None:
    model = database.load_setting(MODEL_SETTING_KEY)
    if not model or model.get("version") != 1:
        return None
    return model


def predict_taste_score(photo: PhotoRecord, model: dict | None) -> float | None:
    if not model:
        return None
    weights = model.get("weights", [])
    intercept = float(model.get("intercept", 0.0))
    features = feature_vector(photo)
    if len(weights) != len(features):
        return None
    raw_score = intercept + sum(float(weight) * value for weight, value in zip(weights, features))
    return sigmoid(raw_score * 4)


def blended_photo_score(photo: PhotoRecord, model: dict | None) -> float:
    quality = photo.quality_score if photo.quality_score is not None else 0.0
    taste_score = predict_taste_score(photo, model)
    score = quality if taste_score is None else (quality * 0.45) + (taste_score * 0.55)

    if photo.user_rating == 1:
        return min(1.5, score + 0.5)
    if photo.user_rating == 0:
        return max(0.05, score * 0.75)
    if photo.user_rating == -1:
        return -1.0
    return score


def feature_vector(photo: PhotoRecord) -> list[float]:
    width = photo.width or 0
    height = photo.height or 0
    megapixels = min((width * height) / 12_000_000, 1.0)
    file_size = min(photo.file_size / 10_000_000, 1.0)
    return [
        safe_score(photo.quality_score),
        safe_score(photo.sharpness_score),
        safe_score(photo.lighting_score),
        safe_score(photo.composition_score),
        megapixels,
        file_size,
    ]


def mean_vector(vectors: list[list[float]]) -> list[float]:
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(len(vectors[0]))]


def safe_score(value: float | None) -> float:
    return 0.5 if value is None else max(0.0, min(1.0, value))


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))
