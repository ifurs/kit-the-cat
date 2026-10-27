## What

<!-- events / sprites / engine / balance / UI — and why -->

## Checks

- [ ] `uv run ruff check src scripts tests web` and `uv run pytest -q`
- [ ] content: `python -m kit_the_cat.content.validate`, `scripts/content_stats.py --strict`, `scripts/gen_dsl_docs.py --check`
- [ ] balance: `scripts/balance.py` has no new FAIL (paste the metrics if engine numbers changed)
- [ ] sprites: `scripts/preview.py --smoke`; screenshot of new art
- [ ] UI: both `sandbox/static/index.html` and `web/index.html`; checked at 375 px (`scripts/ui_audit.js`)
- [ ] text is Ukrainian without russisms and follows [CONTENT_GUIDE §3](../docs/CONTENT_GUIDE.md)
- [ ] CHANGELOG.md → Unreleased
