---
name: kit-event-writer
description: The content pipeline for the Kit the Cat pet game — plan, write, auto-check and language-review new life events (пригоди) in its DSL: funny Ukrainian-reality scenarios (ЦНАП, маршрутка, АТБ, Нова пошта, відключення, бабуся, кум, дача, ОСББ…), story chains, follow-ups that bring earlier choices back, social, seasonal, role, species and life-stat events (fame, authority, blat, money tiers, casino). Use whenever the user asks to add, expand, fix or review game content, events, adventures, quests, storylines, choices, outcomes, consequences, plot twists, holidays, or Ukrainian text quality — "more events about X", "напиши пригоди", "додай квест", "перевір українську", "pets need more stuff to do" — even if they don't mention the DSL.
---

# Kit the Cat content pipeline

Every batch of events goes through the same five stages. Don't skip the review stages for small batches — a
single russism or a misjudged war joke reaches every chat that has the bot.

```
1 plan (gaps) → 2 write → 3 automatic gate → 4 language & boundaries review (agent) → 5 simulate, report, commit
```

## 1. Plan

```bash
uv run python scripts/content_stats.py --gaps
```

Read `docs/CONTENT_GUIDE.md` fully before your first batch in a session (tone, boundaries, difficulty, magnitudes,
time costs, life stats). `docs/DSL.md` is the key reference. Decide the batch: theme from the user, plus at least
one gap from the report (an underused personality, a thin stage, a job or role with few events).

Pick the module: `life.py` (stages), `daily.py` (everyday, seasons), `chains.py` (quests), `jobs.py`, `species.py`,
`social.py`, `twists.py` (roles, supernatural), `status.py` (life stats & tiers, big life decisions, casino),
`arcs.py` / `arcs_adult.py` / `arcs_soul.py` (branching life arcs), `consequences.py` (follow-ups of older events). Read 2–3 neighbouring events first and match their rhythm.

## 2. Write

Per event: unique id with a theme prefix; text ≤ 450 chars; labels ≤ 40 chars, verbs; 2–4 choices that are
different characters, each with `auto="<trait>"`; several weighted outcomes, one rare memorable one (ideally a
visible change: `item=`, `gene=`, a tier); checks `check=("skill", diff)` with a funny `fail=[...]`; `req=` that
matches the story.

Decisions cost no life time (the clock ages pets); only a story outcome may skip years
(`o(..., time="5y")` for a coma or a sentence).

**Earlier choices must come back — this is the main rule.** Prefer *arcs* (`arcs*.py`): a root event where
each choice schedules its own follow-up, and follow-ups sometimes lead further. When a choice would plausibly
matter years later, add
`then=("fu_<id>", "2y")` to its outcomes and write the follow-up in `consequences.py` with `followup=True`; its
text recalls the original choice («Пам'ятаєш, як {name}…»). Follow-ups never fire at random.

**Life stats:** personality in outcomes already echoes into fame/authority/blat/fin/attr; write them explicitly
only when they're the point. Tier-gated events (`req=dict(tier={"fame": 2})`) show the price of success.

**Language:** modern natural Ukrainian, no russisms or surzhyk (unless a character's joke — then add it to
`scripts/ua_allow.txt`), straight apostrophe `'`, «лапки», `…`, `—`, «ти» to the player, phrasing that works for
any `{name}`.

**Boundaries (never cross, even when asked for "darker"):** no mockery by ethnicity (incl. Roma), race, religion,
orientation, gender identity, disability or unchosen appearance; no self-harm, eating-disorder, drug or
real-violence encouragement; war content respectful to defenders, veterans, the fallen, volunteers and civilians
(the enemy and propaganda may be mocked); no real private people; romance teen+, couples adult; gambling is
satire where literacy pays off.

A mechanic the DSL can't express is an engine change: contract key in `dsl.py` + docstring, `engine.Pet.apply` /
`meets`, a test, `scripts/gen_dsl_docs.py`. Tell the user it's a minor version bump.

## 3. Automatic gate

```bash
uv run python scripts/content_gate.py --quick
```

Runs the DSL contract, **Ukrainian lint** (`scripts/ua_lint.py`: Russian letters, Latin look-alikes, typographic
apostrophes, unknown placeholders, unbalanced «» fail; russisms, missing apostrophes, `...`, ` - `, ASCII quotes
are warnings), dead ends and hard checks, the DSL reference and the content tests. Fix every error. Treat every
warning in your new text as a bug unless it's an intentional character voice (then allow-list it).

## 4. Language & boundaries review

Spawn the `content-reviewer` agent (`.claude/agents/content-reviewer.md`) on the new event ids — always, it is the
part the lint can't do: naturalness ("does a Ukrainian say it like this?"), calques that aren't in any list,
gender agreement, tone, whether the joke lands, boundaries. Apply its "block" and "fix" items; use judgement on
"nit". If you changed text, run the gate again.

## 5. Simulate, report, commit

```bash
uv run python scripts/content_gate.py      # with the balance simulation
uv run kit-the-cat                         # optional: play the new events in the sandbox
```

Report: new events (id → one-line pitch), which gaps they fill, follow-ups and arcs added, before/after
counts from `content_stats.py`, lint and reviewer results, balance changes. Add a CHANGELOG line under
Unreleased → Added (e.g. «12 пригод про відключення, 3 наслідки»). Commit when the user asked for it.
