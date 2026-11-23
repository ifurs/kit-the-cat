"""Release metadata for CI (.github/workflows/release.yml). Stdlib only.

    python scripts/release_meta.py version              # X.Y.Z from pyproject.toml (fails if not plain SemVer)
    python scripts/release_meta.py notes X.Y.Z          # that version's CHANGELOG.md section (fails if missing/empty)
    python scripts/release_meta.py check X.Y.Z          # the README install line points at vX.Y.Z

A release is "the version in pyproject.toml has no tag yet"; the PR that bumps it must also move the CHANGELOG
entries under `## [X.Y.Z] — <date>` and update the README pin, or the release job stops before tagging.
"""
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def version(root: Path = ROOT) -> str:
    v = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    if not SEMVER.match(v):
        raise SystemExit(f"version {v!r} is not X.Y.Z")
    return v


def notes(v: str, root: Path = ROOT) -> str:
    text = (root / "CHANGELOG.md").read_text()
    m = re.search(rf"^## \[{re.escape(v)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", text, re.M | re.S)
    if not m or not m.group(1).strip():
        raise SystemExit(f"CHANGELOG.md has no entries under ## [{v}] — move them out of Unreleased in the bump PR")
    body = m.group(1).strip()
    prev = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M)
    if v in prev and (i := prev.index(v)) + 1 < len(prev):
        body += f"\n\n**Full diff:** https://github.com/ifurs/kit-the-cat/compare/v{prev[i + 1]}...v{v}"
    return body


def check(v: str, root: Path = ROOT) -> None:
    if f"@v{v}" not in (root / "README.md").read_text() and f'"v{v}"' not in (root / "README.md").read_text():
        raise SystemExit(f"README.md install line does not mention v{v}")


def main(argv: list[str]) -> None:
    cmd, *args = argv or ["version"]
    if cmd == "version":
        print(version())
    elif cmd == "notes":
        print(notes(args[0]))
    elif cmd == "check":
        check(args[0])
        print("ok")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
