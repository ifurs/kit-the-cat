---
name: kit-release
description: Release a new version of the kit-the-cat package — run all checks, bump the version, update CHANGELOG, tag and push, deploy the browser build to GitHub Pages, verify it live, and bump the pin in the Telegram bot (private koshenyat repo). Use whenever the user says release, ship, publish, tag, deploy, "випусти версію", "bump the version", "update the bot to the new game", or wants game changes to reach the bot or the public site.
---

# Releasing kit-the-cat

The repo is **public**; the bot that depends on it is **private**. Pushing, tagging and deploying publish things —
get the user's go-ahead for the version number before tagging if they haven't said "release" explicitly.

## 1. Gate (all green, or stop and report)

```bash
uv run ruff check src scripts tests web
uv run pytest -q
uv run python -m kit_the_cat.content.validate
uv run python scripts/gen_dsl_docs.py --check
uv run python scripts/content_stats.py --strict
uv run python scripts/balance.py
uv run python scripts/preview.py --smoke
git status --short        # nothing unexpected; no play.json, build/, secrets
```

Scan the diff since the last tag for anything that must not go public (tokens, chat ids, real names, private bot
code): `git diff $(git describe --tags --abbrev=0)..HEAD`.

## 2. Version

Pick per CONTRIBUTING.md#versioning: content/fixes → patch; new DSL keys/API/stored fields → minor; breaking → major.
- `pyproject.toml` → `version = "X.Y.Z"`, then `uv lock` (only the package's own version should change).
- `CHANGELOG.md`: move Unreleased items under `## [X.Y.Z] — <today>`, keep an empty Unreleased, update the
  compare links at the bottom.
- README's install line → the new tag.

## 3. Tag, push, deploy

```bash
git add -A && git commit -m "X.Y.Z: <one-line summary>"     # end the message with the session's attribution line
git tag vX.Y.Z && git push && git push origin vX.Y.Z
uv run python scripts/deploy_pages.py                      # builds Pyodide site, pushes gh-pages
```

Verify the live site (https://ifurs.github.io/kit-the-cat/, may take a minute) with the kit-playtest skill's
phone audit: page loads, a pet hatches, no console errors.

## 4. Bump the bot

In `../koshenyat` (private): follow its `kit-bump` skill — change `rev` in `[tool.uv.sources]`, `uv lock`, run its
tests, `scripts/simulate.py`, commit "Bump kit-the-cat to vX.Y.Z", push. If the release changed the public API
(see docs/INTEGRATION.md), check `handlers/pet.py` call sites first.

## 5. Report

Version, changelog summary, tag/commit links, Pages status, bot commit. Mention anything skipped.
