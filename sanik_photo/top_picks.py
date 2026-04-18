from __future__ import annotations

from .database import PhotoDatabase
from .duplicate_finder import find_similar_photo_groups
from .models import PhotoRecord
from .taste_model import blended_photo_score, load_taste_model


DEFAULT_PICK_COUNT = 15
DEFAULT_SCORE_THRESHOLD = 0.75
TOP_PICK_MODES = ("Balanced", "Happy People", "Amazing Scenery")


def select_top_picks(
    database: PhotoDatabase,
    count: int = DEFAULT_PICK_COUNT,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    mode: str = "Balanced",
    library_root: str | None = None,
    paths: set[str] | None = None,
) -> list[PhotoRecord]:
    photos = database.list_photos(limit=1_000_000, library_root=library_root, paths=paths)
    photos_by_id = {photo.id: photo for photo in photos if photo.id is not None}
    taste_model = load_taste_model(database)

    selected: list[PhotoRecord] = []
    selected_ids: set[int] = set()
    grouped_ids: set[int] = set()

    for group in find_similar_photo_groups(database, library_root=library_root, paths=paths):
        group_ids = [item.photo_id for item in group.items]
        grouped_ids.update(group_ids)
        candidates = [photos_by_id[photo_id] for photo_id in group_ids if photo_id in photos_by_id]
        if candidates:
            standout = sorted(candidates, key=lambda photo: photo_rank_key(photo, taste_model, mode))[0]
            selected.append(standout)
            if standout.id is not None:
                selected_ids.add(standout.id)

    remaining = [
        photo
        for photo in photos
        if photo.id is not None and photo.id not in selected_ids and photo.id not in grouped_ids
    ]
    selected.extend(sorted(remaining, key=lambda photo: photo_rank_key(photo, taste_model, mode)))

    ranked = sorted(selected, key=lambda photo: photo_rank_key(photo, taste_model, mode))
    required_ids = {photo.id for photo in ranked[:count]}
    threshold_ids = {
        photo.id
        for photo in ranked
        if adjusted_quality(photo, taste_model, mode) >= score_threshold
    }
    keep_ids = required_ids | threshold_ids
    return [photo for photo in ranked if photo.id in keep_ids]


def photo_rank_key(
    photo: PhotoRecord,
    taste_model: dict | None = None,
    mode: str = "Balanced",
) -> tuple[float, int, float, str]:
    quality = adjusted_quality(photo, taste_model, mode)
    return (-quality, -photo.file_size, photo.modified_at, photo.path)


def adjusted_quality(
    photo: PhotoRecord,
    taste_model: dict | None = None,
    mode: str = "Balanced",
) -> float:
    base = blended_photo_score(photo, taste_model)
    people = photo.people_score if photo.people_score is not None else 0.0
    scenery = photo.scenery_score if photo.scenery_score is not None else 0.0
    quality = photo.quality_score if photo.quality_score is not None else 0.0

    if photo.user_rating == -1:
        return -1.0
    if mode == "Happy People":
        score = (people * 0.48) + (base * 0.28) + (quality * 0.14) + (safe_score(photo.expression_score) * 0.10)
    elif mode == "Amazing Scenery":
        score = (scenery * 0.50) + (base * 0.25) + (quality * 0.15) + (safe_score(photo.composition_score) * 0.10)
    else:
        score = (max(people, scenery) * 0.35) + (base * 0.40) + (quality * 0.25)

    if photo.user_rating == 1:
        return min(1.5, score + 0.5)
    if photo.user_rating == 0:
        return max(0.05, score * 0.75)
    return score


def safe_score(score: float | None) -> float:
    return 0.0 if score is None else max(0.0, min(1.0, score))
