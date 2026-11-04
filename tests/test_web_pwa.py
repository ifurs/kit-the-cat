"""The browser build as an installable, offline app (GitHub Pages only) and the save file backup (both hosts)."""
import asyncio
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "web")]
import build_web  # noqa: E402


def test_cache_name_follows_the_build():
    a, b = build_web.stamp_sw("<p>one</p>"), build_web.stamp_sw("<p>two</p>")
    name = lambda sw: re.search(r'const CACHE = "(kit-[0-9a-f]{12})"', sw).group(1)  # noqa: E731
    assert name(a) != name(b) and name(a) == name(build_web.stamp_sw("<p>one</p>"))
    pre = json.loads(re.search(r"const PRECACHE = (\[.*?\]);", a).group(1))
    assert pre == ["./", "index.html", *build_web.STATIC, *(f"pyodide/{f}" for f in build_web.RUNTIME)]
    assert "__CACHE__" not in a and "__PRECACHE__" not in a


def test_static_pwa_files_exist_and_match_the_manifest():
    for f in build_web.STATIC:
        assert (build_web.WEB / f).is_file(), f
    man = json.loads((build_web.WEB / "manifest.webmanifest").read_text())
    assert man["lang"] == "uk" and man["display"] == "standalone" and man["start_url"] == "./"
    icons = {i["src"] for i in man["icons"]}
    assert icons <= set(build_web.STATIC) and any(i.get("purpose") == "maskable" for i in man["icons"])


def test_only_the_pages_wrapper_links_the_manifest():
    page = (ROOT / "web" / "index.html").read_text()
    assert 'rel="manifest"' not in page, "the Artifact page must not link a manifest"
    assert 'rel="manifest"' in build_web.standalone("x", pwa=True)
    assert 'rel="manifest"' not in build_web.standalone("x")
    guard = re.search(r'const PWA = "serviceWorker" in navigator && !window\.claude', page)
    assert guard, "service worker registration must be guarded against the Artifact host"
    assert page.count('serviceWorker.register(') == 1 and "skipWaiting" not in page


def test_deploy_precaches_only_files_the_site_has():
    if not all((build_web.CACHE / f).exists() for f in build_web.RUNTIME):
        pytest.skip("Pyodide runtime not downloaded (uv run python scripts/build_web.py)")
    import deploy_pages
    deploy_pages.assemble()
    site = deploy_pages.SITE_DIR
    sw = (site / "sw.js").read_text()
    for f in json.loads(re.search(r"const PRECACHE = (\[.*?\]);", sw).group(1)):
        assert f == "./" or (site / f).is_file(), f
    assert 'rel="manifest"' in (site / "index.html").read_text()


def test_save_file_restore_rejects_garbage_and_keeps_the_game():
    import bridge

    async def go():
        await bridge.boot("")
        await bridge.call("do", 1, json.dumps({"action": "npcs", "x": 2}))
        good = bridge.dump()
        assert json.loads(good)["pets"]
        for bad in ("", "nope", "{}", '{"v": 2}', json.dumps({"v": 1, "pets": [], "logs": [], "graves": [],
                                                                "chats": {}, "next_id": 1}),
                    json.dumps({"v": 1, "pets": {"x": {"oops": 1}}, "logs": [], "graves": [], "chats": {},
                                "next_id": 1}), "x" * (bridge.MAX_SAVE + 1)):
            assert not await bridge.restore(bad)
            assert bridge.dump() == good, "a broken file leaves the current game untouched"
        await bridge.boot("")
        empty = json.dumps({"v": 1, "pets": {}, "logs": [], "graves": [], "chats": {}, "next_id": 1})
        assert await bridge.restore(empty) and not json.loads(bridge.dump())["pets"]
        assert await bridge.restore(good) and bridge.dump() == good
        assert json.loads(await bridge.call("state", 1))
    asyncio.run(go())
