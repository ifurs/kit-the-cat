---
name: kit-release
description: Release a new version of the kit-the-cat package the CI way — run all checks, open a version-bump PR (pyproject version, uv.lock, CHANGELOG section, README pin); when that PR is merged, CI (.github/workflows/release.yml) tags, creates the GitHub Release and deploys Pages; then verify Pages live and check the bot's Dependabot pin-bump PR (private koshenyat repo). Use whenever the user says release, ship, publish, tag, deploy, "випусти версію", "bump the version", "update the bot to the new game", or wants game changes to reach the bot or the public site.
---

# Releasing kit-the-cat

The repo is **public**; the bot that depends on it is **private**. Releases come from CI on a merged version-bump
PR (docs/RELEASING.md) — **never push a tag or run `deploy_pages.py` without `--dry-run` by hand**. Pushing a
branch and opening a PR publish things: get the user's go-ahead for the version number first if they haven't said
"release" explicitly, and push only on their word.

## 1. Gate (all green, or stop and report)

```bash
uv run ruff check src scripts tests web
uv run pytest -q
uv run python -m kit_the_cat.content.validate
uv run python scripts/gen_dsl_docs.py --check
uv run python scripts/content_stats.py --strict
uv run python scripts/ua_lint.py --strict
uv run python scripts/balance.py
uv run python scripts/preview.py --smoke
uv run python scripts/deploy_pages.py --dry-run      # the Pages site CI will publish assembles
git status --short        # nothing unexpected; no play.json, build/, secrets
```

Scan the diff since the last tag for anything that must not go public (tokens, chat ids, real names, private bot
code): `git diff $(git describe --tags --abbrev=0)..HEAD` and `gitleaks detect --no-banner --redact`.

## 2. Version-bump PR

Pick per CONTRIBUTING.md#versioning: content/fixes → patch; new DSL keys/API/stored fields → minor; breaking → major.
On a branch `release/vX.Y.Z`:
- `pyproject.toml` → `version = "X.Y.Z"`, then `uv lock` (only the package's own version should change).
- `CHANGELOG.md`: move Unreleased items under `## [X.Y.Z] — <today>`, keep an empty Unreleased, add the compare link
  at the bottom.
- README's install line → `--tag vX.Y.Z`.
- Prove what CI's `plan` job will check:
  `python scripts/release_meta.py version && python scripts/release_meta.py notes X.Y.Z && python scripts/release_meta.py check X.Y.Z`

Commit `X.Y.Z: <one-line summary>` (end with the session's attribution line). Push and open the PR only when the
user said so (pr-flow skill). Nothing is tagged until the PR is merged.

## 3. After the merge (CI does it)

`release.yml` runs: plan → full `ci.yml` suite → build (sdist + wheel + Pages site) → tag `vX.Y.Z` + GitHub Release
with files and a provenance attestation → Pages deploy. PyPI is a disabled job (docs/RELEASING.md § PyPI).
- Watch it: `gh run list --workflow release.yml -L 1`, then `gh run view <id>`; never poll in a loop.
- Check the result: `gh release view vX.Y.Z`, and the live site (https://ifurs.github.io/kit-the-cat/, may take a
  minute) with the kit-playtest skill's phone audit: page loads, a pet hatches, no console errors.
- A failed job: fix the cause and re-run the failed jobs of that run (same files). Never hand-tag to "finish" a
  release. If `pages` fails with a Pages source error, the one-time switch in docs/RELEASING.md is not done yet.

## 4. The bot's pin

koshenyat's Dependabot opens "Bump kit-the-cat to vX.Y.Z" (group `kit`) at its next weekly run; for an immediate PR,
Insights → Dependency graph → Dependabot → Check for updates in koshenyat. Then, in `../koshenyat`, follow its
`kit-bump` skill on that PR's branch: tests, `scripts/simulate.py`, the API call sites in `handlers/pet.py` if the
public API changed (docs/INTEGRATION.md). Push fixes / merge only on the user's word.

## 5. Report

Version, changelog summary, PR + release run + Release links, Pages status, the bot's Dependabot PR and its check
results. Mention anything skipped or still manual (e.g. the Pages source switch).
