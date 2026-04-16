from __future__ import annotations

import shutil
from pathlib import Path

from .database import PhotoDatabase
from .models import DuplicateGroup


def move_review_duplicates(
    database: PhotoDatabase,
    groups: list[DuplicateGroup],
    review_root: Path | str,
) -> int:
    review_root = Path(review_root).expanduser().resolve()
    review_root.mkdir(parents=True, exist_ok=True)

    moved = 0
    for group_index, group in enumerate(groups, start=1):
        group_dir = review_root / f"duplicate_group_{group_index:04d}"
        group_dir.mkdir(parents=True, exist_ok=True)
        for item in group.items:
            if item.suggested_action == "keep":
                continue
            source = Path(item.path)
            if not source.exists():
                database.log_file_action(item.photo_id, "missing_on_move", item.path)
                continue
            target = unique_target(group_dir / source.name)
            shutil.move(str(source), str(target))
            database.log_file_action(item.photo_id, "move_to_review", str(source), str(target))
            moved += 1
    return moved


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

