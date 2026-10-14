"""Icon freshness is lossless content equality, independent of PNG compression."""
from PIL import Image

from scripts.check_icon_freshness import same_content


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
