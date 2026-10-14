"""Compare generated icon content across hosts, including every container frame.

Pillow wheels can use different PNG compressors on Windows and Linux. Encoded
bytes need not match, but dimensions, frame sets and decoded pixels must.
SVG and JSON outputs still require byte equality.
"""
from pathlib import Path
import tempfile

from PIL import Image

from scripts.generate_icons import TARGETS, cmd_check, cmd_write


def image_frames(path: Path) -> dict:
    with Image.open(path) as image:
        if image.format == "ICO":
            return {size: image.ico.getimage(size).convert("RGBA").tobytes()
                    for size in image.ico.sizes()}
        if image.format == "ICNS":
            return {size: image.icns.getimage(size).convert("RGBA").tobytes()
                    for size in image.info["sizes"]}
        return {(image.format, image.size): image.convert("RGBA").tobytes()}


def same_content(committed: Path, generated: Path) -> bool:
    if committed.suffix.lower() in {".png", ".ico", ".icns"}:
        return image_frames(committed) == image_frames(generated)
    return committed.read_bytes() == generated.read_bytes()


def main() -> int:
    source = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="actelyo-icon-check-") as directory:
        generated = Path(directory)
        if cmd_write(source, generated) or cmd_check(source, generated):
            return 1
        stale = []
        for relative, _, _ in TARGETS:
            try:
                matches = same_content(source / relative, generated / relative)
            except (OSError, ValueError):
                matches = False
            if not matches:
                stale.append(relative)
        if stale:
            print("Stale icon content (regenerate and commit):\n" + "\n".join(stale))
            return 1
        print(f"[ok] all {len(TARGETS)} committed icons match generated content")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
