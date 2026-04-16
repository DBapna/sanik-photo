from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import PhotoRecord


def caption_for_photo(photo: PhotoRecord, people: list[str]) -> str:
    parts: list[str] = []
    when = datetime.fromtimestamp(photo.modified_at).strftime("%B %d, %Y")
    parts.append(f"Photo from {when}")

    if people:
        parts.append("with " + join_names(people))

    quality_bits: list[str] = []
    if photo.quality_score is not None and photo.quality_score >= 0.7:
        quality_bits.append("standout candidate")
    if photo.sharpness_score is not None and photo.sharpness_score >= 0.7:
        quality_bits.append("sharp")
    if photo.lighting_score is not None and photo.lighting_score >= 0.7:
        quality_bits.append("well lit")
    if quality_bits:
        parts.append("(" + ", ".join(quality_bits) + ")")

    return " ".join(parts) + "."


def suggested_organization_path(photo: PhotoRecord, people: list[str]) -> str:
    taken = datetime.fromtimestamp(photo.modified_at)
    year = taken.strftime("%Y")
    month = taken.strftime("%m-%B")
    people_part = "People-" + "-".join(slugify(name) for name in people[:3]) if people else "People-Untagged"
    event = event_from_folder(photo)
    return str(Path(year) / month / people_part / event / photo.filename)


def event_from_folder(photo: PhotoRecord) -> str:
    path = Path(photo.path)
    parent = path.parent.name.strip()
    root = Path(photo.library_root).name.strip()
    if parent and parent != root:
        return slugify(parent)
    return "Event-Unsorted"


def join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def slugify(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "-" for char in value.strip())
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed or "Unsorted"

