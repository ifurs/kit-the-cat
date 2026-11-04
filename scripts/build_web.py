"""Build the in-browser pet sandbox (Pyodide) into build/web/.

    uv run python scripts/build_web.py            # downloads the Pyodide runtime once into .cache/
    uv run python scripts/build_web.py --tree     # also writes build/web-py/ to smoke-test the bundle natively

The page embeds the game's Python sources (the kit_the_cat package + web/bridge.py); the Pyodide runtime is
published next to it under pyodide/. Nothing else is fetched.
"""
import argparse
import hashlib
import io
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYODIDE = "314.0.7"
RUNTIME = ["pyodide.js", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
CACHE = ROOT / ".cache" / f"pyodide-{PYODIDE}"
OUT = ROOT / "build" / "web"
WEB = ROOT / "web"
# the PWA files of the GitHub Pages build (deploy_pages.py); the Artifact page never links them
STATIC = ["manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png"]
PWA_HEAD = ('<link rel="manifest" href="manifest.webmanifest"><meta name="theme-color" content="#1a1c2c">'
            '<link rel="apple-touch-icon" href="icons/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes">'
            '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Kit">')


def fetch_runtime() -> Path:
    if all((CACHE / f).exists() for f in RUNTIME):
        return CACHE
    url = f"https://registry.npmjs.org/pyodide/-/pyodide-{PYODIDE}.tgz"
    print("downloading", url)
    meta = json.load(urllib.request.urlopen(f"https://registry.npmjs.org/pyodide/{PYODIDE}"))
    data = urllib.request.urlopen(url).read()
    want = meta["dist"]["shasum"]
    if hashlib.sha1(data).hexdigest() != want:
        raise SystemExit("pyodide tarball checksum mismatch")
    CACHE.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for f in RUNTIME:
            member = tar.getmember(f"package/{f}")
            (CACHE / f).write_bytes(tar.extractfile(member).read())
    return CACHE


def sources() -> dict[str, str]:
    """path inside Pyodide's FS → source. The package needs no shims: Pillow is imported lazily and the time zone
    falls back to a built-in Kyiv rule when there's no tz database."""
    pkg = ROOT / "src" / "kit_the_cat"
    out: dict[str, str] = {}
    for p in sorted(pkg.rglob("*.py")):
        rel = p.relative_to(pkg)
        if p.name == "validate.py" or rel.parts[0] == "sandbox" and p.name == "server.py":
            continue  # dev tools / aiohttp server: not needed in the browser
        out[f"kit_the_cat/{rel}"] = p.read_text()
    out["bridge.py"] = (ROOT / "web" / "bridge.py").read_text()
    return out


def standalone(page: str, pwa: bool = False) -> str:
    """The page with the doctype/head a normal host needs (the Artifact host adds its own); `pwa` links the manifest
    and the icons (GitHub Pages only)."""
    return ('<!doctype html><html lang="uk"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            + (PWA_HEAD if pwa else "") + "</head><body>" + page + "</body></html>")


def precache() -> list[str]:
    """What sw.js stores for offline play, relative to the site root."""
    return ["./", "index.html", *STATIC, *(f"pyodide/{f}" for f in RUNTIME)]


def stamp_sw(page: str) -> str:
    """sw.js with its cache named after the build: a hash of the served page, the static files, the runtime list
    and the Pyodide version. Another build → another cache name → the old cache is dropped on activate."""
    h = hashlib.sha256(page.encode())
    for f in STATIC:
        h.update(f.encode() + (WEB / f).read_bytes())
    h.update(f"{PYODIDE}:{','.join(RUNTIME)}".encode())
    sw = (WEB / "sw.js").read_text()
    out = (sw.replace('"/*__CACHE__*/kit-dev"', json.dumps(f"kit-{h.hexdigest()[:12]}"))
             .replace('/*__PRECACHE__*/["./"]', json.dumps(precache())))
    if "__CACHE__" in out or "__PRECACHE__" in out:
        raise SystemExit("web/sw.js: the CACHE/PRECACHE placeholders changed, stamp_sw can't fill them")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", action="store_true", help="also write build/web-py/ for a native smoke test")
    ap.add_argument("--no-runtime", action="store_true", help="skip the Pyodide runtime (CI checks of the bundle)")
    a = ap.parse_args()
    srcs = sources()
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.no_runtime:
        runtime = fetch_runtime()
        (OUT / "pyodide").mkdir(exist_ok=True)
        for f in RUNTIME:
            shutil.copy2(runtime / f, OUT / "pyodide" / f)
    # "<" only occurs inside JSON strings: \u003c keeps "</script>" and "<!--" from ending the script element
    blob = json.dumps(srcs, ensure_ascii=False).replace("<", "\\u003c")
    page = (ROOT / "web" / "index.html").read_text().replace("/*__PY_SOURCES__*/{}", blob)
    (OUT / "index.html").write_text(page)  # published as-is: the Artifact host adds doctype/head/body
    (OUT / "preview.html").write_text(standalone(page))  # local preview needs the wrapper the host would add
    if a.tree:
        tree = ROOT / "build" / "web-py"
        shutil.rmtree(tree, ignore_errors=True)
        for path, text in srcs.items():
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).write_text(text)
        print("wrote", tree)
    size = (OUT / "index.html").stat().st_size
    print(f"wrote {OUT}/index.html ({size / 1024:.0f} KB, {len(srcs)} python files)"
          + ("" if a.no_runtime else " + pyodide/ runtime"))


if __name__ == "__main__":
    main()
