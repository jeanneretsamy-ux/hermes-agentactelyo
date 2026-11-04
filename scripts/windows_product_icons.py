"""Canonical Actelyo Windows artwork, independent of development build flavors."""
import io
from pathlib import Path

from PIL import Image

WINDOWS_PRODUCT_ICONS = frozenset({
    "apps/desktop/assets/icon.png", "apps/desktop/assets/icon.ico",
})


def windows_product_icon(source: Path, relative: str) -> bytes | None:
    if relative not in WINDOWS_PRODUCT_ICONS:
        return None
    if relative.endswith(".ico"):
        return (source / "assets/actelyo-law-windows.ico").read_bytes()
    with Image.open(source / "assets/actelyo-law-windows.png") as image:
        canvas = image.convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        canvas.save(output, "PNG")
        return output.getvalue()
