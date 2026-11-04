"""Icon freshness is lossless content equality, independent of PNG compression."""
import io

from PIL import Image

from scripts.check_icon_freshness import same_content
from scripts.windows_product_icons import windows_product_icon


def test_png_compression_may_change_but_pixels_must_match(tmp_path):
    original = tmp_path / "original.png"
    generated = tmp_path / "generated.png"
    image = Image.new("RGBA", (32, 32), (10, 100, 200, 255))
    image.save(original, compress_level=0)
    image.save(generated, compress_level=9)
    assert original.read_bytes() != generated.read_bytes()
    assert same_content(original, generated)
    image.putpixel((0, 0), (11, 100, 200, 255))
    image.save(generated)
    assert not same_content(original, generated)


def test_container_frame_inventory_is_part_of_content(tmp_path):
    original = tmp_path / "original.ico"
    generated = tmp_path / "generated.ico"
    image = Image.new("RGBA", (64, 64), (10, 100, 200, 255))
    image.save(original, sizes=[(16, 16), (32, 32), (64, 64)])
    image.save(generated, sizes=[(16, 16), (32, 32), (64, 64)])
    assert same_content(original, generated)
    image.save(generated, sizes=[(32, 32), (64, 64)])
    assert not same_content(original, generated)


def test_windows_product_outputs_follow_the_canonical_artwork(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    master = Image.new("RGBA", (512, 512), (120, 10, 210, 255))
    master.putpixel((0, 0), (0, 0, 0, 0))
    master.save(assets / "actelyo-law-windows.png")
    master.save(assets / "actelyo-law-windows.ico", sizes=[(16, 16), (32, 32), (256, 256)])
    output = windows_product_icon(tmp_path, "apps/desktop/assets/icon.png")
    with Image.open(io.BytesIO(output)) as image:
        expected = master.resize((1024, 1024), Image.Resampling.LANCZOS)
        assert image.size == expected.size
        assert image.convert("RGBA").tobytes() == expected.tobytes()
    assert windows_product_icon(tmp_path, "apps/desktop/assets/icon.ico") == (assets / "actelyo-law-windows.ico").read_bytes()
    assert windows_product_icon(tmp_path, "website/static/img/favicon.ico") is None
