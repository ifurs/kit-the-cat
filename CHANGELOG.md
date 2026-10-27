# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/), versions: [SemVer](https://semver.org/) — see
[CONTRIBUTING.md](CONTRIBUTING.md#versioning). Hosts pin a tag; read this before bumping.

## [Unreleased]

### Added
- Developer tooling: `scripts/balance.py` (headless neighbourhood simulation with balance targets),
  `scripts/content_stats.py` (content map, gaps, dead-end chains, hard checks), `scripts/gen_dsl_docs.py`
  (`docs/DSL.md` generated from code), `scripts/ui_audit.js` (mobile layout audit).
- Docs: `docs/CONTENT_GUIDE.md` (how to write events — Ukrainian reality, language, boundaries, balance),
  `docs/ARCHITECTURE.md`, `docs/INTEGRATION.md`, `CONTRIBUTING.md`.
- Claude Code skills (`.claude/skills/`) for writing events, sprites, balance, playtesting and releases, and a
  content-review agent; GitHub issue/PR templates; CI checks for generated docs and content.
- `unequip` and `noedu` are now documented in the DSL reference.

## [0.1.1] — 2026-10-27

### Fixed
- Sandbox on phones: no horizontal overflow, popups stay on screen, larger touch targets, wrapping rows, 2×2 tabs.
- Tournaments with byes no longer stall; hidden browser tabs no longer freeze animation waits.

## [0.1.0] — 2026-10-27

### Added
- The «Кошеня» pet life-sim as a standalone package: engine, 313 events / 1134 choices in the DSL, 6 species,
  procedural sprites with a chat-unique genome, 8 roles, jobs and economy, battles and tournaments, `MemoryStore`,
  sandbox (aiohttp server and Pyodide browser build on GitHub Pages).

[Unreleased]: https://github.com/ifurs/kit-the-cat/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/ifurs/kit-the-cat/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ifurs/kit-the-cat/releases/tag/v0.1.0
