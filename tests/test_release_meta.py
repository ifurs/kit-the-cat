"""scripts/release_meta.py — what the release workflow (.github/workflows/release.yml) reads before it tags."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import release_meta as rm  # noqa: E402

CHANGELOG = """# Changelog

## [Unreleased]

## [1.2.0] — 2026-12-01

### Added
- Нова подія.

## [1.1.0] — 2026-11-01

### Fixed
- Стара правка.

[1.2.0]: https://github.com/ifurs/kit-the-cat/compare/v1.1.0...v1.2.0
"""


def _repo(tmp_path: Path, version: str = "1.2.0", changelog: str = CHANGELOG, readme: str = "") -> Path:
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "kit-the-cat"\nversion = "{version}"\n')
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    (tmp_path / "README.md").write_text(readme or f'uv add "kit-the-cat @ git+https://x" --tag v{version}\n'
                                                  f"git+https://github.com/ifurs/kit-the-cat@v{version}\n")
    return tmp_path


def test_repo_metadata_is_consistent():
    """The real repo: the current version has a CHANGELOG section and the README pins it."""
    v = rm.version()
    assert rm.notes(v)
    rm.check(v)


def test_version_must_be_plain_semver(tmp_path):
    assert rm.version(_repo(tmp_path)) == "1.2.0"
    with pytest.raises(SystemExit):
        rm.version(_repo(tmp_path, version="1.2.0rc1"))


def test_notes_take_one_section_and_link_the_diff(tmp_path):
    body = rm.notes("1.2.0", _repo(tmp_path))
    assert "Нова подія" in body and "Стара правка" not in body
    assert body.endswith("compare/v1.1.0...v1.2.0")
    assert "compare" not in rm.notes("1.1.0", tmp_path)  # oldest entry: nothing to compare with
    assert "[1.2.0]:" not in rm.notes("1.1.0", tmp_path)  # link references are not part of the section


def test_missing_or_empty_section_stops_the_release(tmp_path):
    with pytest.raises(SystemExit, match="no entries"):
        rm.notes("1.3.0", _repo(tmp_path))
    with pytest.raises(SystemExit, match="no entries"):
        rm.notes("1.3.0", _repo(tmp_path, changelog="## [1.3.0] — 2026-12-02\n\n## [1.2.0] — x\n- a\n"))


def test_readme_must_pin_the_new_tag(tmp_path):
    rm.check("1.2.0", _repo(tmp_path))
    with pytest.raises(SystemExit, match="README"):
        rm.check("1.2.0", _repo(tmp_path, readme="git+https://github.com/ifurs/kit-the-cat@v1.1.0\n"))
