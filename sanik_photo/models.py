from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhotoRecord:
    id: int | None
    library_root: str
    path: str
    filename: str
    extension: str
    file_size: int
    modified_at: float
    sha256: str
    width: int | None = None
    height: int | None = None
    perceptual_hash: str | None = None
    sharpness_score: float | None = None
    lighting_score: float | None = None
    composition_score: float | None = None
    expression_score: float | None = None
    people_score: float | None = None
    scenery_score: float | None = None
    face_count: int | None = None
    quality_score: float | None = None
    user_rating: int | None = None
    is_deleted: bool = False


@dataclass(frozen=True)
class DuplicateItem:
    photo_id: int
    library_root: str
    path: str
    filename: str
    file_size: int
    modified_at: float
    sha256: str
    quality_score: float | None
    sharpness_score: float | None
    lighting_score: float | None
    composition_score: float | None
    expression_score: float | None
    people_score: float | None
    scenery_score: float | None
    face_count: int | None
    user_rating: int | None
    suggested_action: str


@dataclass(frozen=True)
class DuplicateGroup:
    group_key: str
    items: tuple[DuplicateItem, ...]
