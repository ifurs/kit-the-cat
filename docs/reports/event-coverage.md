# Event coverage: why ~240 events «never fired» in `balance.py`

Date: 2026-11-03 · content at 0.14.0 (749 events, 251 of them follow-ups) · tool: `scripts/event_coverage.py`.

## Short answer

**Not a single event is unreachable.** The «never fired» line of `balance.py` was a simulation artefact, not a content
bug: out of 283 events missing in a reproducible baseline run, **none** has a contradictory `req`, a follow-up without a
root, a flag nobody sets, or a follow-up that comes due at the wrong age. Two real defects were found, both in the
tooling, not in the content:

1. **The sandbox killed every story after its second step for neighbours (NPCs).** `Sandbox.advance` auto-resolved a
   pending step and then wrote `p.pending = {}`, wiping the next step that `Pet.resolve` had just started. About 70
   events (story steps `st_*_3`, `st_*_end*`, `st_tv_*`) could never fire in any simulation or in the local sandbox world.
   Fixed (`sandbox/game.py`).
2. **The run was not reproducible** (see below): the clock was real time, so the date, holidays, night and the seconds
   the run itself took changed the result.

After the fixes the default run fires 72% of the content (was 62%); twelve runs from dates spread over the year, with
owners who also hunt for jobs, fire 94% (703 of 749). The 46 left are exactly the deep chains and jobs that need a
longer story (see «Left on purpose»).

## What «never fired» consisted of

Baseline = the old engine, made reproducible (seed 1, start 2026-03-02): **283** never fired. Same run after the
sandbox fix: **212**. Categories (`event_coverage.categorize`):

| Category | Baseline | After the fix | What it means |
|---|---:|---:|---|
| (г) needs a job / role / story flag / relationship the run rarely gets | 99 | 87 | `job_*`, `army_*`, `crime_*`, `pol_*`, `space_*`, `tw_*` role twists… The run has no hiring and roles are rare. All reachable (see graph below); `--sim` with job hunting + 12 dates cuts them to 30. |
| (а) follow-up, root fired but not it | 59 | 54 | Needs one particular choice or outcome of its root (often a money-gated choice, `w=0.2` outcome or a 10–20-year delay), which the autopilot did not take. |
| (а) follow-up waiting for its root | 83 | 26 | Root itself never fired in the run. Dropped from 83 to 26 once stories could continue. |
| (в/г) plain: drawn from a pool of ~150 and just not drawn | 26 | 29 | `teen_*`, `sp_*`, … 3000 draws per run over 750 events. They fire in other seeds. |
| (г) seasonal: the run covers 40 days from one date | 16 | 16 | `daily_new_year`, `koliada_group`, `forest_mushrooms`, `ice_slush`, … They fire when the run starts at the right date (`--union`). |
| (б) unreachable `req`, no root, nobody sets the flag | **0** | **0** | the only real errors, and there are none |
| (в) too small a weight | **0** | **0** | the rarest event in its own situation is `tw_lottery_mansion` at 0.09% of its pool (a twist, on purpose) |

## How reachability is proved (`scripts/event_coverage.py`)

1. **Forge.** For every event (and for each of its choices, since a choice has its own `req`) a pet is built that meets
   the `req` on a date that fits `season=`/`night=`, and the engine's own `Pet.eligible` is asked. This finds
   contradictory or impossible requirements (a teen with `years=(30, 40)`, `flag` and `noflag` on the same flag).
2. **Walk.** From the events that need no story state, every choice and every outcome is applied to a copy of the pet with
   the real `Pet.apply`; follow-ups (`then=`) come due, story steps (`step=`, with `sv=`) follow, and each resulting
   state is checked against the events that need story state (`flag`, `edu`, `role`, `has`, `job`, `sv`). Age, skills,
   money and the like count as reachable by living on; flags, education, items, roles and jobs must really come from an
   outcome. A follow-up must also come due at a fitting age (the root's window plus the delay plus the 15 years it
   waits). Social events additionally need a relationship someone can form (`status=crush|partner`, an ex needs a
   partner).
