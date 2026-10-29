# Plan: name cases, pet gender, «Холостяк / Холостячка»

Status: phase 1 done on `feat/gender-cases` (not pushed) · written 2026-10-29 · executor: Claude Sonnet, one phase per session.

Three user-visible problems, in the order they are fixed:

1. **Names are never declined.** Every `{name}` is inserted in the nominative, so a name with an adjective or a tail
   breaks the sentence: «Під дверима **Крилатий з Троєщини** пищить кошеня», «**Крилатий з Троєщини** запросили на
   Fashion Week». Must be «Крилатого з Троєщини», «Крилатому з Троєщини», «з Крилатим з Троєщини».
2. **Every pet is a he.** There is no gender field; the name pools already contain girls (Мурка, Сметанка, Жучка,
   Синичка, Мандаринка, Зірочка…) but every text says «вилупився», «знайшов», «Підкорив Говерлу», «найкращий друг».
3. **«Холостяк» is one line.** `blog_viral` → «Піти на «Холостяка»» gives one result («Не отримав троянду…»). It is
   an STB show — it must be a multi-step story with a row of decisions (roses, dates, drama, final), and a
   «Холостячка» version for girls.

Numbers to keep in mind (2026-10-29): 698 events in 25 content modules, 606 `{name}` and 165 `{other}` placeholders,
~35 engine f-strings with `self.name`, achievements stored as plain strings in pet documents.

## Rules for every session

- Read `CLAUDE.md`, `docs/CONTENT_GUIDE.md`, `docs/DSL.md` first. Use the `kit-event-writer` skill for content.
- Work on the branch `feat/gender-cases` (create it in phase 1; later phases continue on it). Commit at the end of a
  phase with a message `gender/cases phase N: …` and the session's attribution line. **Do not push, tag, release,
  bump the version or deploy Pages** — the owner decides releases. Do not touch the bot repo except in phase 6.
- Gates before every commit (all green):
  ```bash
  uv run python scripts/content_gate.py
  uv run --with pytest pytest -q
  uv run --with ruff ruff check src scripts tests
  uv run python scripts/balance.py
  ```
- Old pet documents must keep loading: every new field gets a default in `Pet.from_dict` (old pets are `"m"`).
- Ukrainian quality: natural modern Ukrainian, no russisms/surzhyk, apostrophe `'`. Gender must not change gameplay
  (no stat, price or chance differences) and no jokes built on gender stereotypes; dating stays gender-agnostic (any
  two pets may date — no mockery by orientation).
- Templates are trusted content; never pass user text (pet names) as a template — names go in as values only.
- When a phase is done, tick it here (`- [x]`) and add a line to `CHANGELOG.md` under `[Unreleased]`.

## Phase 1 — name declension (the bug)  · 1 session

