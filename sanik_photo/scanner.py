from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from pathlib import Path

from .models import PhotoRecord
from .quality import score_image

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
}

ProgressCallback = Callable[[str], None]


def scan_folder(folder: Path | str, progress: ProgressCallback | None = None) -> Iterator[PhotoRecord]:
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Folder does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {root}")

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if progress:
            progress(str(path))
        stat = path.stat()
        metadata = image_metadata(path)
        yield PhotoRecord(
            id=None,
            library_root=str(root),
            path=str(path),
            filename=path.name,
            extension=path.suffix.lower(),
            file_size=stat.st_size,
            modified_at=stat.st_mtime,
            sha256=sha256_file(path),
            width=metadata["width"],
            height=metadata["height"],
            perceptual_hash=metadata["perceptual_hash"],
            sharpness_score=metadata["sharpness_score"],
            lighting_score=metadata["lighting_score"],
            composition_score=metadata["composition_score"],
            expression_score=metadata["expression_score"],
            quality_score=metadata["quality_score"],
        )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_metadata(path: Path) -> dict[str, int | float | str | None]:
    empty: dict[str, int | float | str | None] = {
        "width": None,
        "height": None,
        "perceptual_hash": None,
        "sharpness_score": None,
        "lighting_score": None,
        "composition_score": None,
        "expression_score": None,
        "quality_score": None,
    }
    if Image is None or ImageOps is None:
        return empty
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            scores = score_image(image)
            return {
                "width": width,
                "height": height,
                "perceptual_hash": dhash(image),
                "sharpness_score": scores.sharpness,
                "lighting_score": scores.lighting,
                "composition_score": scores.composition,
                "expression_score": scores.expression,
                "quality_score": scores.overall,
            }
    except Exception:
        return empty


def dhash(image: "Image.Image", hash_size: int = 8) -> str:
    grayscale = image.convert("L").resize((hash_size + 1, hash_size))
    pixel_data = (
        grayscale.get_flattened_data()
        if hasattr(grayscale, "get_flattened_data")
        else grayscale.getdata()
    )
    pixels = list(pixel_data)
    bits: list[str] = []
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for column in range(hash_size):
            left = pixels[offset + column]
            right = pixels[offset + column + 1]
            bits.append("1" if left > right else "0")
    value = int("".join(bits), 2)
    return f"{value:0{hash_size * hash_size // 4}x}"
