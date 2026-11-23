# Releasing

Releases come from CI, not from tags pushed by hand. A release is **one merged PR that bumps `version` in
`pyproject.toml`**; `.github/workflows/release.yml` does the rest on the merged commit. Same design as dexus-vault.

```
bump PR (version + uv.lock + CHANGELOG section + README pin)
   └─ merge into main
        └─ release.yml
             plan            version has no tag? commit is a merged PR? CHANGELOG section and README pin present?
             checks          the whole ci.yml suite (workflow_call) on the merged commit
             build           uv build (sdist + wheel, SOURCE_DATE_EPOCH = commit time, no cache), wheel import smoke,
                             scripts/deploy_pages.py --dry-run → build/site/ → Pages artifact
             github-release  build-provenance attestation, tag vX.Y.Z on the tested commit, GitHub Release + files
             pages           actions/deploy-pages
             publish-to-pypi disabled (see below)
   └─ koshenyat's Dependabot opens the pin-bump PR
```

## Cutting a release

1. Gate locally (the `kit-release` skill lists the commands); CI runs the same suite again before tagging.
2. On a branch `release/vX.Y.Z`:
   - `pyproject.toml` → `version = "X.Y.Z"`, then `uv lock` (only this package's version line changes);
   - `CHANGELOG.md`: move the Unreleased items under `## [X.Y.Z] — YYYY-MM-DD`, keep an empty `## [Unreleased]`,
     add the compare link at the bottom;
   - README install line → `--tag vX.Y.Z`.
   `python scripts/release_meta.py notes X.Y.Z` and `… check X.Y.Z` must pass (the `plan` job runs them).
3. Open the PR, let `ci` pass, merge. Watch the `release` run; the summary links the Release.
4. Verify Pages (https://ifurs.github.io/kit-the-cat/) with the kit-playtest phone audit.

Failed run: fix the cause, then **re-run the failed jobs** of the same run — they reuse the built files, so the
Release and Pages always carry what was tested. A version that is already tagged is never released again; a broken
release gets a new patch version. There is no `workflow_dispatch` on purpose (a manual run could release another
branch). A direct push to main that bumps the version fails the `plan` job.

Verify a downloaded file: `gh attestation verify kit_the_cat-X.Y.Z-py3-none-any.whl --repo ifurs/kit-the-cat`.

## One-time setup (repo settings — not done yet)

- **Pages source → GitHub Actions.** Today Pages serves the `gh-pages` branch (`build_type: legacy`), which the
  `pages` job cannot deploy to. Switch once: Settings → Pages → Source: *GitHub Actions*, or
  `gh api -X PUT repos/ifurs/kit-the-cat/pages -f build_type=workflow`. After that `deploy_pages.py` without
  `--dry-run` is obsolete and the `gh-pages` branch can be deleted. Until then the release still tags and publishes;
  only the `pages` job fails.
- **Environment `github-pages`:** created by the switch; restrict deployment branches to `main`.
- **Tag ruleset:** Settings → Rules → new tag ruleset for `v*`: restrict creation, update and deletion; bypass:
  *GitHub Actions* only (or the repo admin as an emergency). Then only `release.yml` can create release tags, and
  nobody can move one (koshenyat's lock pins the commit hash, but other hosts may trust the tag).
- **Branch protection on main:** require the `ci / test` check and a PR (the `plan` job also refuses non-PR commits).

## PyPI (Trusted Publishing, disabled)

The `publish-to-pypi` job runs only when the repo variable `PYPI_PUBLISH` is `true`. It uses OIDC Trusted Publishing:
no PyPI token is stored anywhere. To enable:

1. Check the name is free: https://pypi.org/project/kit-the-cat/ (404 = free).
2. On PyPI: Account → Publishing → *Add a new pending publisher*: owner `ifurs`, repository `kit-the-cat`,
   workflow `release.yml`, environment `pypi`. (The binding is to this file name — don't rename the workflow.)
3. On GitHub: Settings → Environments → new `pypi`; deployment branches: `main` only; optionally a required
   reviewer, so every upload waits for a click.
4. Settings → Variables → Actions → `PYPI_PUBLISH` = `true`.
5. The next release uploads the same files that went into the GitHub Release (`skip-existing` makes re-runs safe).
   To publish an already-released version, re-run its `publish-to-pypi` job after steps 1–4.

Then hosts can depend on `kit-the-cat[images]>=X.Y` from PyPI instead of a git tag.

## Downstream: the bot's pin

koshenyat pins `kit-the-cat = { git = …, tag = "vX.Y.Z" }` in `[tool.uv.sources]`. Its Dependabot (`uv` ecosystem,
group `kit`, no cooldown) sees the new tag at its weekly run and opens a PR that bumps the tag and `uv.lock`; the
bot's CI and its `kit-bump` skill checks (tests, `scripts/simulate.py`) then decide. For an immediate PR: koshenyat
→ Insights → Dependency graph → Dependabot → *Check for updates*.

Why not `repository_dispatch` from here: it would need a token with write access to the private bot repo stored
in this **public** repo's secrets. Dependabot needs no cross-repo credential, so it stays the only link.
