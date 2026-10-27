"""Publish the in-browser sandbox to GitHub Pages from this repo's `gh-pages` branch.

    uv run python scripts/deploy_pages.py --dry-run  # only assemble build/site/ (no git, no network)
    uv run python scripts/deploy_pages.py            # build → commit to gh-pages → push

Turn Pages on once (repo Settings → Pages → branch gh-pages / root, or):
    gh api -X POST repos/<owner>/kit-the-cat/pages -f "source[branch]=gh-pages" -f "source[path]=/"
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_web  # noqa: E402

BRANCH = "gh-pages"
SITE_DIR = ROOT / "build" / "site"     # assembled site
DIR = ROOT / "build" / "pages"         # checkout of the gh-pages branch


def sh(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    return subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=True).stdout.strip()


def assemble() -> None:
    sys.argv = [sys.argv[0]]
    build_web.main()
    out = build_web.OUT
    shutil.rmtree(SITE_DIR, ignore_errors=True)
    SITE_DIR.mkdir(parents=True)
    shutil.copy2(out / "preview.html", SITE_DIR / "index.html")  # standalone page (doctype + head) for a normal host
    shutil.copytree(out / "pyodide", SITE_DIR / "pyodide")
    (SITE_DIR / ".nojekyll").write_text("")
    (SITE_DIR / "README.md").write_text(
        "Built site of kit-the-cat: the pet sandbox running in the browser (Pyodide).\n\n"
        f"`pyodide/` is the unmodified npm package pyodide@{build_web.PYODIDE} (MPL-2.0, "
        "https://github.com/pyodide/pyodide).\n")


def main() -> None:
    dry = "--dry-run" in sys.argv
    assemble()
    if dry:
        print("assembled", SITE_DIR, "(dry run: nothing pushed)")
        return
    origin = sh("git", "remote", "get-url", "origin")
    if not (DIR / ".git").exists():
        shutil.rmtree(DIR, ignore_errors=True)
        cloned = subprocess.run(["git", "clone", "-q", "--branch", BRANCH, "--single-branch", origin, str(DIR)],
                                text=True, capture_output=True)
        if cloned.returncode:  # first deploy: no gh-pages branch yet
            DIR.mkdir(parents=True)
            sh("git", "init", "-q", cwd=DIR)
            sh("git", "checkout", "-q", "--orphan", BRANCH, cwd=DIR)
            sh("git", "remote", "add", "origin", origin, cwd=DIR)
        for key in ("user.name", "user.email"):  # same author as the source repo
            val = sh("git", "config", key, check=False)
            if val:
                sh("git", "config", key, val, cwd=DIR)
    for p in DIR.iterdir():
        if p.name != ".git":
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    shutil.copytree(SITE_DIR, DIR, dirs_exist_ok=True)
    sh("git", "add", "-A", cwd=DIR)
    if not sh("git", "status", "--porcelain", cwd=DIR):
        print("nothing changed")
        return
    sh("git", "commit", "-q", "-m", f"Build from {sh('git', 'rev-parse', '--short', 'HEAD')}", cwd=DIR)
    sh("git", "push", "-q", "origin", f"HEAD:{BRANCH}", cwd=DIR)
    print("deployed to the gh-pages branch")


if __name__ == "__main__":
    main()
