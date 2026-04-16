from __future__ import annotations

from .database import PhotoDatabase
from .duplicate_finder import find_similar_photo_groups
from .models import PhotoRecord
from .taste_model import blended_photo_score, load_taste_model


DEFAULT_PICK_COUNT = 15


def select_top_picks(
    database: PhotoDatabase,
    count: int = DEFAULT_PICK_COUNT,
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
            standout = sorted(candidates, key=lambda photo: photo_rank_key(photo, taste_model))[0]
            selected.append(standout)
            if standout.id is not None:
                selected_ids.add(standout.id)

    remaining = [
        photo
        for photo in photos
        if photo.id is not None and photo.id not in selected_ids and photo.id not in grouped_ids
    ]
    selected.extend(sorted(remaining, key=lambda photo: photo_rank_key(photo, taste_model)))

    return sorted(selected, key=lambda photo: photo_rank_key(photo, taste_model))[:count]


def photo_rank_key(photo: PhotoRecord, taste_model: dict | None = None) -> tuple[float, int, float, str]:
    quality = adjusted_quality(photo, taste_model)
    return (-quality, -photo.file_size, photo.modified_at, photo.path)


def adjusted_quality(photo: PhotoRecord, taste_model: dict | None = None) -> float:
    return blended_photo_score(photo, taste_model)
