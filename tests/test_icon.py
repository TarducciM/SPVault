"""Icona dell'app: file in assets\\ (disegnati da assets\\make_icon.py), icona della finestra, autotest."""
import struct
from pathlib import Path

import spvault as spb
from conftest import self_test

ASSETS = Path(__file__).resolve().parents[1] / "assets"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def ico_frames(path: Path) -> dict[int, bytes]:
    """Immagini del file .ico per dimensione (lato in pixel)."""
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)  # 1 = icona (2 sarebbe un cursore)
    frames = {}
    for i in range(count):
        width, height, _, _, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        assert width == height and (planes, bits) == (1, 32)
        assert offset + size <= len(data)
        frames[width or 256] = data[offset:offset + size]  # 0 = 256
    return frames


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == PNG_MAGIC and data[12:16] == b"IHDR"
    return struct.unpack_from(">II", data, 16)


def test_ico_has_the_sizes_used_by_windows():
    frames = ico_frames(ASSETS / "spvault.ico")
    assert {16, 20, 24, 32, 40, 48, 64, 128, 256} <= set(frames)
    for side, frame in frames.items():
        if frame.startswith(PNG_MAGIC):
            assert png_size(frame) == (side, side)
        else:  # BMP a 32 bit: altezza doppia (immagine + maschera)
            assert struct.unpack_from("<IiiHH", frame) == (40, side, side * 2, 1, 32)


def test_window_icon_and_social_preview_are_there():
    assert png_size((ASSETS / "spvault.png").read_bytes()) == (256, 256)
    assert png_size((ASSETS / "social-preview.png").read_bytes()) == (1280, 640)
    assert (ASSETS / "app-icon.svg").is_file() and (ASSETS / "social-preview.svg").is_file()


def test_icon_files_are_read_from_the_repository_assets():
    assert [spb.asset_path(name) for name in spb.ICON_FILES] == [ASSETS / name for name in spb.ICON_FILES]


def test_window_gets_the_icon(root):
    assert spb.set_window_icon(root)


def test_missing_icon_is_not_an_error(root, monkeypatch, tmp_path):
    monkeypatch.setattr(spb, "asset_path", lambda name: tmp_path / name)
    assert spb.set_window_icon(root) is False


def test_self_test_fails_without_the_icon(monkeypatch, tmp_path):
    # con l'icona al suo posto self_test() dà 0: test_gui.py::test_self_test_passes
    monkeypatch.setattr(spb, "asset_path", lambda name: tmp_path / name)  # exe compilato senza icona
    assert self_test() == 1
