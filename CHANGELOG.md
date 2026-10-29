# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/), versions: [SemVer](https://semver.org/) — see
[CONTRIBUTING.md](CONTRIBUTING.md#versioning). Hosts pin a tag; read this before bumping.

## [Unreleased]

### Changed
- **Stories cost less and never push a broke pet into debt**: the car story starts only with 2 500 ₴ of savings and
  its sums are roughly halved (deposit 200, prepayment 800, the car 1 200), rent commission 500, the first donation
  300; pricey choices (prepayment, buying the car, paying the commission, donating) are hidden when the pet can't
  afford them.
- **A small debt no longer kills**: below 0 ₴ a pet stops healing, but debt collectors hurt its health only below
  −1 000 ₴ (`DEBT_SOFT`), and faster below −3 000 ₴ as before. Weak pets used to die from a short dip under zero
  because they could neither heal nor pay the doctor. Debt deaths: balance 7 of 129 over 4 seeds (was 17 of 136),
  the bot's simulation 4 of 20 over 3 seeds (was 11 of 20).

### Fixed
- `test_health_recovers_slowly_and_the_doctor_costs_money` failed after 14:00 (ten ticked hours crossed midnight
  and daily upkeep changed the wallet).

## [0.9.0] — 2026-10-29

### Added
- **Stories — several decisions in a row** (`content/stories.py`): 8 small real-life Ukrainian situations played as
  2–4 decisions without pressing 🎲 again — «Ніч тривоги», «Потяг до Ужгорода», «Авто з OLX», «Весілля в селі»,
  «Збір на пікап», «Довідка з ЦНАПу», «Не та посилка», «Квартира в Києві». Hidden story scores pick one of 2–3
  endings, and the last result lists every decision with «Разом за історію» totals.
- DSL: effect `step="id" | [ids]` (the next step starts at once; a list picks the first whose `req` holds, the last
  is the fallback), effect `sv={...}` and requirement `sv={...}` (story scores), `ev(..., story="Назва")`.
  `Result.next` and `Result.story` tell hosts to show the next step right away and the recap at the end; the
  story being played lives in `Pet.tale`. The validator checks steps, loops and depth (≤ 6).
- Browser game: «📖 Назва · крок N», the previous step's outcome above the next one, the recap in the result card;
  on phones the adventure scrolls so its choices sit right above the bottom dock.

### Fixed
- `test_tournament` was flaky after the longer childhood: the test now grows pets through all of childhood.

## [0.8.1] — 2026-10-29

### Changed
- **Childhood lasts longer**: a kid ages 4 years per game day instead of 7 — about three real days and twice as many
  childhood adventures (≈16 instead of ≈8); a whole life still takes 35–39 real days.
- **Phone layout of the browser game**: a compact pet header (small sprite beside the name), skills and life stats
  folded under «📊 Навички й статус», the four tabs in one row, and a bottom dock with «🎲 Нова пригода» /
  «❗ Вирішити пригоду», 💊 and 🐾 that jumps straight to the adventure; the scene picture has a fixed height so
  every choice fits above the dock. Desktop is unchanged.

### Fixed
- An unanswered adventure the pet has outgrown is dropped (a 17-year-old no longer gets «ріжуться зуби» from the
  baby days): `Pet.age_fits()` re-checks stage, phase and years as the pet ages.

## [0.8.0] — 2026-10-29

### Added
- **31 childhood and youth events** (`content/youth.py`): St Nicholas night, chickenpox, lessons in the school
  shelter, the tooth fairy, the icy sledding hill, the first pocket money, the school play «Котигорошко», chess
  club, fishing with grandpa; for teens — the ID-card photo, a cruel meme in the class chat, the smartwatch cheat,
  the skatepark, the first concert, school president elections, teaching grandma her smartphone, a fake-news
  panic, esports, the exchange trip, tutoring, a sleepover, the basketball team.
- **Childhood echoes**: three choices come back in adulthood — the new kid from Kharkiv offers a job (16 years
  later), the yard HQ reunites by its old password (20 years), the school president is asked to run for council.

### Changed
- Events written for the pet's current life phase (`req phase=`) come up twice as often, so kids and teens live
  kid and teen stories instead of generic ones.

## [0.7.1] — 2026-10-29

### Changed
- **Only risky choices kill**: a choice that leaves health at 0 kills only if it took at least `LETHAL_HIT = 30`
  health at once; smaller hits (one more episode, a toothache) leave the pet at 1 ❤️ with a warning, and random
  tails never kill.
- **Every stat is named**: the card shows «❤️ здоров'я 80 · 😊 настрій 65», «💪сила 13 🧠розум 12…», life stats and
  traits with their names; the browser game labels the bars and stat chips too (and the bar grid fits the numbers).

## [0.7.0] — 2026-10-29

### Added
- **Life phases** (`engine.PHASES`, `Pet.phase()`, `req=dict(phase=…)`): childhood 0–12, youth 12–18, young
  adulthood 18–30, maturity 30–60, old age 60+. The card shows the phase instead of the stage.
- **33 events by age** (`ages.py`): a childhood dream (`dream_seed` makes the dream's quest come sooner), the
  first class, a summer in the village, selling apples; driving school, camouflage nets, a hackathon, streaming;
  roommates, the wedding summer, **the quarter-life crisis (24–30)** with four branches (travel, therapy, IT
  courses, back to the parents); the parents' chat, a bad back, **the midlife crisis (40–50)** with four branches
  (motorbike, garage band, Ironman, garlic in the village); a smartphone that turns a grandparent into a blogger,
  the university of the third age, romance in a sanatorium, nets with the neighbours.

### Changed
- The old «Криза середнього віку» event comes only at 38–55, not to every adult.

### Fixed
- The card game with Death and the genie's «eternal youth» said «днів» but added 20–38 years (left over from
  day-based ages): now +10 / +15 / −5 / +8 years, as the text says.

## [0.6.1] — 2026-10-29

### Fixed
- A failed dream step could come back after every few adventures (a weak pet repeated `dr_drone_2` endlessly):
  every follow-up is scheduled at most `FOLLOWUP_MAX = 3` times per life, and dream retries wait ≥ 2 years.
- The fair world event no longer uses an ethnic stereotype («ворожка з картами»).

## [0.6.0] — 2026-10-29

### Changed
- **Decisions cost life time again, hidden from the player**: `Choice.time` / `Event.time`, `dsl.infer_time`,
  module bases and `CHOICE_TIME` are back, but `Pet.button()` shows no time and outcomes add no «⏳» note.
  `Result.time` tells hosts how many years a decision took (to pace their world); `Pet.spend()` charges hidden
  time for actions — casino (1d/3d/1w), job interview (2w), doctor (1w). Jail and hospital eat years again.
  The clock is slower (`YEARS_PER_DAY` 7/2/1.4/1.4): a life is ~86 years ≈ 38 days in the bot.
- **Health matters**: natural recovery is slow (`HEAL_PER_H = 0.3`, faster in a good mood); health at 0 after a
  choice kills («не пережив пригоду «…»»); the doctor (💊) costs `HEAL_PRICE` 150 ₴ for adults.
- **Sandbox / browser game: no time button.** The egg has a one-time «🐣 Вилупити» (`hatch` action); every action
  moves the world on by the life time it cost (`Sandbox._pass`); your own pets never live without you.

### Added
- **Temperament perks** (`persona.PERKS`, `Pet.perk()`, `perk_text()`): base-stat modifiers for all 36
  temperaments, counted in every check; in-character choices get +8, come up more often, feed the lean trait more
  and are marked 🎭 on buttons («🎭 конспіролог: у своїй стихії» in the result).
- **Dreams are goals** (`persona.GOALS`, `req=dict(goal=…)`, `Pet.goal_step()`, `goal_text()`): 12 dreams, each
  with a three-step quest (36 events in `dreams.py`), retries after failures, «Мрія збулася» achievement, a life
  title and a summary line. Old pets get a goal on load.
- **11 health events** (`health.py`): tooth, check-up, gym, Truskavets, a roof at sunset, an e-scooter, running,
  sleep, blood pressure, blood donation, appendicitis.
- 12 пригод у трьох арках: тривога в коридорі й сусіди, грибний ліс (лісовик, луна), різдвяні колядники
  (`arcs_week_20261029.py`, перший тижневий PR).
- Balance: `dream_share` target (25–85% of lives fulfil the dream); event deaths up to 25%.

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

[Unreleased]: https://github.com/ifurs/kit-the-cat/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/ifurs/kit-the-cat/compare/v0.8.1...v0.9.0
[0.8.1]: https://github.com/ifurs/kit-the-cat/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/ifurs/kit-the-cat/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/ifurs/kit-the-cat/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/ifurs/kit-the-cat/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/ifurs/kit-the-cat/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/ifurs/kit-the-cat/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/ifurs/kit-the-cat/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ifurs/kit-the-cat/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ifurs/kit-the-cat/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ifurs/kit-the-cat/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ifurs/kit-the-cat/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ifurs/kit-the-cat/releases/tag/v0.1.0