3. **Weight.** For the forged pet, the event's share of `Pet.candidates` (the exact pool `pick_event` draws from).

Tests: `tests/test_event_coverage.py` feeds synthetic content with each defect (orphan follow-up, unset flag value,
contradictory `req`, follow-up that outlives the pet, follow-up its own root makes ineligible, a story step no path
reaches, a relationship nobody forms) and the real content, which must stay clean.

## The gate

`content_stats.py --strict` (hence `content_gate.py` and the check list in `CLAUDE.md`) now fails on any unreachable
event, with the reason. It costs about 12 seconds, so the plain overview (`content_stats.py`) does not run it. There is
no threshold: today the true count is 0, and every defect class above is a content error. The «rare» warning
(`RARE_SHARE`, below 0.05% of the pool) only prints.

Run it by hand: `uv run python scripts/event_coverage.py [--list]`, and
`uv run python scripts/event_coverage.py --sim --union 12 --list` to explain the simulation's «never fired» list (about
four minutes).

## Reproducibility of `balance.py` (task 2)

Sources of the 65–72% jitter in `check_success`:

- `Sandbox` set `engine.clock = time.time() + offset`: the simulated date (season, holidays, night, `kyiv()`) started at
  *today*, and the 13–16 real seconds a run takes were added to the game clock. Two runs never saw the same calendar.
- `Pet.hatch` drew `next_ev` from the global `random`.

Fixes: `Sandbox(..., epoch=)` gives a purely virtual clock (`epoch + offset`); `balance.py` starts at `--start`
(default 2026-03-02, 08:00 Kyiv) and passes the seed; `Pet.hatch(t, rng)` takes the sandbox rng. Three runs in a row, and
runs under different `PYTHONHASHSEED`, now give identical output (66% / 72% coverage / 212 never fired).

The target `check_success 0.45–0.70` is **unchanged**: the reproducible default result is 66%; other seeds give 66–70%
(seed 4: 70%, a `WARN` at the edge). That is real spread between seeds of a 24-pet run, not a miscalibration. No other
target was touched. After the story fix the numbers moved because neighbours now live whole stories (time and money): `money_median` 2484 (unseeded runs gave 4800–6850), `life_years` 76 (was ~82), `debt_share` 15% (was 0%); all still `OK`.

## Left on purpose

- The 46 events the twelve-date run (`--union 12`, owners hunt for jobs) still did not fire:
  - 30 deep story states: `crime_boss`, `crime_retire`, `job_bandit*`, `pol_*`, `job_deputy_tender`, `space_*`,
    `job_astro_iss`, `cult_succession`, `blog_award`, `blog_burnout`, `hire_doctor`, `job_doctor*`, `hire_poker`,
    `job_poker_tell`, `poker_*`, `job_dj*`, `job_exorcist_osbb`, `keys_tavria`, `st_nabu`, `st_phone_law`. Each needs a
    3–5 step chain (a flag value that must be exactly `crime: 3`, a diploma, a job taken through a gated event). The walk
    proves a path exists for each one.
  - 15 follow-ups that wait for one choice of their root (`arc_loan_rich`, `arc_osbb_scandal`, `st_tv_end*`, …).
  - 1 plain event (`st_casino_addiction`: needs `gambler ≥ 25`).
- Twist events with a weight of 0.2–0.5 (`tw_*`) stay rare: by design.
- No event text was changed, so the `content-reviewer` pass was not needed.

## Not done / ideas

- A job hunt is only in coverage runs (`balance.py --jobs`, used by `event_coverage.py --sim`): with it on, wallets and
  the economy targets shift, so the main balance run stays without it.
- The walk treats a skill/money/trait requirement as reachable by living on; if a future event asks for something no
  pet reaches (`cha 100`), add a cap check per stat (all stats cap at 100, so only values near 100 matter).