- [x] New pure module `src/kit_the_cat/grammar.py`:
  - `CASES = ("nom", "gen", "dat", "acc", "ins", "loc", "voc")`
  - `decline(name: str, gender: str = "m") -> dict[str, str]` — all seven forms.
  - Split the name into a **declinable head** and an **indeclinable tail**: tails start at a preposition
    (`з`, `із`, `зі`, `від`) or `№`; everything after stays as is («з Троєщини», «Із Жмеринки», «№ 12»).
  - Decline each word of the head: adjectives (`-ий`, `-ій`, `-а`/`-я` after an adjective stem: Крилатий → Крилатого,
    Крилатому, Крилатим, на Крилатому; Вороний; Третій → Третього; Велика → Великої), masculine nouns on a consonant
    (Барсик → Барсика/Барсикові/Барсика/Барсиком/на Барсикові/Барсику), on `-ь`/`-й` (Пельмень → Пельменя), on `-о`
    (Бровко → Бровка, Бровкові, Бровком), nouns on `-а`/`-я` (Мурка → Мурки, Мурці, Мурку, Муркою; Гоша → Гоші,
    Гошу, Гошею), alternations (Овес → Вівса is wrong for a name — keep «Овса»; Горобчик, Снігур → Снігура).
    Animate accusative = genitive for masculine names.
  - `EXCEPTIONS: dict[str, dict]` for names the rules get wrong; indeclinables (Ферарі, Цок-Цок, Гуппі-Бос, Аксель?) —
    decide each one and test it. Unknown words (user names via the bot's `/pet_name`) fall back to the rules; if a
    word does not match any rule (Latin letters, digits, emoji), leave it in the nominative.
- [x] `Pet.fmt` gets `name_gen`, `name_dat`, `name_acc`, `name_ins`, `name_loc`, `name_voc` and the same for
  `other_*` (cached per name). `{name}` stays the nominative. Add the keys to whatever list the validator uses for
  allowed placeholders and to `docs/DSL.md` (regenerate with `scripts/gen_dsl_docs.py`).
- [x] `tests/test_grammar.py`: a table of ≥ 60 hand-checked forms including **every** base name in
  `content/persona.py` `NAMES` (gen, dat, ins at least), names with suffixes («Крилатий з Троєщини», «Бублик
  Грозний», «Лис Микита», «Пуголовок Іван», «Мурка Велика» after phase 2), and fallbacks. This table is the spec —
  verify each form yourself, do not generate it from the code under test.
- [x] Fix the content: find every `{name}` / `{other}` that is not a subject and switch it to the right case. Write
  `scripts/case_scan.py` that lists candidates: after a preposition (у, в, до, від, для, без, біля, про, на, за, над,
  під, перед, між, з, із, з-за, у дворі, під дверима…), before an impersonal plural verb («{name} запросили /
  покликали / відправили / забрали / вигнали / кличуть / пропонує»), after «Відео/пости/мама/двері + {name}»
  (genitive), vocative in quoted speech («Ей, {name}!» → `{name_voc}`). Review every hit by hand — the scan is a
  helper, not the judge. Add a content-gate check that fails on the obvious patterns (preposition + `{name}`).
- [x] Engine f-strings (`self.name` in `engine.py`, ~35) and `sandbox/game.py`: same review.
- Done when: the gate check is green, `grep -rn "з {name}\|у {name}\|до {name}" src` is empty, and a sandbox pet
  renamed «Крилатий з Троєщини» reads correctly in 20 random events (write it as a test that formats every event text
  and every outcome text with that name and asserts no `{` is left).

## Phase 2 — gender in the engine  · 1 session

- [ ] `Pet.gender: str = "m"` (`"m"` | `"f"`), saved in the document, default `"m"` in `from_dict`.
- [ ] `new_pet(..., gender=None)`: random 50/50 when not given; heirs get a fresh random gender.
- [ ] `content/persona.py`: `NAMES[species]` → `{"m": [...], "f": [...]}`; move the existing girls' names to `"f"` and
  add enough so each list has ≥ 12. `NAME_SUFFIX` → pairs (`(" Великий", " Велика")`, `(" Третій", " Третя")`,
  tails like `" з Троєщини"` are shared). `make_name(species, taken, rng, gender)`.
- [ ] **Template syntax for gendered words**: `{вилупився|вилупилася}` (the pet) and `{other:відмовив|відмовила}`
  (the other pet). `Pet.fmt` substitutes these with a regex **before** `format_map`
  (`\{(?:(other):)?([^{}|:]*)\|([^{}|]*)\}`), so it never reaches `str.format`. Validator: exactly two alternatives,
  no nested braces, no placeholders inside the alternatives; document it in the DSL docstring + `docs/DSL.md`.
- [ ] Gendered display data: `STATUS_NAMES` (друг/подруга, найкращий друг/найкраща подруга, суперник/суперниця,
  ворог/ворогиня — pick natural words), `PHASE_NAMES` if any are gendered, role names (Вампір/Вампірка?, Ангел — keep
  if a feminine form sounds silly; decide per word), epitaphs (`{|}` inside them), species names if needed.
- [ ] Achievements: keep the stored key masculine (existing documents), add `ACH_F = {"Підкорив Говерлу":
  "Підкорила Говерлу", …}` and `Pet.ach_name(key)` for display; the browser game and the bot show `ach_name`.
- [ ] Tests: old document → `"m"`; a girl's `fmt` picks the second alternative; achievements display gendered;
  validator rejects malformed `{a|b|c}`.

## Phase 3 — gender in the content  · 3–4 sessions (≈ 6–8 modules each)

- [ ] Write `scripts/gender_scan.py`: for each module, render every text (event text, choice labels, outcomes, fail
  outcomes, engine notes) for a girl named «Мурка» and list words that look masculine and refer to the pet:
  past-tense verbs ending in `-в`/`-вся`/`-шов` (знайшов, вирішив, повернувся, пішов), short adjectives/participles
  (радий, готовий, щасливий, сам), nouns of role (переможець, чемпіон, блогер? — decide), «він/його/йому» about the
  pet. It prints `module:line: word — text`; keep an allowlist for words about other characters (сусід вирішив…).
- [ ] Go module by module (biggest first: check `scripts/content_stats.py`), turning each hit into `{…|…}` or
  rephrasing so it is gender-neutral (second person present, «вдалося», «тобі дісталося») — rephrasing is often nicer
  than a pair. Keep lines ≤ 120 columns; caption limits still apply (the bot posts these as photo captions ≤ 1024).
- [ ] Add a gate test: every text rendered for `"f"` has no unresolved `{`, and `gender_scan.py --strict` reports zero
  unreviewed hits (allowlist entries carry a short reason).
- Suggested split: session A — `life`, `youth`, `daily`, `consequences`; B — `chains`, `arcs`, `arcs_soul`, `social`,
  `status`; C — `jobs`, `dreams`, `stories`, `stories_more`; D — everything left + engine notes + `sandbox/game.py`.

## Phase 4 — the «Холостяк / Холостячка» story  · 1 session

Design (write the texts with `kit-event-writer`; follow the «Історії» section of `docs/CONTENT_GUIDE.md`):

- Story id prefix `st_tv_`, title `{Холостяк|Холостячка}` → the engine must run the story title through `fmt`
  (`self.tale["title"]` is stored formatted when the story begins; test it). The pet is the **star** of the season
  (boys are «Холостяк», girls «Холостячка»); the contestants are NPCs with first names and a city (Оксана з Полтави,
  Марта-стоматологиня зі Львова, Даша-тіктокерка; for the girl's season — Тарас-пожежник, Андрій-айтішник, Олег-фітнес-
  тренер). Mock the TV format — producers, limousine, roses, «Я не за славою прийшла», drama confessionals — never
  the contestants' looks, origin or class.
- Entry: `blog_viral` → «Піти на «Холостяка»» no longer resolves the whole thing; it sets `flag={"tv_cast": 1}` and the
  root `st_tv` has `req=dict(flag={"tv_cast": 1}, phase=…young/middle…)` (a story root cannot be a `then=` target —
  validator: `then=` must point at a follow-up). Also allow a rarer entry without the blog (`cha` ≥ 60 or fame).
- Six steps (STORY_STEPS = 6), hidden scores `sv={"heart": …, "show": …}`:
  1. **Кастинг** — продюсерка пропонує контракт: погодитись по-чесному / заради реклами блогу (`show+`) / відмовитись
     (story ends, small consolation).
  2. **Перший вечір, лімузин** — кому перша троянда: тій, що спекла вареники / тіктокерці з камерою / тихій, яка
     нервово сміється (`heart`/`show`).
  3. **Групове побачення** — Карпати на квадроциклах / кулінарний батл / фотосесія на Андріївському; конфлікт між
     учасниками — розборонити / дати посваритися на камеру.
  4. **Скандал на віллі** — хтось злив ваше листування / продюсери просять «більше емоцій»: зізнатися / мовчати /
     підіграти сценарію.
  5. **Знайомство з батьками** — двоє фіналістів, поїздки в Житомир і Одесу; мама питає про плани, тато про борщ.
  6. **Фінал** — освідчитись / нікому не дати троянду / піти з тією, кого вибили на другому тижні (secret ending if
     `heart` is high and a step-2 choice matched). Endings by score (`step=[…]` list, fallback last): «Справжнє
     кохання» (partner flag / love+), «Шоу-зірка» (fame, money from ads, `job="blogger"`), «Скандал сезону»
     (fame+, mood−), «Пішов/Пішла з шоу» (calm, `heart`).
- Achievements: «Остання троянда» (gender-neutral), «Зірка реаліті».
- Tests in `tests/test_stories.py`: both genders play every path ≤ 6 steps; the title is «Холостячка» for a girl; the
  recap lists all decisions; `blog_viral` sets the flag and `st_tv` can then fire.

## Phase 5 — browser game  · 1 session

- [ ] Adoption: under the species buttons a ♂ / ♀ / 🎲 choice (default 🎲). Sandbox API `adopt(species, gender)`.
- [ ] Card: a small ♂/♀ next to the name; journal and recaps already come formatted from the engine.
- [ ] Keep `web/index.html` and `src/kit_the_cat/sandbox/static/index.html` identical outside the loader block;
  check phone 375 px and 1280×720 (choices fit) with `scripts/ui_audit.js`.
- [ ] Update `README.md` / `docs/PET.md` (gender, cases), `CHANGELOG.md`.

## Phase 6 — release and the bot  · with the owner

- The owner approves the release (minor bump, new pet field + DSL syntax → 0.12.0); then the usual flow in
  `CONTRIBUTING.md`. The bot side has its own plan in the bot repository (`docs/plans/pet-gender.md`).

## Kick-off prompt for a Sonnet session

> Відкрий `docs/plans/gender-cases-bachelor.md` у kit-the-cat і виконай фазу N. Дотримуйся правил із розділу «Rules
> for every session», не пуш і не випускай реліз. Наприкінці — коротко що зроблено, результати перевірок і що
> лишилось.
