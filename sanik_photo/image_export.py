from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from .file_actions import unique_target
from .image_loader import register_image_openers
from .models import PhotoRecord

register_image_openers()

def resize_photos(
    photos: list[PhotoRecord],
    output_dir: Path | str,
    max_width: int = 1920,
    max_height: int = 1080,
    quality: int = 85,
) -> int:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    copied = 0
    for photo in photos:
        source = Path(photo.path)
        if not source.exists():
            continue
        try:
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((max_width, max_height))
                target = unique_target(output / f"{source.stem}_resized.jpg")
                image.save(target, format="JPEG", quality=quality, optimize=True)
                copied += 1
        except Exception:
            continue
    return copied
