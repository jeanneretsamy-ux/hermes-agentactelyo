"""Canonical Actelyo product artwork on Windows and shared desktop surfaces."""
import io
from pathlib import Path

from PIL import Image

WINDOWS_PRODUCT_ICONS = frozenset({
    "apps/desktop/assets/icon.png", "apps/desktop/assets/icon.ico",
    "apps/desktop/public/apple-touch-icon.png", "apps/desktop/public/actelyo-logo.png",
})


def windows_product_icon(source: Path, relative: str) -> bytes | None:
    if relative not in WINDOWS_PRODUCT_ICONS:
        return None
    if relative.endswith(".ico"):
        return (source / "assets/actelyo-law-windows.ico").read_bytes()
    with Image.open(source / "assets/actelyo-law-windows.png") as image:
        size = 512 if relative.endswith("/actelyo-logo.png") else 1024
        canvas = image.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        canvas.save(output, "PNG")
        return output.getvalue()
