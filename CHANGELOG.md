# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/), versions: [SemVer](https://semver.org/) — see
[CONTRIBUTING.md](CONTRIBUTING.md#versioning). Hosts pin a tag; read this before bumping.

## [Unreleased]

## [0.23.1] — 2026-11-13

### Fixed
- Browser build: after an update the installed app could hang on launch and «Перезапустити» did nothing. The worker
  of 0.21–0.22 stored the 2 MB page before handing it over, and a request stuck there kept the new worker waiting
  for ever. The page of the GitHub Pages build is now small (the game code is a file of its own, `py-<hash>.json`,
  cached for offline play), a waiting version is switched on at launch before the game starts, and when the old
  worker does not answer in 4 seconds the page drops it and loads without one. A deploy no longer downloads the
  game code twice.

## [0.23.0] — 2026-11-13

### Added
- **Redrawable art.** `src/kit_the_cat/assets/` holds 295 PNG files: scenes, wearable items, the shapes of shop items, ears,
  tails, faces, marks, extras, the markers between two pets and the life card's icons. Draw over a file and the bot and
  the browser build use it; an untouched file changes nothing, the code keeps drawing it. How to: `assets/README.md`.
  `scripts/art.py` exports the originals and reports what is redrawn or broken; `tests/test_art.py` keeps them in step
  with the code. Head and body shapes, fur patterns, eyes, role overlays and eggs are still code.
- Browser and sandbox: pictures in the wardrobe, the bazaar and homes (your pet wearing the thing, or standing in the
  place); the diary starts with this life's quests, achievements and ancestors.
- The result of an adventure keeps its picture, and the pet looks happy or sad depending on how it went.
- Between adventures the pet does something that fits its age, not one line for a whole life.
- **17 пригод** (`content/arcs_week_20261112.py`): по одній новій для професій, що мали дві (кухар, діджей, лікар, фермер,
  кур'єр, волонтер, блогер, нічний сторож, екзорцист, покерист), три листопадові (перший сніг, темрява о пів на п'яту,
  зимова гума) і чотири наслідки через роки (шаурмична з генератором, пан Василь, сусід Степан, аукціон на тепловізор).

### Changed
- **The arena is a duel in rounds.** A spar is now up to 7 rounds; every round you pick ⚔️ Удар, 🛡 Захист or 🎭 Хитрість
  (strike beats trick, trick beats guard, guard beats strike), or a named move of the pet's character, or the
  ultimate of its role. What a move does comes from skills, level and worn things: every button shows the damage to
  expect, armour blunts strikes but not tricks, and the screen lists the things that count. Before each round the
  opponent gives itself away with a look that is honest more often for a smart pet (45–80%). The opponent answers
  a repeated move. New in `battle`: `duel`, `duel_round`, `duel_moves`, `duel_tell`, `auto_move`, `Duel`, `MOVES`,
  `DUEL`; `fight` / `resume` are unchanged. In a tournament your own pet's match is a duel too («▶ Бій»); the
  other matches, and everything under «⏭ До фіналу», play by themselves as before. A duel that was left is fought
  out by the pets: there is no second try. Sandbox API: `spar` returns a duel, `spar_move` plays a round, `t_next`
  takes `duel: true`; `spar_tactic` is gone.
- **Scenes step back, the pet stands out.** Outlines in the scenes take the colour of what they outline instead of
  the pet's dark line, and scene colours are a little calmer.
- **One frame per screen in adventures.** The story is plain text in the card, a result is marked by a line on the
  left, choices have no border of their own: no more frame in a frame in a frame.
- **Phones.** The pet card is a strip (portrait, name, health and mood) until «Докладніше про пета» or the «Пет»
  button opens it; the tabs stay at the top while scrolling; after a decision the story is on screen without
  scrolling; larger buttons for choices and tabs.
- **New look of the pets: chibi.** A big head on a small body, flat bold colours with a thin shade line instead of a
  gradient, round eyes with a glint, the face low on the head, a wider blush, whiskers for cat faces. Ears scale with
  the head, the tail moved to the left so that a held thing is visible on the right. Genes, ages, moods, roles and items
  work as before; backgrounds are unchanged. The anchors moved (`sprites.GEOM`, `FACE_DY`), so a picture redrawn for
  the old body has to be redrawn. The old look is the git tag `style-classic`.
- **All 31 scenes are redrawn** in the same flat sticker look as the pets: big simple shapes, a floor band across the
  bottom, the middle left free for the pet. They are pictures in `assets/backgrounds/` (one 48×48 frame each, so scenes
  no longer animate by themselves); night, seasons and weather are still added on top. Delete a file and run
  `scripts/art.py export` to get the code-drawn scene back.
- A pet alone in an adventure now gets the season and the night on outdoor scenes, like two-pet scenes always did.
- `sprites.describe` names the genes in Ukrainian («вуха: звислі», it was «ears: звислі»).

### Fixed
- **The browser game hung on an endless load for a returning player after every new deploy**: the service worker waited
  for the page to reach its cache before giving it to the browser, which stalls Chrome on a page this big.
- «Кексик потрібна довідка» → «Кексикові потрібна», also in the surgery event.
- `scripts/case_scan.py` catches a nominative name before «потрібна / треба / можна…».
- A language review of the oldest content (chains, daily, jobs, life, twists, species, social, status, health), about 150
  fixes: gender pairs that inflected somebody else («Суддя… {випустив|випустила}», «{вилетів|вилетіла} джин»), words that
  fit only a boy pet («Розумник!», «Козак росте!», job names in the job hunt), russisms («білет», «завіщання»,
  «сокамерник», «поварешка», «заглох», «включити»), typos and stories that contradicted themselves (a barista who changed
  sex, a router switched off where «вайфаю немає», «рік життя» for two years).
- Age and state: collectors and «Продати нирку» only for grown-ups, the naked Kupala swim and the garage night only for
  adults, the dating app only without a partner, the blogger's living grandmother closes at 40 like the others.
- «Хай вирішить сам» said to a girl → «Хай вирішить пет». The «Є оновлення гри» banner stays on one line on a phone.

## [0.22.1] — 2026-11-07

### Added
- **Three new recurring characters, each with a quest** (`content/quests.py`, 27 events): пані Ірина, бібліотекарка
  («Бібліотека на Райдужній»: readers, a flood, the district council, money for the roof), дід Петро, голуб'ятник
  («Голуби з даху»: find the champion Сизий, train him, save the dovecote from the ОСББ, the race) and Ярослав
  Іванович, краєзнавець («Карта 1912 року»: a map, a dig permit, a time capsule of 1912, the letter's descendants).
  A quest is a series: episodes months apart, «📺 Раніше», three endings by the hidden scores and a coda years later.
  It starts only for a pet who met the character and did not fall out with them; баба Галя, Мирон, лікар Остап and
  Соломія Андріївна open extra choices on the way, a drone opens a 🔒 choice. In 100 playtest lives about a quarter
  meet each of the pigeon and the map quests and one in ten the library one.

### Changed
- `scripts/playtest_checks.py`: no lifespan>105 lead — long lives are by design.

## [0.22.0] — 2026-11-05

### Fixed (an automated playtest: 140 whole lives, journals read by Haiku, findings verified by Sonnet and by scripts)
- **Grown-up things for kids.** Beer on the bench for 3-year-olds (`soc_meet_bench` → компот), «дружнє пиво» with a
  foe (→ чай), champagne at the prom, cigarettes behind the school, a beer heist (`crime_shoplift` → energy drinks),
  самогон for the pig's uncle and the grandmother's liqueur for appendicitis (now grown-ups only), the night club on a
  15-year-old's date, a positive «try the vape». The kum's самогон tail and the lottery tail need `years=(18, …)`.
- **Romance stays within an age bracket.** `engine.same_bracket`: every event that can start or deepen a romance
  (`engine.ROMANCE`: dates, crush/partner statuses, a baby) is for two teens or two grown-ups; the built-in `_date`
  keeps the proposal and «think about kids» for grown-ups. `soc_baby` is for two adults of working age, not 80-year-olds.
- **Newborns live newborn events.** The baby guard (`engine.for_infants`): under INFANT_YEARS only `baby*` events and
  events whose `years`/`age` start below that age; `family.py`'s age caps no longer open an event to newborns. The
  teacher Соломія Андріївна meets the pet at 6–17, not at 0.
- **«🔒 потрібно 0 ₴ (є −731)»** in debt → «бракує 1031 ₴».
- **«First meetings» only with strangers.** `status=[""]` (the eight `soc_meet_*`) now means never met: a cooled-down
  acquaintance is not a stranger.
- **Tails** may have a req (`(text, fx, weight, req)`): the boss tail needs a job, «коли вже онуки» is for 20–50, and
  «{застряг|застрягла} у ліфті» has a feminine form. «Покликати маму» in a fight is for kids and teens; grown-ups call
  the кум. A random `_date` no longer happens with a rival, an enemy or an ex (the owners can still arrange one).
- Work words for a pet without a job (the alarm story, «завтра на роботу», «продати сало колегам»); a dream event after
  the dream came true; the parents' chat for a pet with no kids; a teen's microcredit shawarma business (grown-ups).
- Text: «Синку»/«синочку» to a girl, «Тихо зник», Барон «{втік|втекла}», «{name} записано», «той {налив|налила}»,
  «грате», «найкращою деревом», «одна одному» for two boys, «ніжно-пастельним» for a girl, the job and the new
  temperament in notes in the pet's gender; money in notes is always whole hryvnias.

### Added
- `scripts/integrity_audit.py --static`: alcohol, tobacco, vape, microcredit and mortgage words a pet under 18 could
  be offered (the youngest age comes from the event's gate, the baby guard, follow-up parents, story openings and
  dream chains), the same for tails; a wider WORK regex (роботу, нарада, «— робота»). Reviewed exceptions:
  `OTHERS["grown_up"]`.
- `scripts/playtest_lives.py` (whole lives through the sandbox → one readable journal per life, 100 lives in ~2 min)
  and `scripts/playtest_checks.py --strict` (deterministic checks over the journals); how to run them and how to brief
  an LLM read: `docs/PLAYTEST.md`.

## [0.21.0] — 2026-11-04

### Added
- **Install as an app, play offline (GitHub Pages build).** `web/manifest.webmanifest`, pixel-cat icons drawn by
  `scripts/make_icons.py` with the game's sprites (`web/icons/`), and a service worker `web/sw.js`: the page is
  network-first with a 3 s timeout, `pyodide/*`, the icons and the manifest are cache-first. `build_web.stamp_sw()` names
  the cache after a hash of the build, so a new deploy drops the old cache; a waiting update is never swapped under a
  running game: a banner «Є оновлення гри» asks first. «📲 Встановити гру» shows up when the browser offers it, iPhones
  get a one-time «Поділитися → На екран „Додому“» hint, and `navigator.storage.persist()` asks Safari not to evict the
  save. All of this runs only on a normal https/localhost origin, never on the Artifact host; the manifest links live in
  `build_web.standalone(page, pwa=True)`, used by `deploy_pages.py`, which also checks that every precached file exists.
- **Save file backup (both hosts).** «💾 Зберегти сейв у файл» downloads `kit-the-cat-YYYY-MM-DD.json`; «📂 Відновити з
  файлу» asks before replacing the game and calls the new `bridge.restore(text)`: the file is untrusted, capped at 5 MB,
  parsed as JSON and checked on a scratch store (format, shapes, every pet loads) before it replaces anything; a broken
  file leaves the current game untouched.

## [0.20.0] — 2026-11-04

### Added
- **Income you can see.** `engine.income_preview(pet)` and `engine.income_line(pet)`; the daily step stores the last payout
  in `pet.flags["_last_pay"]`. `_daily` and the preview share one set of functions (`_base_income`, `_extras`, `_upkeep`),
  the numbers are unchanged. The card and both browser UIs show «💼 Касир АТБ · ≈ +420 ₴/день, побут −60 ₴» (or the
  allowance, pension, pocket money), a toast «💰 Зарплата: +432 ₴ · побут −60 ₴ → 💰 1 872 ₴» once per game day, and the
  job centre says «+2% за кожен день стажу (до +60%)».
- **Items with visible stats and a small effect in adventures.** `content.economy.ITEM_SKILL` (30 items, +2…+5; a generated
  item gives +1), counted by `Pet.skill` while the item is worn, at most +8 per skill (`ITEM_SKILL_CAP`). The wardrobe, the
  shop and the skill chips show «🗡️+6 · 💪+3» (`battle.item_label`). Worn items lift the floor of «стиль» by 2 each.
- **Skills you can read on every check.** Choice buttons show «💪 65%» with a tooltip from `Pet.chance_parts`;
  `chance()` is built from the same pieces (the number is unchanged). The result line reads «🎲 14 · шанс 65% → вдалося ·
  💪 сила 42 (річ +3) проти складності 30», and when a worn item decided a check the result says «🗡 Шабля — дуже до речі»
  (`Result.check`, `Result.helped`).

- **A readable arena fight.** The log now plays at 1.1 s a line (1.6 s for a crit, a special or an ultimate, 0.7 s for a
  miss), the key lines are bold, the HP bars glide, a ticker under them shows «Раунд 4 · 🐷 63 ❤️ · 🐱 41 ❤️», and
  «⏸ Пауза», «⏩ ×2» (remembered) and «⏭ До фіналу» (only the highlights) sit under the log. `BattleResult.highlights`
  (≤ 8 log entries: the opening, the last lead change, crits, specials, ultimates, the finishing blow, the verdict);
  log entries have a kind `k` (`crit`, `miss`, `special`, `ult`, `dot`, `skip`, `tactic`, `surrender`) and an index `i`.
- **One decision mid-fight.** `battle.fight(a, b, rng, stop_at=0.5)` returns a `FightState` when a fighter first
  drops below half health and `battle.resume(state, tactic_a, tactic_b, rng)` plays the rest: «🔥 Ва-банк» (attack +30%,
  defence −30%), «🛡 В оборону» (defence +40%, attack −20%), «🏳 Здатися» (lose now, keep the health). The old one-call
  `fight()` is unchanged; `auto_tactic(fighter)` is what NPCs pick. The sandbox pauses a spar for 20 s (`spar_tactic`;
  the fight id is single-use and belongs to the player who started the spar).
- **A reason to fight.** The result screen lists everything the fight gave (Elo with the new total, XP, strength, mood,
  fame; health for the loser) and the record with the next achievement. `battle.rank(p)` (Новачок / Боєць / Гроза
  району / Легенда арени by Elo), `battle.record(p)`, `battle.next_goal(p)`; the rank is on the pet card. A win gives
  fame +1 (from tier 2 fame pays «реклама» every day), five wins set the flag `arena_vet`, a tournament title
  (`battle.crown`) gives fame +5 and the flag `arena_champ`.
- **6 arena events** (`content/arena.py`): a sports-drink ad, a kid from the yard, a rival at the market, a local
  paper interview, a fan club of two grandmothers, an old coach (for `arena_vet` / `arena_champ`).

- **30 new dates** (`content/dates.py`, ids `dt_*`) and 3 short follow-ups a year later (`fu_dt_*`): strangers and friends
  (5 teen: a school disco, an АТБ queue, a joint project, a rink, the last row of a cinema; 5 grown-up: a blind date,
  a 2017 photo, salsa, a shelter, the night train), a crush (4 teen, 7 grown-up: the Carpathians in the rain, a dinner
  by candles during a blackout, dumplings, IKEA, a dance for the 60+, meteors, a cat café), partners (6: a renovation,
  a ficus, the parents, a day without phones, the place they met, the dacha) and exes (3). Romance stays teen+, couples
  grown-up; a teen date is innocent (nothing above `party=1`, no alcohol, a teen's date is a teen).
- New event attribute `ev(..., date=True)`: marks a romantic scene as a member of the date pool (`engine.is_date_event`).
  `soc_proposal`, `soc_valentine` and `soc_ex_things` are marked; `DATE_HINTS` stays as a fallback for old ids.
- The pair remembers its dates (`Pet.had_date`, flags `dt:<pid>`, 60 per pair): `pick_event(kind="date")` offers a date the
  pair has not had yet before it repeats one, and once they have had all of them, the one longest ago.
- **Skills and items open choices in adventures.** 83 new choices on existing events (`content/gated.py`, appended after the
  old choices): 50 behind a skill (13 🧠, 13 😎, 12 💪, 12 🍀; kids 19–22, teens 21–30, adults 28–52 — set from where real
  pets' skills are) and 33 behind an item the shop sells (guitar, sabre, helmet, book, sunglasses, mic, laptop, monocle…).
  They skip the dice, give a slightly better reward and name the skill or the item in the text.
- **Locked buttons for them.** `Pet.locked_why(e, other) -> [(idx, reason)]` (at most `LOCK_MAX` = 2) lists the choices that
  only a skill, an item or money separate the pet from («потрібно 🧠 40 (зараз 31)», «потрібна річ: 🗡 Шабля», «бракує 300 ₴»);
  role, cast, flag and every other requirement stay hidden. Both browser UIs draw «🔒 label» with the reason under it
  (`pending.locked` is `{i, label, why}` now, was `{i, label, need}`). `Pet.locked` keeps its money-only form.
- **A hint that skills matter.** `Result.hint`: after an event that had a locked choice, 1 time in 3 and at most once per game
  day, «🔒 З 🧠 40 тут був би ще один варіант».

### Changed
- `/pet_date` and the date pool: the built-in `_date` no longer competes with real dates (it was drawn at full weight and
  was the repeat players saw). It is a fallback only for a pair with nothing to do, and now has three variants
  (`_date`, `_date2`, `_date3`) picked at random.
- **Body swap is now visible.** `swap_genes` exchanges the bodies (genes, so the species too — emoji, battle bonuses and
  species events follow the body) and leaves the souls (name, skills, bonds, items). For 3 game days both pets carry
  `flags["_swap"] = [other_pid, until_day, other_gender]`, and the card shows «🔄 У тілі <імені>» (`Pet.swap_label`,
  `Pet.swap_with`). Swapping back while it is on clears the mark. In the sandbox and the browser build the outcome
  gets a highlighted banner («Обмін тілами!») and the avatar flashes and reloads at once; a swap started by a neighbour
  or by the autopilot reaches the other player through `view()["pet"]["news"]` (shown once) instead of going unnoticed.
- «ур.» (a russism) became «рів.» in the card and both UIs.

### Fixed
- A pet of 65 got «a lesson at school». Two causes. (1) A follow-up (`then=("id", "8y")`) came any time in the 15 years
  after it was due, so «the last bell» of a first-grader could ring at 30. Now it has a grace window,
  `max(1 year, half of its delay)` («in 8y» → until +4y); the queue entry is `[id, due, grace]`, and an old two-item entry
  of a saved pet keeps the 15 years. `kid_first_class_fu` also has `years=(13, 19)`. (2) A scalar `stage=2` means
  «12 years and older», not «a teenager»: `teen_vyshyvanka_day`, `soc_teen_cheat/chat/earphone/skip` and
  `hol_valentine_card` (a note in the school bag) now say `stage=(2, 2)`; `teen_uni`, `teen_hair`, `teen_tattoo`
  got `years=` (up to 24). `hol_valentine_single` (the Valentine's event for grown-ups) is twice as likely, since the card is
  for teens now.
- `integrity_audit.py`: a school scene (lesson, homework, test, «до школи», class chat…) in an event that a pet older than
  25 can get is a static problem (a follow-up is also bounded by its parent's age + delay + grace); events that are
  memories, a kid NPC or a classmate met later are listed in `OTHERS["school"]` with the reason. Also: a `kid_`/`teen_`
  event open to a pet older than 25, the oldest pet that lived a school scene, and follow-ups that came more than 3 years
  after they were due (the dynamic part).

## [0.19.1] — 2026-11-04

### Fixed
- The grandmother's 80th birthday came again in every new life of the same player (a pet dies, the heir hatches and
  meets «Бабусі вісімдесят!» once more). `once="dynasty"` marks a family one-off that the heirs remember: the jubilee, the
  cousin's wedding, the two-clubs wedding, the grandmother's recipe, the embroidered shirt in the chest, the
  grandmother's smartphone. `integrity_audit.py` counts the family one-offs a dynasty lived twice (155 of 200 before the fix, 0 now).

## [0.19.0] — 2026-11-04

### Added
- **23 modern events** (`content/modern.py`): the story «Акція в «Аврорі»» (a pot for twelve litres, a cat-shaped kettle,
  three endings and a kettle that comes back for a return), the story «Борщ без сметани» in Threads (a flame war, a poll
  of 41 thousand votes, three endings), the pigeon conspiracy of ЖЕК, a reply guy, a night of scrolling and its
  follow-up, an AI chatbot (a shawarma business plan; a teen's homework), subscriptions, a QR menu, a delivery robot and
  a four-minute voice message.
- New effect `dream="sea"`: the pet's dream comes true if its goal is this one and it is not fulfilled yet. A pet that
  dreams of the sea in Odesa now gets the dream on the Odesa vacation (and on an army leave, a vampire's holiday,
  the Odesa story, the last wish); the same for Mars, the mayor, the drone and the bestseller.
- Jobs can grow a new title with a flag (`titles={flag: (name, name_f)}`): the taxi's radio goes from «Ялинка FM» to
  «Класика FM» after the choice «Вмикати класику, а не шансон».

### Changed
- The taxi driver is «Ялинка FM», not «Шансон FM»; classical music in the car changes it to «Класика FM».
- The family does not live forever (`content/family.py`): events about the pet's mother, father or parents close at
  50 years, those about a living grandmother or grandfather at 40 (a mother no longer calls an 86-year-old to dig potatoes).
- `__version__` of the package matches the release.

## [0.18.0] — 2026-11-03

### Added
- **Life card** («картка життя»): `card.render_life_card(look, summary)` draws a whole life as one PNG — the pet on its
  scene (a ghost at the cemetery for the dead), name, title, cause of death, facts with pixel icons, up to six
  highlights, family and the epitaph. Pure stdlib: a baked bitmap font (`cardfont.py`, Spleen 6×12, BSD-2; regenerate
  with `scripts/bake_font.py`), pixel icons and a zlib PNG encoder, so it needs no Pillow and works in the browser build.
  Both game UIs have a «🖼 Картка життя» button on the screen of a dead pet (sandbox route `/img/card/<owner>.png`,
  browser bridge `card_png`); `tests/test_card.py` checks the PNG and that no letter the game writes is missing from
  the font.

- **Integrity of stories** (`scripts/integrity_audit.py`, `tests/test_integrity.py`): lives of simulated pets are read
  for events that disagree with the state of the pet or come back too often.
- New requirement `tenure=(min, max)`: years in the current job. «Перший тиждень на новій роботі» and «Перша зарплата»
  came 30 years into a job (a hire stamps `flags["_job_y"]`; a pet hired before this version simply never meets them).
- Five jail events (`jail_library`, `jail_lawyer`, `jail_kitchen`, `jail_letter`, `jail_yard`): there were three, so
  every second event behind bars was a repeat.

- **39 social events** (`content/social_more.py`; there were 52, a third of them repeats): sandbox, swing, desk and stickers
  for kids; cheating, prom, class chat and skipping for teens; a queue at Нова пошта, an air-raid shelter, rain, a charger
  and a courtyard for strangers; moving a piano, barbecue, karaoke, secret Santa, pysanky for friends; a drill on Sunday,
  snow, a review for foes; anniversary, dinner, a trip, Valentine's day, an ex's wedding and a box of things for couples.
- New requirement `kids=N` (the pet has had at least N children): grandchildren belong only to a pet that has some.
  «Онуки приїхали на літо» now needs it; `old_yard_kids` is the same story with the yard's children for the childless.
- `integrity_audit.py` also reads the text against the state: a boss, an office or colleagues need a job, grandchildren
  need `kids=`; the simulation lists the events that speak of a job or grandchildren the pet does not have.

### Changed
- Baby events (`baby_*`) have an age window: «перше слово» no longer comes at ten years old, after the first class.
- A pet younger than 3 (`INFANT_YEARS`) lives only events written for its age (an explicit stage, years or phase):
  no pranks, gossip or queues at АТБ for a baby.
- A social event is offered at most twice per life (`SOCIAL_LIFE_MAX`); when the pool of fresh ones is empty the pet lives
  a solo event instead of the same prank again (a third of all social events were repeats).
- «Кинув офіс» (a pet that never had one), a boss who «списує на ремонт офісу», «колеги» in the blood-donation event and the
  quantum boss no longer come to a pet without a job (`job=` or neutral wording); «смартфон від онуків» is from the neighbours.
- «Шлюб врятовано» → «Стосунки врятовано» (a pair is not always married).
- `life_summary` tells a repeating highlight once («мав загинути, але вижив» no longer fills the list three times).

## [0.17.0] — 2026-11-03

### Added
- **Recurring characters** («постійні персонажі», `content/cast.py`): seven people who live next to every pet and
  remember how they were treated — баба Галя (neighbour), лікар Остап (vet), двірняга Гаврик, Оксана з АТБ, пан Богдан
  (colleague), сусід Мирон (garage), Соломія Андріївна (teacher). A pet meets each of them in its own way; every
  decision moves a bond (−6..6), and they age, move away, write letters and come back. 40 events in
  `cast_home.py` / `cast_town.py` (11 follow-ups), e.g. a stairwell neighbour who moves to Poznań and returns, a vet who
  comes at night when the pet's health is low, a dog from the garages who leads the yard, a cashier who opens a bakery.
- New DSL keys: effects `cast={"galya": +1}` (meet or change the bond) and `cast_state={"galya": "away"}`; requirements
  `cast` (bond at least / within a range, the character is around), `cast_state`, `cast_for` (known for N years) and
  `nocast` (not met yet). Contract in `content/dsl.py`, regenerated `docs/DSL.md`, validation of character ids in
  `content/validate.py`.
- `Pet.cast` (new field, old documents load with `{}`), `Pet.meet()`, `Pet.cast_list()`; the sandbox state has `cast`
  and both game UIs show the people in «Навички й статус»; the life summary lists the closest ones. Events about the cast
  come `CAST_BOOST` (×2.5) more often.
- Achievements «Свій у під'їзді» and «Друг з гаражів».
- Tools: `event_coverage.py` and `content_stats.py` understand characters; `tests/test_cast.py`.
- **Series** — serials of 5–8 episodes that come years apart, with a recap («📺 Раніше: …») at the start of each
  episode, hidden scores kept for the whole life and several endings, then a coda («second season») years later.
  Four of them in `content/series.py` (33 events): «Шалаш за гаражами» (childhood, 3 endings + coda), «Лист у
  пляшці» (teen → young, 3 endings incl. a rare one + coda), «Кав'ярня на розі» (adult, 4 endings + coda), «Нічний
  маршрут» (mystic, 3 endings, a rare one gives a coda).
- DSL: effects `ss={"hut.team": 1}` (series scores), `recap=("hut", "line")`, `finale=("hut", "legend")`; requirements
  `ss={"hut.team": 4}` and `finale={"hut": "any"}`; `then=` takes a list of ids and picks the first whose req holds
  (write `ss=` before it) — the ending depends on the scores. `ev(..., series="hut")`, placeholder `{recap_hut}`.
- `Pet.series` (id → ep, vars, recap, end; a new field with a default: old documents load as is), `Result.series`
  (`id`, `title`, `ep`, `finale`, `ending`), the sandbox shows «📺 серія N» on an episode and the ending of a season.
- `validate.py` checks series (ids, endings, recap length, every outcome of an episode goes on or ends).

### Changed
- **Economy: money is a choice, not an accident.** A choice whose every outcome loses money now has a *price*
  (`Pet.price(choice)`): a pet that cannot pay does not get it among `Pet.options()`. `Pet.locked(event, other)` lists
  those choices with the ₴ missing, and the sandbox shows them as locked buttons («🔒 … бракує N ₴»). An autopilot pet
  never picks a choice it cannot pay for. Hosts that draw buttons from `options()` need no change; showing locked ones is
  optional.
- Losses stop at `DEBT_FLOOR` (−500 ₴): what could not be taken becomes consequences (mood, sometimes an item). Debt
  deeper than that exists only as a deliberate loan: the new effect `credit=-1500` (iPhone on credit, mortgage, a new
  loan to close the old one, the café opened on credit, a failed crypto bet), which sets the flag `loan` until the pet is
  back above zero. A dying pet is treated on credit (the doctor does not turn it away).
- `WELFARE` 40 → 65 ₴/day: an unemployed adult can pay the cost of living and slowly climb out of a small debt.
- Every event keeps a choice that costs nothing (`validate.py` checks it; 6 events got one). `arc_wallet_camera`: denying
  everything now costs 70% of the savings and a day in custody instead of a fixed bill of 20 000 ₴.
- `scripts/balance.py` targets: debt share ≤ 10%, median wallet ≥ 500 ₴.
- **Names in the text.** Events and the journal call a pet by its short name («Мурчик»); the tail («Великий»,
  «з Троєщини») stays on the card. The whole name returns only when it would be confusing: the other pet in the scene
  has the same short name, or the pet shares a name with a character it knows. New: `persona.short_name`,
  `Pet.called()`, `Pet.called_in(case)`. New pets get a tail in 30% of cases (was ~80%) and, when possible, a name whose
  short form is not taken by a neighbour.

## [0.16.0] — 2026-11-03

### Added
- Mystic arcs in `arcs_soul.py` (8 events): a mirror in the stairwell and its advice, a magpie that predicts guests,
  Tarot on a night train, a staircase dream and a blue candle during a blackout.

### Changed
- Stories: the rare special endings are now reachable (about 30% of random playthroughs instead of 6–13%): the fox raid
  («greed»), the dog show («Золотий нашийник»), the pickup fundraiser («reach»).
- 54 choices that already granted the **mystic** or **patriot** trait now carry the matching `auto=`, so pets of that
  temperament act in character more often; the personality gaps of `content_stats.py` are closed.

## [0.15.2] — 2026-11-03

### Changed
- Browser game: the gender picker has just ♂ Хлопчик / ♀ Дівчинка (the «🎲 Будь-яка» button is gone); one of them is
  preselected by a coin flip.
- Browser game, UX leftovers of the review: on phones the empty adventure view no longer repeats the «▶ Пригода» button
  the dock already has; the «Грати за» selector has a visible label (wide screens) and a tooltip; the «Казино» button is
  disabled with an explanation while the casino is closed to the pet; lists (bazaar, wardrobe…) no longer scroll inside
  the page; a toast stays up longer when the message is long.

## [0.15.1] — 2026-11-03

### Changed
- Browser game: **«Як це працює»** — a short intro and a legend of the symbols (🎭, the % on a button, ❤️/😊, perks like 🧠+9,
  level, rarity, dream steps, the result chips, the tabs). It opens once on the first visit without a pet, then from the
  «?» button in the header; one column on phones, closes with a tap on the backdrop or Esc. Both pages.
- Browser game, small UX fixes (both pages): the arena hint no longer points at a «⚙️» that does not exist («вкладка «Сусіди» →
  «Заселити 3 сусідів»»); an egg's card shows only «Яйце», not money/level/rarity; «Лікар» is disabled for a healthy pet
  (a mis-tap used to cost mood); the bazaar dims what you cannot afford and says «не вистачає»; the sub-tabs of «Ще…» are
  32 px high.

### Fixed
- Story endings: in a random-picks player, 88% of «Весілля», 72% of «Говерла» and «Кав'ярня» ended in the fallback and the
  special endings were almost out of reach. Thresholds lowered (`st_wedding_end_duty/star` 5→4, `st_coffee_end_hit` 5→4,
  `st_hov_end_rescue` 3→2): wedding 45/39/16%, Говерла 64/23/13%, кав'ярня 49/25/26%. A test now plays every story with
  random picks for both genders and requires every ending to be reachable (≥ 2%) and nobody to die on the way.

## [0.15.0] — 2026-11-03

### Added
- **Event reachability** (`scripts/event_coverage.py`): walks the content like a player who tries every choice and
  outcome, forges a pet for every event's `req`, and says which events can never happen (contradictory `req`, a
  follow-up nobody schedules, story state nothing gives, a follow-up its own root makes ineligible or that comes due at
  the wrong age). `content_stats.py --strict` (and so `content_gate.py`) fails on them. `--sim [--union N]` splits the
  balance run's «never fired» list into categories. Report: `docs/reports/event-coverage.md`.
- `Pet.candidates(other, kind, twist)`: the weighted pool `pick_event` draws from (same weights, now inspectable).
- **Holidays** (`content/holidays.py`, 31 events: 25 + 6 follow-ups): the Ukrainian calendar through `season=`.
  Christmas (вертеп + районний фестиваль, Святвечір з кутею, ярмарок), Щедрий вечір, the New Year tree (+ the yard
  that copied it), Андрія (вишнева гілочка), Valentine's Day (teen+: анонімна валентинка + підпис через рік, вечір «без
  сердець»), Easter (кошик, писанки + писанка на виставці, паска, Подоляночка, реванш крашанками after
  `daily_easter`), День вишиванки, Купала (вінок, цвіт папороті — rare `sparkles@9` —, стрибок через вогонь for two pets),
  День Незалежності (парад вишиванок + фото в музеї, ярмарок «Усе для ЗСУ» + лист подяки), День захисників (волонтерський
  центр + відповідь з війська) and Halloween (костюм з рідкісною роллю вампіра, цукерка чи капость, гарбуз, страшилки).
  Gaps: `patriot` and `mystic` choices.
- Holiday windows `malanka` (12–14 Jan), `vyshyvanka` (15–21 May: the third Thursday), `pokrova` (12–16 Oct) for `req=dict(season=…)`;
  `dsl.SEASONS` lists every valid value and `content.validate` rejects an unknown one (a typo used to make an event
  silently dead).
- `tests/test_holidays.py`: every window holds its dates; every holiday event is eligible in its days and not in September.
- **Видові пригоди й арки** (`content/species_more.py`, 32 події, по 4–5 на кожен вид): лис — історія «Набіг на курник»
  (жадібність, пес Бровко, наслідок через роки); кіт — історія «Котяче пограбування» (Зломщик / Відволікач / Технар) і подкаст
  дільничного; свиня — «Рити» (трюфель, клумба біля мерії, монета з наслідками) і дегустація соусу; пес — історія
  «Виставка «Золотий нашийник»» (догляд проти «Найщиріший погляд»); кінь — гурток верхової їзди (+ вершниця через
  8 років), весілля, електропастух, Купала; аксолотль — заплив «Дніпрова хвиля» (+ реванш), біологи, світний ставок;
  птах — годівничка взимку (+ весняний садочок), птахи на дротах, кільцювання (+ лист з маршрутом).

### Fixed
- Language and logic review of the 0.13.0 «побут» events (`arcs_week_20261102.py`; ids unchanged): «Борщ» → «Бограч» in the
  bograch story, «той, хто приносить капусту» / «не одеський» / «шерсть» / «для кота» (wrong for a girl or another species),
  «в кухні», «першою чи після кави», «змагання у танцях», «чаєм з малиною», «Дві посилки… обидві чужі», the heating chat no
  longer calls the pet its founder when the pet only went to the housing office, a failed Lviv password no longer throws
  the pet out before the café scene, and the like. Seasonal sense: the Odesa story is summer/early-autumn, the bograch
  festival May–October; `clean=-5` removed from the exploding jar.
- **The favourite food is declined.** `{food}` was always the accusative, so 22 texts said «Головне — шаурму»,
  «Вам би поменше шаурму», «банок з-під шаурму», «ящик борщ». New placeholders `{food_nom}`, `{food_gen}`,
  `{food_dat}`, `{food_ins}`, `{food_loc}` from a hand-written table (`persona.FOOD_FORMS`, `persona.food_in`); `{food}`
  stays the accusative. Old pet documents keep their stored `persona.food`; a food missing from the table is used as
  it is. Texts with an agreeing adjective or verb («домашній {food}», «{food} дарує») were rephrased, since a food can
  be plural. `scripts/food_scan.py` is a new gate in `content_gate.py`. The food «кулешик» (a russism) is now «куліш»;
  pets that already have the old word keep it in every case.
- Sandbox: a neighbour's story stopped after its second step (the auto-resolve of a pending step cleared the next step
  it had just started); stories now finish for NPCs.
- `balance.py` is reproducible: the sandbox clock was real time (season, holidays, hour of the day and the seconds the
  run took leaked into the result — `check_success` jumped between 62% and 72%), `Pet.hatch` used the global random.
  `Sandbox(..., epoch=)` gives a purely virtual clock; `balance.py --start YYYY-MM-DD` picks the simulated date.

## [0.14.0] — 2026-11-02

### Added
- **Inner voice of the temperament**: over about 40% of events the pet's character says one line —
  «🎭 хуліганка: «Правила — це рекомендації для тих, хто боїться.»». 36 temperaments × 6 lines
  (`content/voices.py`); when a choice is in character (🎭) the voice often leans towards it. Never over grave events
  (death, hospital, jail, a big health hit, the army: `engine.is_grave_event`). `Pet.inner_voice(e, other)`; the
  sandbox state has `pet.pending.voice`; both pages show it. Hosts: show `p.inner_voice(e, other)` under the event text (a no-op on older games:
  guard with `getattr`).

## [0.13.0] — 2026-11-02

### Added
- **Побут і календар** (`arcs_week_20261102.py`): «Опалювальний сезон» (+ чат стояка), «Борщ із квасолею чи без» (+ дворовий
  фестиваль), «Закрутки» (+ вибухова банка), Святий Миколай, Масляна, Водохреща, ожеледиця.
- **Цифрова дрібниця**: «Дія» без потрібної довідки (+ довідка на ім'я кума), зум із бабусею (+ сімейний зум), поштомат із чужою посилкою.
- **Чотири короткі історії про регіони** (3 кроки, 3 кінцівки кожна): «Одеський привіз», «Бограч на фестивалі»
  (Закарпаття), «Кав'ярня з паролем» (Львів), «Два клуби на весіллі». Без війни, переселенців і шахраїв.

## [0.12.1] — 2026-10-30

### Fixed
- Language: «Перепідарувати чужий подарунок» → «Передарувати…»; the four events that put a fear into the wrong case
  («що огірків заважає жити») now say «страх {fear}»; «мерка» → «міська голова»; «командир черги»,
  «Кримінальна лідерка»; `ua_lint` flags «перепідар*» and «сперечальник*».
- Language, review pass over the new feminine forms: «нащадкиня», «добровольчиня», «шефиня», «сіра еміненція»,
  «екомажор», «криптоінфлюенсер», «фітнес-тренер», «охоронниця скарбу», «єдинорогиня», «гніда» (not «вороная»),
  «старша по камері»; the unused case of «хтось» in `NOBODY.loc`.

## [0.12.0] — 2026-10-30

### Added
- **The story «Холостяк / Холостячка»** (phase 4): a TV dating show with the pet as its star, five decisions in a row
  (casting, limousine and the first rose, a group date in the Carpathians, a leaked-chat scandal, meeting the
  parents) and six endings picked by hidden scores (heart, show, drama): «Справжнє кохання», «Шоу-зірка», «Скандал
  сезону», a quiet one, and a secret one that needs the third rose at the very start. A boy's season is «Холостяк»,
  a girl's is «Холостячка» (the contestants are the other sex). «Піти на Холостяка» in `blog_viral` now sends the pet
  to the casting (`tv_cast`); a charming pet (cha 60) can be scouted on the street. New achievements «Остання
  троянда» and «Зірка реаліті». Story titles are now formatted like any text (`Pet.fmt`), which also fixes
  «{Застряг|Застрягла} у ліфті».
- **Pets have a gender** (phase 2; texts are not converted yet): `Pet.gender` `"m"` | `"f"` (saved in the document; old
  documents load as `"m"`), `new_pet(..., gender=None)` (a coin flip; an heir gets a fresh one). Name pools are split
  into boys' and girls' (≥ 12 each per species, `make_name(..., gender)`), tails agree with the gender («Мурка
  Велика», «Мурчик Великий»), names decline by gender (a feminine name on a consonant stays indeclinable).
- **Gender pairs in texts**: `{вилупився|вилупилася}` for the pet and `{other:відмовив|відмовила}` for the other pet,
  resolved by `Pet.fmt` before the name is substituted (`grammar.pick`); `content/validate.py` rejects a malformed
  pair. Epitaphs, role names/descriptions (Вампірка, Перевертниця…), relationship words (подруга, суперниця…),
  species words (Кішечка) and 70 achievement titles (`ACH_F`, shown through `Pet.ach_name`) have feminine forms.
- **Browser game: choose the gender** (phase 5): under the species buttons — ♂ Хлопчик / ♀ Дівчинка / 🎲 Будь-яка
  (default 🎲, a coin flip); the card shows a small ♂/♀ next to the name. The sandbox API `create` takes an optional
  `gender` (`"m"` | `"f"`), the state has `pet.gender`; both pages (`sandbox/static/index.html`, `web/index.html`) updated.
- API: `Pet.g`, `Pet.role_name`, `Pet.role_desc`, `Pet.ach_name`, `engine.role_name/role_desc/status_name/species_name`.
  Breaking for hosts that read the data directly: `persona.NAMES[species]` is `{"m": …, "f": …}`, `NAME_SUFFIX` holds
  `(masculine, feminine)` pairs, `FALLBACK_NAMES` is split by gender.

- **The texts speak about a girl in the feminine** (phase 3): ~1100 masculine words about the pet in 698 events and
  the engine's notes became `{знайшов|знайшла}` pairs (verbs, predicate adjectives, «Ти — {герой|героїня}»,
  «{Депутат|Депутатка} {name}», `{other:…|…}` for the other pet); death causes, epitaphs, life-summary titles,
  casino/world/care/battle texts, temperaments (`TEMPER_F`), tier titles (`TIER_F`), life stages (`STAGES_F`) and job
  names (`name_f` in `economy.JOBS`, `Pet.job_name`) have feminine forms. New `scripts/gender_scan.py` finds the
  masculine words that are left; its `--strict` is a gate in `content_gate.py` (`scripts/gender_allow.txt` lists the
  sentences that are about somebody else). Achievement keys stay masculine; `content/validate.py` measures texts as the
  player reads them.

### Fixed
- **Pet names are declined**: «Під дверима Крилатий з Троєщини пищить кошеня» is now «Під дверима Крилатого з
  Троєщини…». New `grammar.py` (`decline`, `inflect`) gives all seven cases of a name (adjectives, nouns on a
  consonant / «-ь» / «-й» / «-о» / «-а» / «-я»; a tail after «з», «із», «від», «№» stays as it is; indeclinable and
  foreign words stay put). Texts use `{name_gen}`, `{name_dat}`, `{name_acc}`, `{name_ins}`, `{name_loc}`,
  `{name_voc}` and the same `{other_*}`; `{name}` is still the nominative, so old content and hosts keep working.
  About 300 texts and the engine's notes were moved to the right case; `scripts/case_scan.py` lists the doubtful
  ones and its `--strict` check (a preposition right before `{name}`) is part of `content_gate.py`.

## [0.11.3] — 2026-10-29

### Changed
- **Thinner frames**: buttons, cards, fields, the menu, toasts and the header/dock lines use 2 px borders instead of
  3 px; the dialog's double frame is 9 px wide instead of 12 px.
- **Choices look like buttons**: each choice is a framed tile with an always-visible ▶ (before, the cursor showed only
  on hover, so on a phone the choices read as plain text); hover/focus highlights it, a press sinks it, and «Хай
  вирішить сам» has a dashed frame.

## [0.11.2] — 2026-10-29

### Changed
- **No pixel type in anything you read**: buttons, the menu, the pet's name, story titles and numbers use the system
  font too (sentence case instead of capitals); only the «Kit the Cat» logo keeps the pixel typeface. The pixel look
  stays in the graphics: sprites, dialog frames, segmented meters, the ▶ cursor and bevelled buttons.

## [0.11.1] — 2026-10-29

### Changed
- **Easier to read**: the pixel typeface stays on the title, the pet's name, buttons, the menu, story titles and
  numbers; the story text, choices, results, journal and notes use the system font, a little larger (17 px in the
  dialog) with more line spacing.

## [0.11.0] — 2026-10-29

### Changed
- **The browser game looks like a pixel RPG**: one night palette, the Pixelify Sans pixel typeface everywhere
  (bundled in `web/fonts/`, embedded in the page — the game still works offline and contacts no font server), the
  scene on a stage at the top and the story in a dialog box with a ▶ cursor on the choice, health and mood as
  segmented pixel meters (blinking when low), bevelled pixel buttons, the tab menu with a ▶ marker. Replaces the
  exercise-book look from 0.10.0.
- **Fits every common screen**: the scene's height follows the screen height, so the story and all choices fit
  without scrolling from 1280×720 up; on monitors 1600 px and wider the layout is wider (1360 px) with larger text;
  tablets in portrait (up to 900 px) get the phone layout with the bottom dock. Checked at 1280×720, 1366×768,
  1440×900, 1536×864, 1920×1080, 2560×1440, 1024×768, 768×1024, 375×812, 390×844 and 412×915.
- The menu lost its emoji and the theme toggle (the game has one deliberate night theme).

### Added
- **MIT licence** (`LICENSE`, also in the package metadata): free to use, change and share, provided as is; no
  support is promised. The README and the game menu say so.

## [0.10.0] — 2026-10-29

### Added
- **10 more stories** (`content/stories_more.py`): «Дванадцять годин без світла», «Застряг у ліфті», «Перший
  тиждень» (new job), «Говерла», «Ремонт у ванній», «Бабусин ювілей» and «Пропав пес» (kids too), «Перше
  побачення» (teens), «Черга на кордоні», «Кава з собою». 18 stories in all; new achievements «Підкорив Говерлу»,
  «Знайшов Барона», «Своя кав'ярня». Pricey choices are hidden from pets who can't afford them.

### Changed
- **The browser game has its own look instead of a generic app style**: a squared school exercise book by day
  (ballpoint-blue ink, the red margin line, the adventure written on squared paper in a book serif) and the school
  chalkboard by night (chalk text, chalk-yellow accent); square corners and pressed buttons to match the pixel
  sprites; notebook-style tabs; words instead of emoji in the interface («Лікар», «Казино», «Ще…», «Меню»); stats as
  plain text with tabular numbers instead of pills; no accent bars on rounded cards; the journal tab is «Щоденник».
  On wide screens the scene picture is capped so the story text stays in view.

### Fixed
- A story no longer breaks when a choice's hidden time makes the pet grow up in the middle of a step (the answered
  event was still pending while the age checks ran).

## [0.9.1] — 2026-10-29

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

[Unreleased]: https://github.com/ifurs/kit-the-cat/compare/v0.23.1...HEAD
[0.23.1]: https://github.com/ifurs/kit-the-cat/compare/v0.23.0...v0.23.1
[0.23.0]: https://github.com/ifurs/kit-the-cat/compare/v0.22.1...v0.23.0
[0.22.1]: https://github.com/ifurs/kit-the-cat/compare/v0.22.0...v0.22.1
[0.22.0]: https://github.com/ifurs/kit-the-cat/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/ifurs/kit-the-cat/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/ifurs/kit-the-cat/compare/v0.19.1...v0.20.0
[0.19.1]: https://github.com/ifurs/kit-the-cat/compare/v0.19.0...v0.19.1
[0.19.0]: https://github.com/ifurs/kit-the-cat/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/ifurs/kit-the-cat/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/ifurs/kit-the-cat/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/ifurs/kit-the-cat/compare/v0.15.2...v0.16.0
[0.15.2]: https://github.com/ifurs/kit-the-cat/compare/v0.15.1...v0.15.2
[0.15.1]: https://github.com/ifurs/kit-the-cat/compare/v0.15.0...v0.15.1
[0.15.0]: https://github.com/ifurs/kit-the-cat/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/ifurs/kit-the-cat/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/ifurs/kit-the-cat/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/ifurs/kit-the-cat/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/ifurs/kit-the-cat/compare/v0.11.3...v0.12.0
[0.11.3]: https://github.com/ifurs/kit-the-cat/compare/v0.11.2...v0.11.3
[0.11.2]: https://github.com/ifurs/kit-the-cat/compare/v0.11.1...v0.11.2
[0.11.1]: https://github.com/ifurs/kit-the-cat/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/ifurs/kit-the-cat/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/ifurs/kit-the-cat/compare/v0.9.1...v0.10.0
[0.9.1]: https://github.com/ifurs/kit-the-cat/compare/v0.9.0...v0.9.1
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
