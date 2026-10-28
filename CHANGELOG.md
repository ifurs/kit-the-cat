# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/), versions: [SemVer](https://semver.org/) — see
[CONTRIBUTING.md](CONTRIBUTING.md#versioning). Hosts pin a tag; read this before bumping.

## [Unreleased]

## [0.5.0] — 2026-10-28

### Changed
- **Decisions cost no life time again** (no labels, no inference; `Pet.button()` returns the plain label;
  `Choice.time`/`Event.time` removed). The clock ages pets: a life is ~80 years ≈ 30 real days. Story outcomes
  may still skip years (`o(..., time="5y")`). The casino costs no time; `CASINO` tuples lost the time field.
- **Energy is automatic** like food and sleep (`EVENT_ENERGY = 0`); the card shows only ❤️ and 😊. Hosts pace
  manual adventures with their own cooldowns.

### Added
- 🐦 **Bird**, the 7th species: crest / parrot crest, beak / hooked beak, feather fan / swallow tail, wings,
  three-toed feet; sparrow, tit, canary, robin, parrot, pigeon, crow and bullfinch colours; 🐦 Політ battle
  passive (+12% dodge, fast); names; 6 bird events; a twist can turn a pet into a bird.
- **92 new events as branching life arcs** (`arcs.py`, `arcs_adult.py`, `arcs_soul.py`): every choice of a root
  event schedules its own consequence, some chain further — the drawing on the wallpaper, the music school, the
  school bully, the love note, the olympiad, the stray puppy, the time capsule, flooding the neighbours, the found
  wallet, a loan to a friend, the ОСББ chair, a car from Lithuania, grandma's recipe, great-grandpa's house, fraud
  at work, the stairwell generator, the bench committee, a charity run, fortune tellers, the домовик, Andriy's
  Eve, prophetic dreams, grandpa's telescope, switching to Ukrainian, grandma's vyshyvanka, the veteran next
  door, the drone jar. 478 events / 1598 choices in total.

## [0.4.0] — 2026-10-28

### Changed
- **Decisions weigh more, the clock less.** Choices without a hand-set `time` get one computed from what they
  do (`dsl.infer_time`: studying, a job, moving, a serious relationship, a story step, skills learned, money
  earned), so options within an event differ (events where every choice costs the same: 328 → ~60). Prison and
  hospital cost life time (`jail=48` ≈ 1 year). Adult clock 2.0 → 1.05 years/day: decisions now eat ~35% of a
  life (was ~15%); a life is ~45 real days. Hand-tuned times for the most common everyday events.
- Personality steers what happens: situations where a pet can act in character come up more often.

### Added
- **Consequences:** `then=("fu_id", "2y")` schedules a follow-up event after that much of the pet's life;
  `ev(..., followup=True)` events never fire at random. 21 follow-ups (`content/consequences.py`) for common
  choices — the scam call, «КумКоїн», the kum's wedding, ЦНАП, the socket, the shelter, the TikTok video…
- Life summary: «рішення забрали N років життя» (`counters["dec_years"]`).
- Content pipeline: `scripts/ua_lint.py` (Ukrainian lint over every player-facing string: Russian letters, Latin
  look-alikes, apostrophes, placeholders, «», russisms/surzhyk, typography; strict in CI), `scripts/content_gate.py`
  (all content gates in one command), the `kit-event-writer` skill as a plan → write → gate → review → simulate
  pipeline, a stronger `content-reviewer` agent; balance target `decision_share`.

## [0.3.0] — 2026-10-28

### Changed — the life model (breaking for hosts that show care)
- **Upkeep is automatic.** Food, washing and sleep happen by themselves; adults pay a daily cost of living by
  wealth tier. Debt shows on the sprite (hungry, dirty), brings poverty events and slowly hurts health.
  Pets no longer die of neglect. `care()`/`feed()` still work but are no longer needed (healing is).
- **Age is in years.** `Pet.years`: the clock ages a pet (faster in childhood), and **every decision costs time**
  (`time=` on choices/outcomes, module defaults; `Pet.button()` shows it: «Вступити в КПІ · 4 р.»). A life is
  ~75–90 years ≈ 30 real days; stages at 12/18/60 years; `lifespan` is in years.
- **Life stats with tiers:** 📈 популярність, 🕶 авторитет, 🤝 блат, 📊 фінграмотність, ✨ привабливість (0–100) and
  💰 wealth tiers. Tiers bring income (ads, «дах», interest, better pay) and risks (raids, NABU, scandals, tax
  checks), are announced, and are recorded in the life summary. Personality in outcomes echoes into them.
- Old pet documents migrate on load (age → years, life stats guessed from skills, traits, job and record).

### Added
- 🎰 Casino: `engine.casino(p, venue, stake, rng)`, venues per wealth tier (`CASINO`, `casino_venues`).
- 47 new events (`content/status.py`): blogging and fame, money and investments, «крипта від кума», street
  authority, connections, style, big life decisions with years, casino; per-choice time on key older events.
- DSL: effects `fame auth blat fin attr time`; requirements `life tier tier_max years`; `dsl.years()`.
- Sandbox: life stats with tier names, casino, time on choice buttons, age in years; care buttons removed.

## [0.2.0] — 2026-10-27

### Added
- Developer tooling: `scripts/balance.py` (headless neighbourhood simulation with balance targets),
  `scripts/content_stats.py` (content map, gaps, dead-end chains, hard checks), `scripts/gen_dsl_docs.py`
  (`docs/DSL.md` generated from code), `scripts/ui_audit.js` (mobile layout audit).
- Docs: `docs/CONTENT_GUIDE.md` (how to write events — Ukrainian reality, language, boundaries, balance),
  `docs/ARCHITECTURE.md`, `docs/INTEGRATION.md`, `CONTRIBUTING.md`.
- Claude Code skills (`.claude/skills/`) for writing events, sprites, balance, playtesting and releases, and a
  content-review agent; GitHub issue/PR templates; CI checks for generated docs and content.
- `unequip` and `noedu` are now documented in the DSL reference.
- Life summary after death: `engine.life_summary()` (title for the life, facts, highlights, family, epitaph) and
  `engine.obituary()` (caption-sized HTML); the dead pet's `card()` and the sandbox show it. `engine.plural()`.
- Pet documents gain `seen` (events lived) and `story` (highlights); old documents load with empty defaults.

### Changed
- Events repeat much less: a pet doesn't get any of its last 40 events (was 12) while something else fits, and
  every earlier time it lived an event cuts that event's weight ×0.3 for the rest of its life. Social events also
  skip what the other pet just lived. Simulation: repeats within a life 24 % → 10 %.
- Sandbox shows the role's name instead of its id.

## [0.1.1] — 2026-10-27

### Fixed
- Sandbox on phones: no horizontal overflow, popups stay on screen, larger touch targets, wrapping rows, 2×2 tabs.
- Tournaments with byes no longer stall; hidden browser tabs no longer freeze animation waits.

## [0.1.0] — 2026-10-27

### Added
- The «Кошеня» pet life-sim as a standalone package: engine, 313 events / 1134 choices in the DSL, 6 species,
  procedural sprites with a chat-unique genome, 8 roles, jobs and economy, battles and tournaments, `MemoryStore`,
  sandbox (aiohttp server and Pyodide browser build on GitHub Pages).

[Unreleased]: https://github.com/ifurs/kit-the-cat/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/ifurs/kit-the-cat/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ifurs/kit-the-cat/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ifurs/kit-the-cat/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ifurs/kit-the-cat/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ifurs/kit-the-cat/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ifurs/kit-the-cat/releases/tag/v0.1.0
