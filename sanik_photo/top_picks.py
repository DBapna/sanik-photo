from __future__ import annotations

from .database import PhotoDatabase
from .duplicate_finder import find_similar_photo_groups
from .models import PhotoRecord


DEFAULT_PICK_COUNT = 15


def select_top_picks(
    database: PhotoDatabase,
    count: int = DEFAULT_PICK_COUNT,
    library_root: str | None = None,
    paths: set[str] | None = None,
) -> list[PhotoRecord]:
    photos = database.list_photos(limit=1_000_000, library_root=library_root, paths=paths)
    photos_by_id = {photo.id: photo for photo in photos if photo.id is not None}

    selected: list[PhotoRecord] = []
    selected_ids: set[int] = set()
    grouped_ids: set[int] = set()

    for group in find_similar_photo_groups(database, library_root=library_root, paths=paths):
        group_ids = [item.photo_id for item in group.items]
        grouped_ids.update(group_ids)
        standout = photos_by_id.get(group.items[0].photo_id)
        if standout is not None:
            selected.append(standout)
            selected_ids.add(group.items[0].photo_id)

    remaining = [
        photo
        for photo in photos
        if photo.id is not None and photo.id not in selected_ids and photo.id not in grouped_ids
    ]
    selected.extend(sorted(remaining, key=photo_rank_key))

    return sorted(selected, key=photo_rank_key)[:count]


def photo_rank_key(photo: PhotoRecord) -> tuple[float, int, float, str]:
    quality = adjusted_quality(photo)
    return (-quality, -photo.file_size, photo.modified_at, photo.path)


def adjusted_quality(photo: PhotoRecord) -> float:
    quality = photo.quality_score if photo.quality_score is not None else 0.0
    if photo.user_rating == 1:
        return min(1.5, quality + 0.5)
    if photo.user_rating == 0:
        return max(0.05, quality * 0.75)
    if photo.user_rating == -1:
        return -1.0
    return quality
