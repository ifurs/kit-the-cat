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
    (OUT / "preview.html").write_text(  # local preview needs the wrapper the host would add
        '<!doctype html><html lang="uk"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>'
        + page + "</body></html>")
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
