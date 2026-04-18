from __future__ import annotations

from .database import PhotoDatabase
from .models import DuplicateGroup, DuplicateItem


def find_exact_duplicate_groups(
    database: PhotoDatabase,
    library_root: str | None = None,
    paths: set[str] | None = None,
) -> list[DuplicateGroup]:
    groups: list[DuplicateGroup] = []
    for sha256 in database.duplicate_hashes(library_root=library_root, paths=paths):
        items = tuple(database.duplicate_items_for_hash(sha256, library_root=library_root, paths=paths))
        if len(items) > 1:
            groups.append(DuplicateGroup(group_key=sha256, items=items))
    return groups


def find_similar_photo_groups(
    database: PhotoDatabase,
    max_distance: int = 6,
    library_root: str | None = None,
    paths: set[str] | None = None,
) -> list[DuplicateGroup]:
    photos = database.photos_with_perceptual_hash(library_root=library_root, paths=paths)
    groups: list[DuplicateGroup] = []
    used_ids: set[int] = set()

    for photo in photos:
        if photo.id is None or photo.id in used_ids or not photo.perceptual_hash:
            continue
        matches = [photo]
        for candidate in photos:
            if (
                candidate.id is None
                or candidate.id == photo.id
                or candidate.id in used_ids
                or not candidate.perceptual_hash
                or candidate.sha256 == photo.sha256
            ):
                continue
            distance = hamming_distance(photo.perceptual_hash, candidate.perceptual_hash)
            if distance <= max_distance:
                matches.append(candidate)

        if len(matches) < 2:
            continue

        matches.sort(key=lambda item: (-item.file_size, item.modified_at, item.path))
        matches.sort(key=photo_rank_key)
        used_ids.update(item.id for item in matches if item.id is not None)
        items = tuple(
            DuplicateItem(
                photo_id=int(item.id),
                library_root=item.library_root,
                path=item.path,
                filename=item.filename,
                file_size=item.file_size,
                modified_at=item.modified_at,
                sha256=item.sha256,
                quality_score=item.quality_score,
                sharpness_score=item.sharpness_score,
                lighting_score=item.lighting_score,
                composition_score=item.composition_score,
                expression_score=item.expression_score,
                people_score=item.people_score,
                scenery_score=item.scenery_score,
                face_count=item.face_count,
                user_rating=item.user_rating,
                suggested_action="keep" if index == 0 else "review",
            )
            for index, item in enumerate(matches)
        )
        groups.append(DuplicateGroup(group_key=photo.perceptual_hash, items=items))

    return groups


def hamming_distance(left: str, right: str) -> int:
    left_value = int(left, 16)
    right_value = int(right, 16)
    return (left_value ^ right_value).bit_count()


def photo_rank_key(photo) -> tuple[float, int, float, str]:
    quality = photo.quality_score if photo.quality_score is not None else 0
    if photo.user_rating == 1:
        quality += 0.5
    elif photo.user_rating == 0:
        quality *= 0.75
    elif photo.user_rating == -1:
        quality = -1
    return (-quality, -photo.file_size, photo.modified_at, photo.path)
