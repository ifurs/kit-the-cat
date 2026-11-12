"""Redrawable art (kit_the_cat.art + assets/): untouched files change nothing, a redrawn one is used, a broken one isn't."""
import importlib.util
import io
import logging
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from kit_the_cat import art, sprites as S, sprites_bg as B

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("art_cli", ROOT / "scripts" / "art.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


@pytest.fixture
def assets(tmp_path, monkeypatch):
    """An empty assets directory; `put` adds a picture to it as a redrawn file."""
    monkeypatch.setattr(art, "ROOT", tmp_path)
    (tmp_path / "manifest.json").write_text("{}")
    art.reload()
    B._bg_pixels.cache_clear()

    def put(rel: str, pic: Image.Image) -> None:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        pic.save(tmp_path / rel)
    yield put
    monkeypatch.undo()
    art.reload()
    B._bg_pixels.cache_clear()


def _frames(lk: S.Look) -> list[dict]:
    return [dict(c.px) for c in S.frame_canvases(lk, 4)]


def _solid(colour: tuple, w: int = 48, h: int = 48, box: tuple = (20, 0, 28, 8)) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    im.paste((*colour, 255), box)
    return im


@pytest.mark.parametrize("mode", ["RGBA", "RGB", "P", "L", "LA"])
def test_png_decoder_reads_what_editors_save(mode):
    src = Image.new("RGBA", (9, 5), (0, 0, 0, 255))
    src.paste((200, 200, 200, 255), (2, 1, 7, 4))
    buf = io.BytesIO()
    src.convert(mode).save(buf, "PNG")
    w, h, rgba = art.png_decode(buf.getvalue())
    assert (w, h, len(rgba)) == (9, 5, 180)
    grey = {rgba[i] for i in range(0, len(rgba), 4)}
    assert len(grey) == 2 and rgba[3] == 255
    i = (2 * 9 + 4) * 4
    assert rgba[i] == rgba[i + 1] == rgba[i + 2] == 200


def test_png_encoder_round_trips():
    rgba = bytes(range(256)) * 16
    assert art.png_decode(art.png_encode(32, 32, rgba))[2] == rgba


def test_every_asset_on_disk_matches_the_code():
    """Fails after a change in the sprite code: run `uv run python scripts/art.py export`."""
    assert cli.export(check=True) == 0


def test_untouched_files_are_not_used():
    """The scenes are redrawn pictures; everything else is still what the code draws, and those files are ignored."""
    redrawn = set(art.redrawn_files())
    assert art.manifest() and all(rel.startswith("backgrounds/") for rel in redrawn)
    untouched = [rel for rel in art.manifest() if rel not in redrawn]
    assert all(art.load(*rel[:-4].split("/", 1)) is None for rel in untouched[::7])


def test_a_picture_of_an_item_draws_the_same_as_the_code(monkeypatch):
    """The exported files really are what the game draws: forced on for the reference pet, nothing changes."""
    look = S.Look(stage=3)
    items = list(S.ITEMS)[::3]
    code = {i: _frames(replace(look, items=[i])) for i in items}
    monkeypatch.setattr(art, "manifest", lambda: {})
    art.load.cache_clear()
    try:
        assert all(art.load("items", i) for i in items)
        for i in items:
            assert _frames(replace(look, items=[i])) == code[i], i
    finally:
        monkeypatch.undo()
        art.load.cache_clear()


def test_a_picture_of_a_background_draws_the_same_as_the_code(assets):
    """What `art.py export` writes for a scene is what the code draws: put it back as a redrawn file, nothing changes."""
    look = S.Look(stage=3, background="kyiv")
    code = _frames(look)  # the assets directory is empty here: the code draws
    w, h, rgba = cli.fresh()["backgrounds/kyiv.png"]
    assets("backgrounds/kyiv.png", Image.frombytes("RGBA", (w, h), rgba))
    art.reload()
    B._bg_pixels.cache_clear()
    assert art.load("backgrounds", "kyiv") and _frames(look) == code


def test_redrawn_item_is_used_and_tinted(assets):
    red = (200, 30, 30)
    assets("items/crown.png", _solid(red))
    frames = _frames(S.Look(stage=3, items=["crown"]))
    assert all(red in fr.values() for fr in frames)
    tinted = _frames(S.Look(stage=3, items=["crown@6"]))
    assert red not in tinted[0].values()


def test_a_hat_follows_the_head_of_another_pet(assets):
    red = (200, 30, 30)
    box = (20, 4, 28, 8)  # sits just above the reference head (its top is y=8 in frame 0)
    assets("items/crown.png", _solid(red, box=box))
    def rows(lk):
        return sorted({y for (_, y), c in S.frame_canvases(lk, 1)[0].px.items() if c == red})
    grown, baby = rows(S.Look(stage=3, items=["crown"])), rows(S.Look(stage=1, items=["crown"]))
    assert grown[0] == 4 and baby[0] > grown[0]  # a baby's head is lower


def test_two_frames_of_animation_and_a_single_frame(assets):
    a, b = (200, 30, 30), (30, 200, 30)
    strip = Image.new("RGBA", (192, 48), (0, 0, 0, 0))
    for k, c in enumerate((a, b, a, b)):
        strip.paste((*c, 255), (k * 48 + 20, 0, k * 48 + 28, 8))
    assets("items/crown.png", strip)
    assets("items/cap.png", _solid(a))
    f = _frames(S.Look(stage=3, items=["crown"]))
    assert a in f[0].values() and a not in f[1].values() and b in f[1].values()
    still = _frames(S.Look(stage=3, items=["cap"]))
    assert a in still[0].values() and a in still[1].values()


def test_redrawn_ears_take_the_colours_of_the_pet(assets):
    look = S.Look(stage=3, genes=replace(S.REF.genes, ears="bunny", hue=0.6, sat=0.9, val=0.9))
    assets("ears/bunny.png", _solid(art.KEYS["base"], box=(18, 0, 30, 6)))
    base = S.palette(look.genes)[0]
    frame = _frames(look)[0]
    assert art.KEYS["base"] not in frame.values() and base in frame.values()


def test_a_redrawn_background_fills_and_a_wide_scene_mirrors_it(assets):
    pic = Image.new("RGB", (48, 48), (10, 20, 30))
    pic.paste((250, 0, 0), (0, 0, 4, 48))
    assets("backgrounds/kyiv.png", pic)
    B._bg_pixels.cache_clear()
    cv = S.Canvas(96, 48)
    B.paint_bg(cv, "kyiv", 0)
    assert cv.px[(1, 10)] == (250, 0, 0) and cv.px[(30, 10)] == (10, 20, 30) and cv.px[(94, 10)] == (250, 0, 0)
    B._bg_pixels.cache_clear()
    night = S.Canvas()
    B.paint_bg(night, "kyiv~night", 0)
    assert night.px[(30, 10)] != (10, 20, 30)  # modifiers still work on a picture


def test_a_broken_file_falls_back_to_the_code(assets, tmp_path, caplog):
    look = S.Look(stage=3, items=["crown"])
    assets("items/cap.png", _solid((1, 2, 3)))  # keeps the directory
    (tmp_path / "items" / "crown.png").write_bytes(b"this is not a png")
    with caplog.at_level(logging.WARNING, logger="kit_the_cat.art"):
        frames = _frames(look)
    assert frames and "art items/crown.png ignored" in caplog.text


def test_the_wrong_size_is_ignored(assets):
    assets("items/crown.png", Image.new("RGBA", (10, 10), (1, 2, 3, 255)))
    assert art.load("items", "crown") is None


def test_browser_bundle_holds_only_redrawn_pictures(assets, monkeypatch):
    import base64
    assets("items/crown.png", _solid((200, 30, 30)))
    data = (art.ROOT / "items" / "crown.png").read_bytes()
    assert art.redrawn_files() == ["items/crown.png"]
    monkeypatch.setattr(art, "BUNDLE", {"items/crown.png": base64.b64encode(data).decode()})
    art.load.cache_clear()
    assert art.load("items", "crown") and art.load("items", "cap") is None
    monkeypatch.setattr(art, "BUNDLE", None)
    art.load.cache_clear()
