---
name: kit-event-writer
description: Write new life events (пригоди) for the Kit the Cat pet game in its DSL — funny Ukrainian-reality scenarios (ЦНАП, маршрутка, АТБ, Нова пошта, відключення, бабуся, кум, дача, ОСББ…), story chains, social events, seasonal/holiday events, role and species events. Use whenever the user asks to add, expand, fix or review game content, events, adventures, quests, storylines, choices, outcomes, plot twists, holidays, jobs content, or says something like "more events about X", "напиши пригоди", "додай квест", "pets need more stuff to do", even if they don't mention the DSL.
---

# Writing Kit the Cat events

The game's soul is everyday Ukrainian life pushed into absurdity, with consequences the player can see on the
sprite. Your job is to write events that are funny in natural Ukrainian, safe, and balanced — and to prove it with
the content tools.

## 1. Find what's needed

```bash
uv run python scripts/content_stats.py --gaps
```

If the user named a theme, still glance at gaps: you can often serve both (e.g. a ЦНАП event with a `glutton`
choice — that personality is underrepresented). Read `docs/CONTENT_GUIDE.md` fully before your first batch in a
session; it has the tone, boundaries, difficulty and magnitude tables. `docs/DSL.md` is the key reference
(effects, requirements, items, backgrounds, jobs, seasons). Don't invent keys — the contract is
`content/dsl.py` (`KNOWN_FX`, `KNOWN_REQ`).

Pick the module by theme: `life.py` (stages of life), `daily.py` (everyday, seasons/holidays), `chains.py`
(multi-step quests), `jobs.py` (job-gated), `species.py` (one species), `social.py` (two pets), `twists.py`
(roles, supernatural, plot twists). Read 2–3 neighbouring events there first and match their rhythm.

## 2. Write

Per event:
- unique id with a theme prefix; text ≤ 450 chars; button labels ≤ 40 chars, verbs;
- 2–4 choices that are *different characters* (careful / greedy / chaotic / kind…), each with `auto="<trait>"`;
- several outcomes with weights where surprise helps; one rare (`w=0.2–0.35`) memorable outcome per event is
  ideal — ideally one that changes the look (`item=`, `gene=`, `mutate=`) or opens a chain (`flag=`);
- checks via `check=("skill", diff)` with a funny `fail=[...]`; choose `diff` from the guide's table for the
  youngest stage that can see the event;
- `req=` matching the story: jobs/marriage/debt → adult, crushes → teen+, babies → `stage=1`.

Ukrainian: modern, no russisms/surzhyk (unless a character's joke), straight apostrophe `'`, «ти» to the player.
Pets are referred to as `{name}`; prefer constructions that don't break for any pet name.

Boundaries (never cross, even if asked for "darker"): no mockery by ethnicity/race/religion/orientation/gender
identity/disability/appearance; no self-harm, eating-disorder, drug or real-violence encouragement; war content
respectful to defenders, veterans, the fallen, volunteers, civilians — the enemy and propaganda may be mocked;
no real private people; romance only teen+ and couples adult. Dark, absurd, cartoon-deadly is fine.

For a chain: every flag value some event requires must be set by an outcome; give an exit at each step; finish
with `unflag=`. For social: `social=True`, `{other}`/`{other_owner}`, `other={...}`, `rel=`, `status=`.

A new mechanic that the DSL can't express is an engine change, not content: add the key to the contract and the
dsl.py docstring, implement it in `engine.Pet.apply`/`meets`, add a test, then run
`uv run python scripts/gen_dsl_docs.py`. Tell the user it's a minor version bump.

## 3. Verify (all must pass)

```bash
uv run python -m kit_the_cat.content.validate
uv run python scripts/content_stats.py --strict      # dead ends, {other} misuse, hard checks
uv run pytest -q tests/test_dsl_contract.py
uv run python scripts/balance.py --pets 24 --days 40 # no new FAIL; event deaths stay ≤ 15 %
```

Read new warnings from `content_stats.py`: a hard check in a chain finale is fine, a hard check on an everyday
event is not. To see an event in action, the sandbox (`uv run kit-the-cat`) lets you trigger adventures.

## 4. Report

List the new events (id → one-line pitch), which gaps they fill, the before/after counts from `content_stats.py`,
and any balance changes. Offer the `content-reviewer` agent for a second pass on language and boundaries when the
batch is large (10+ events). Update `CHANGELOG.md` under Unreleased → Added (e.g. «12 пригод про відключення»).
