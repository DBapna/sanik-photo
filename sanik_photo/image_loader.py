from __future__ import annotations

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from pillow_heif import register_heif_opener
except ImportError:
    register_heif_opener = None


def register_image_openers() -> None:
    if Image is None or register_heif_opener is None:
        return
    register_heif_opener()
