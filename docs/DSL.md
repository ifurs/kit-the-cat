# Довідник DSL пригод

> Згенеровано `scripts/gen_dsl_docs.py` з коду — не редагуй вручну. Як писати гарні пригоди: [CONTENT_GUIDE.md](CONTENT_GUIDE.md).

Контракт: **61 ефектів**, **40 вимог**, ролі: alien, angel, cyborg, demon, quantum, vampire, werewolf, zombie. Рушій гарантовано підтримує кожен ключ; невідома вимога = подія недоступна.

## Синтаксис (з `content/dsl.py`)

```text
Tiny DSL for writing life events.

    ev("found_wallet", "{name} знайшов гаманець…",
       ch("Віднести в поліцію", o("Поліцейський забрав його собі.", love=2, mood=-5), auto="love"),
       ch("Забрати гроші", o("+500 ₴, але совість гризе.", money=500, toxic=1), auto="toxic"),
       ch("Купити лотерейки", o("Джекпот!", money=5000), check=("luck", 70),
          fail=[o("Нічого не виграв.", money=-50)], auto="gambler"),
       req=dict(stage=2))

Names are declined, not pasted: «{name}» is the nominative («Крилатий з Троєщини» is the subject), every other
role takes its own case — {name_gen} «Крилатого з Троєщини» (нема кого?, у/до/від/для/без/біля/про…), {name_dat}
(кому?), {name_acc} (кого?), {name_ins} (з ким? — «з {name_ins}»), {name_loc} (на/у/при кому?), {name_voc}
(«Ей, {name_voc}!»); the same for {other_gen} … {other_voc}. «До {name} прийшов кур'єр» is a bug, «До {name_gen}
прийшов кур'єр» is right; scripts/case_scan.py lists the suspicious ones. The rules live in grammar.py.

The favourite food is declined the same way, from a hand-written table (content/persona.py FOOD_FORMS): «{food}» is
the accusative, as it is stored («їсть {food}», «піти по {food}», «Принести лікарю {food}»), and the other cases are
{food_nom} («Головне — {food_nom}»), {food_gen} («поменше {food_gen}», «ящик {food_gen}», «банок з-під {food_gen}»),
{food_dat}, {food_ins} («подякувати {food_ins}») and {food_loc} («у {food_loc}»). A food can be plural
(«вареники з вишнями», «чебуреки з вокзалу»), so never put a verb or an adjective that agrees with it next to the
placeholder («{food} дарує» is a bug; «порція {food_gen}» is right); scripts/food_scan.py lists the suspicious ones.

Pets are boys or girls (Pet.gender "m" | "f"), and a text speaks about both: a word that changes with the gender is a
pair, «{вилупився|вилупилася}» (the first for a boy, the second for a girl), «{other:відмовив|відмовила}» for the other
pet of a social event. Exactly two alternatives, no braces, colons or bars inside them; the validator checks it.
Rephrasing into something gender-neutral is often nicer than a pair. Do not put pairs in a name or a {placeholder}.

Time: every decision costs some of the pet's life, and the player never sees how much (no time on buttons).
A choice costs `time` if it has one, else `infer_time(choice, base)` — the event's / module's base plus what the
choice does (studying, settling into a job, moving, a serious relationship, a story step, skills learned, money
earned). Give `time=` to the choices whose cost is obvious from the story: «Вступити в КПІ» → "4y", «Купити
хліб» → "1d". An outcome may cost extra: o("Прокинувся через п'ять років…", time="5y"). Jail and hospital eat
life too. Durations: "3d", "2w", "6m", "4y" or a number of years. On top of that the clock ages pets slowly.

Effects (o(..., **fx)):
  hunger mood clean health energy      stat deltas (0..100); hunger/clean/energy are automatic upkeep — use
                                       mood and health in new content
  fame auth blat fin attr              life stats 0..100 with tiers (engine.LIFE): популярність, авторитет, блат,
                                       фінграмотність, привабливість (style and charm, never mocking looks)
  time="5y"                            extra life time this outcome costs (coma, a sentence, cryosleep)
  str int cha luck                     skill deltas
  toxic gambler dark party patriot glutton love mystic   trait deltas
  money xp lifespan                    ₴, experience, years of life. A loss never digs deeper than engine.DEBT_FLOOR (−500):
                                       the rest is written off (mood, sometimes an item). A choice whose every outcome
                                       loses money is a PRICE: the pet cannot pick it without the money (engine.price)
  credit=-1500                         a loan the pet takes on purpose: ignores the debt floor and marks the pet as
                                       «у кредиті». Only in events/choices about кредит/борг/позика/розстрочка
  item="cowboy@6" | ["a", "b"]         give & equip;  item_slot="head" → random item for slot
  lose_item="random" | "id"            take away
  unequip="head" | "all"               take off what is worn in that slot (or everything); items stay owned
  flag={"crime": 2}  unflag="crime"    story flags (quest chains)
  job="it" | job=""                    hire / fire
  edu="kpi"                            diploma
  home="palace"                        move (background)
  jail=48 | hospital=24                hours (outfit + background while there)
  die="cause"                          death
  achievement="…"
  money_mult=0.5                       multiply money (0 = lose everything)
  free=True                            released from jail
  gene={"extra": "fangs"}              set genes directly (sprite changes!)
  mutate=2                             randomly mutate N visible genes
  species="fox"                        transform into another species (keeps colour, swaps parts)
  role="vampire" | role=""             supernatural role (see engine.ROLES) / cure
  reroll_persona=True                  amnesia: new temperament, dream, fear, quirk
  twist=True                           marks the outcome as a plot twist (announced louder)
  then=("fu_kum_returns", "2y")        schedule a follow-up event after that much of the pet's life: earlier
                                       choices come back (the follow-up must be an ev(..., followup=True))
  step="st_alarm_2" | ["a", "b"]       story: the next step comes right away (no 🎲). A list = the first step whose
                                       req (usually sv=) holds; the last one is the fallback. Steps are
                                       ev(..., story="Назва", followup=True); the first step has story= only
  sv={"kind": 1, "risk": 2}            story variables: hidden scores the later steps and the ending read (sv=)
  cast={"galya": 2}                    a recurring character (content/cast.py CAST): met for the first time (bond 0) and
                                       the bond moves by that much (−6..6); the pet remembers how they were treated
  cast_state={"galya": "away"}         where the character is now: "here" (default), "away" (moved, may come back),
                                       "gone" (for good). Only for a character the pet has met
  ss={"bus.trust": 1}                  series scores: "<series>.<score>" is kept for the whole life, between episodes,
                                       unlike sv= (episodes are far apart in time; see content/series.py)
  recap=("bus", "пустили на ніч")      one line of «Раніше в серіалі» (≤ 90 chars, no name needed); a later episode shows
                                       the last four through {recap_bus} at the start of its text
  finale=("bus", "good")               the series (season) ends with this ending tag (a key of its `ends`)
  then=(["bus_end_a", "bus_end"], "1y")  a list of ids picks, right now, the first whose req holds (ss= first!);
                                       the last is the fallback (no ss= in its req): the ending depends on the scores
  # social events only:
  rel=+10  status="friend|bestie|rival|enemy|crush|partner|ex"  other={...effects for the other pet}
  baby=True                            the couple gets an heir egg (hybrid genes)
  swap_genes=True                      body swap: the two pets exchange looks

Requirements (req=dict(...)):
  stage=2 | (2, 3)   species="pig"   flag="crime" | flag={"crime": 2}   noflag="crime"
  tenure=(0, 1.5)    years in the CURRENT job (min, max): «перший тиждень на новій роботі» needs it, else it would come
                     after thirty years of work; a pet without a job (or hired before 0.18) never meets it
  trait={"toxic": 10}   skill={"int": 30}   money=100   job="it"|"any"|"none"   edu="kpi"   noedu="kpi"
  has="sabre"   partner=True|False   night=True   jail=True (only while jailed)
  status=["crush"] (social: relation with the other pet)   other_stage=2   age=(min_days, max_days)
  debt=500 (money <= -500)   low={"health": 40}   role="vampire" | role="any" | norole=True
  other_role="vampire"   nostatus=[...]   other_partner=False   other_stage_max=2
  life={"fame": 40} (life stat at least)   tier={"fame": 2, "money": 3} (tier at least; money tiers too)
  tier_max={"auth": 0}   years=(18, 60) (age in years)   goal="mayor" (the pet's dream, persona.GOALS)
  sv={"kind": (2, 9)} (story variables of the story being played, at least / within a range)
  cast={"galya": 2} | {"galya": (-6, -2)}   the pet knows the character, who is around ("here"), and the bond is at
         least that / within the range (negative bonds are grudges); cast_state={"galya": "away"} asks for another state
         instead; cast_for={"galya": 8} (known for at least that many years); nocast="galya" | [ids] (not met yet)
  ss={"bus.trust": 2} | {"bus.trust": (2, 9)} (series scores, at least / within a range)
  finale={"bus": "good"} | {"bus": "any"} (the series has ended with that ending / with any)
  phase="young" | ["young", "middle"]   life phase by age: kid 0–12, teen 12–18, young 18–30, middle 30–60, grand 60+
  season="winter|spring|summer|autumn" | holiday (newyear christmas andriy easter kupala halloween valentine
         independence malanka vyshyvanka pokrova) | list of those | month numbers (real Kyiv date)
```

## Підстановки в тексті

| Підстановка | Що це |
|---|---|
| `{name}` | ім'я пета |
| `{owner}` | ім'я власника |
| `{food}` | улюблена їжа пета, знахідний (їсть кого? що? — «шаурму») |
| `{dream}` | мрія |
| `{fear}` | страх |
| `{quirk}` | дивна звичка |
| `{temper}` | темперамент |
| `{money}` | гроші пета (число) |
| `{role}` | назва ролі за статтю пета (🧛 Вампір / 🧛 Вампірка…) |
| `{other}` | ім'я іншого пета (лише social) |
| `{other_owner}` | власник іншого пета (лише social) |
| `{name_gen}` | ім'я пета в родовому відмінку (немає кого? — «Мурки») |
| `{name_dat}` | давальний (кому? — «Мурці») |
| `{name_acc}` | знахідний (кого? — «Мурку») |
| `{name_ins}` | орудний (з ким? — «Муркою») |
| `{name_loc}` | місцевий, без прийменника (на кому? — «Мурці») |
| `{name_voc}` | кличний (Ей, «Мурко»!) |
| `{food_nom}` | їжа в називному (що? — «шаурма», «вареники з вишнями») |
| `{food_gen}` | родовий (нема чого? — «шаурми») |
| `{food_dat}` | давальний (чому? — «шаурмі») |
| `{food_ins}` | орудний (з чим? — «шаурмою») |
| `{food_loc}` | місцевий, без прийменника (на чому? — «шаурмі») |
| `{other_gen}…{other_voc}` | ті самі відмінки для імені іншого пета (лише social) |
| `{recap_hut}` | «Раніше в серіалі…» — до чотирьох останніх рядків `recap=` серіалу `hut` (порожньо до першої серії) |
| `{він\|вона}` | слово за статтю пета: перша частина для хлопчика, друга для дівчинки («{вилупився\|вилупилася}») |
| `{other:він\|вона}` | те саме за статтю іншого пета (лише social; без іншого пета — перша частина) |

## Стати, навички, риси

| Ключ | Що це |
|---|---|
| `hunger` | 🍖 |
| `mood` | 😊 |
| `clean` | 🧼 |
| `health` | ❤️ |
| `energy` | ⚡ |

| Навичка | Значок |
|---|---|
| `str` | 💪 |
| `int` | 🧠 |
| `cha` | 😎 |
| `luck` | 🍀 |

| Риса | Назва |
|---|---|
| `toxic` | 🤬 токсичність |
| `gambler` | 🎰 азарт |
| `dark` | 💀 темрява |
| `party` | 🌙 тусовки |
| `patriot` | 🇺🇦 патріотизм |
| `glutton` | 🍔 ненажерливість |
| `love` | 💖 ніжність |
| `mystic` | 🔮 містика |

## Життєві стати (`fame`, `auth`, `blat`, `fin`, `attr`) і рівні

Значення 0–100; рівні з порогами 0 / 20 / 45 / 70 / 90. Вимога `tier={"fame": 2}` = щонайменше 2-й рівень (рахуємо з 0). Гроші теж мають рівні (`tier={"money": 3}`).

| Ключ | Що це | Рівні |
|---|---|---|
| `fame` | 📈 популярність | Ніхто → Зірка під'їзду → Мікроблогер → Медійна персона → Зірка Євробачення |
| `auth` | 🕶 авторитет | Чистий перед законом → Хуліган з району → Решала → Авторитет → Хрещений батько |
| `blat` | 🤝 блат | Ніхто нікого не знає → Кум у ЦНАПі → Свій у міськраді → Людина зі зв'язками → Телефонне право |
| `fin` | 📊 фінграмотність | Гроші під матрацом → Знає, що таке відсоток → Веде таблицю витрат → Інвестор → Фінансовий гуру |
| `attr` | ✨ привабливість | Звичайний → Охайний → Стильний → Красунчик району → Ікона стилю |
| `money` | 💰 статки (₴) | 🕳 У боргах (<0) → 🥫 Бідний студент (≥0) → 🧾 Середній клас (≥1000) → 🚗 Мажор (≥5000) → 🛥 Олігарх (≥20000) |

Високі рівні приносять дохід (реклама, «дах», відсотки, зарплата з блатом) і ризики (облави, НАБУ, скандали, податкова). Привабливість підсилює ріст популярності, фінграмотність зменшує втрати грошей.

## 🎰 Казино (дія, не DSL)

| venue | Назва | Рівень статків | Ставка ₴ | Час |
|---|---|---|---|---|
| `underpass` | 🎰 Автомати в переході | 1 | 20–300 | metro |
| `bukovel` | 🎲 Казино в Буковелі | 2 | 300–5000 | bukovel |
| `private` | 🃏 Закритий покер олігархів | 4 | 5000–50000 | casino |

## Етапи життя

| stage | Назва | Від віку (років) |
|---|---|---|
| 0 | 🥚 Яйце | яйце ~1 год |
| 1 | 👶 Малюк | 0 |
| 2 | 🧒 Підліток | 12 |
| 3 | 🧑 Дорослий | 18 |
| 4 | 👴 Старий | 60 |

## Ролі (`role=`)

| role | Назва | Назва (дівчинка) | Пасивка |
|---|---|---|---|
| `vampire` | 🧛 Вампір | 🧛 Вампірка | голод майже не мучить, вдень депресує, вночі — король. Кусає ворогів. |
| `werewolf` | 🐺 Перевертень | 🐺 Перевертниця | сильний, а вночі злий і ще сильніший. |
| `zombie` | 🧟 Зомбі | 🧟 Зомбі | не лікується сам, зате майже не вмирає з голоду й живе довше. |
| `demon` | 😈 Демон | 😈 Демониця | токсичнішає щодня, але гроші до нього липнуть. |
| `angel` | 😇 Ангел | 😇 Ангел | лікує друзів, ніжнішає, приносить удачу в любові. |
| `cyborg` | 🤖 Кіборг | 🤖 Кіборг | не старіє, розумніший, їсть менше. Боїться відключень світла. |
| `alien` | 👽 Іншопланетянин | 👽 Іншопланетянка | з ним щодня трапляється щось дивне. |
| `quantum` | ⚛️ Квантовий | ⚛️ Квантова | існує в суперпозиції: 50% пережити будь-яку смерть. |

## Стосунки (`status=`)

| status | Назва | Назва (дівчинка) |
|---|---|---|
| `friend` | 🤝 друг | 🤝 подруга |
| `bestie` | 💛 найкращий друг | 💛 найкраща подруга |
| `rival` | 😤 суперник | 😤 суперниця |
| `enemy` | ⚔️ ворог | ⚔️ ворогиня |
| `crush` | 😳 закоханість | 😳 закоханість |
| `partner` | 💍 партнер | 💍 партнерка |
| `ex` | 💔 колишній | 💔 колишня |

## Сезони й свята (`season=`)

| season | Вікно (місяць, день) |
|---|---|
| `newyear` | (12, 20) → (1, 14) |
| `christmas` | (12, 20) → (1, 10) |
| `andriy` | (12, 8) → (12, 16) |
| `easter` | (3, 25) → (5, 10) |
| `kupala` | (6, 20) → (7, 10) |
| `halloween` | (10, 25) → (11, 2) |
| `valentine` | (2, 10) → (2, 16) |
| `independence` | (8, 20) → (8, 27) |
| `malanka` | (1, 12) → (1, 14) |
| `vyshyvanka` | (5, 15) → (5, 21) |
| `pokrova` | (10, 12) → (10, 16) |
| `winter` | 12, 1, 2 |
| `spring` | 3, 4, 5 |
| `summer` | 6, 7, 8 |
| `autumn` | 9, 10, 11 |

## Роботи (`job=`)

| job | Назва | ₴/день | Вимоги |
|---|---|---|---|
| `atb` | 🛒 Касир АТБ | 120 | — |
| `courier` | 🛵 Кур'єр на самокаті | 150 | {'skill': {'str': 15}} |
| `taxi` | 🚕 Таксист «Шансон FM» | 170 | — |
| `cook` | 🌯 Кухар у шаурмичній | 150 | — |
| `farmer` | 🚜 Фермер | 170 | {'skill': {'str': 25}} |
| `it` | 💻 Айтішник | 380 | {'skill': {'int': 45}} |
| `blogger` | 📸 Блогер | різна | {'skill': {'cha': 35}} |
| `dj` | 🎧 Діджей | 240 | {'trait': {'party': 15}} |
| `witch` | 🔮 Потомствена ворожка | 200 | {'trait': {'mystic': 15}} |
| `doctor` | 🩺 Лікар | 340 | {'edu': 'med'} |
| `volunteer` | 🇺🇦 Волонтер | 60 | {'trait': {'patriot': 15}} |
| `deputy` | 🏛 Депутат | 350 | {'flag': 'politics'} |
| `bandit` | 🕶 Бандит | 400 | {'flag': 'crime'} |
| `poker` | 🃏 Професійний покерист | різна | {'skill': {'luck': 40}} |
| `prophet` | 🕯 Пророк секти | 450 | {'flag': 'cult'} |
| `astronaut` | 👨‍🚀 Космонавт | 600 | {'flag': 'space'} |
| `military` | 🪖 Захисник | 300 | {'flag': 'army'} |
| `night_guard` | 🌙 Нічний сторож на кладовищі | 260 | {'role': 'any'} |
| `exorcist` | ✝️ Екзорцист за викликом | 320 | {'trait': {'mystic': 30}} |

## Освіта (`edu=`)

| edu | Назва |
|---|---|
| `school` | 🏫 Атестат (з трійками) |
| `ptu` | 🔧 Диплом ПТУ |
| `kpi` | 🎓 Диплом КПІ |
| `mohyla` | 📜 Диплом Могилянки |
| `med` | ⚕️ Медичний |
| `courses` | 💾 Курси «Айті за 2 тижні» |
| `hogwarts` | 🧙 Заочна школа магії |

## Їжа

| id | Назва | Ціна ₴ |
|---|---|---|
| `crust` | 🍞 Хліб з водою | 0 |
| `mivina` | 🍜 Мівіна | 10 |
| `salo` | 🥓 Сало | 30 |
| `varenyky` | 🥟 Вареники | 35 |
| `borsch` | 🍲 Борщ | 40 |
| `beer` | 🍺 Пиво | 45 |
| `salad` | 🥗 Салатик | 50 |
| `shrooms` | 🍄 Дивні гриби | 60 |
| `shawarma` | 🌯 Шаурма | 70 |
| `cake` | 🎂 Київський торт | 120 |
| `blood` | 🩸 Донорська кров | 90 |
| `brains` | 🧠 Мізки з ринку | 80 |

## Дім / фон (`home=`, `bg=`)

Модифікатори фону: `~spring`, `~summer`, `~autumn`, `~winter`, `~dawn`, `~dusk`, `~night`, `~blackout`, `~rain`, `~storm`, `~snow`, `~fog`, `~wind` (напр. `farm~winter~snow`).

| id | Назва |
|---|---|
| `meadow` | 🌿 Галявина |
| `khrushchovka` | 🏚 Хрущовка з килимом |
| `toxic` | ☢️ Токсичне болото |
| `casino` | 🎰 Казино |
| `cemetery` | 🪦 Кладовище |
| `club` | 🪩 Нічний клуб |
| `field` | 🌾 Пшеничне поле |
| `kitchen` | 🍳 Кухня |
| `love` | 💗 Рожевий світ |
| `mystic` | 🌙 Містична ніч |
| `office` | 🏢 Офіс |
| `farm` | 🚜 Ферма |
| `space` | 🚀 Космос |
| `mountains` | 🏔 Карпати |
| `sea` | 🌊 Одеське море |
| `prison` | ⛓ В'язниця |
| `hospital` | 🏥 Лікарня |
| `palace` | 🏛 Палац (Межигір'я) |
| `bunker` | 🧱 Бункер |
| `kyiv` | 🌃 Нічний Київ |
| `ruins` | 🏚 Руїни |
| `chornobyl` | ☢️ Зона відчуження |
| `metro` | 🚇 Станція метро |
| `bukovel` | ⛷ Буковель |
| `village` | 🌻 Село, хата-мазанка |
| `atb` | 🛒 Дискаунтер «АТБ» |
| `wedding` | 💒 Весільна зала |
| `court` | ⚖️ Зала суду |
| `school` | 🏫 Шкільний клас |
| `marshrutka` | 🚐 Маршрутка |
| `dacha` | 🥒 Дача |

## Речі (`item=`)

Фіксовані речі нижче; будь-яку можна перефарбувати: `id@1…11` (червоний, помаранчевий, жовтий, зелений, бірюзовий, синій, фіолетовий, рожевий, золотий, чорний, срібний). Згенеровані речі: `item_slot="head"` або `gen:<slot>:<код>`.

| id | Назва | Слот |
|---|---|---|
| `horns` | 😈 Роги | head |
| `vinok` | 🌺 Вінок | head |
| `bow` | 🎀 Бантик | head |
| `wizard` | 🧙 Капелюх мага | head |
| `crown` | 👑 Корона | head |
| `cap` | 🧢 Кепка-восьмиклинка | head |
| `helmet` | 🪖 Каска | head |
| `chef` | 👨‍🍳 Ковпак кухаря | head |
| `cowboy` | 🤠 Ковбойський капелюх | head |
| `partyhat` | 🥳 Святковий ковпак | head |
| `halo` | 😇 Німб | head |
| `beanie` | 🧶 Шапка з помпоном | head |
| `headphones` | 🎧 Навушники | head |
| `oseledets` | 🪶 Оселедець | head |
| `foil` | 🛸 Шапочка з фольги | head |
| `flower` | 🌸 Квітка за вухом | head |
| `sunglasses` | 🕶 Окуляри | face |
| `eyepatch` | 🏴‍☠️ Пов'язка на око | face |
| `scar` | ⚔️ Шрам | face |
| `monocle` | 🧐 Монокль | face |
| `nerd` | 🤓 Окуляри ботана | face |
| `mustache` | 🥸 Козацькі вуса | face |
| `clown` | 🤡 Клоунський ніс | face |
| `mask` | 😷 Маска | face |
| `plaster` | 🩹 Пластир | face |
| `tears` | 💧 Тату-сльози | face |
| `vr` | 🥽 VR-окуляри | face |
| `chain` | ⛓ Золотий ланцюг | neck |
| `bib` | 🍼 Слинявчик | neck |
| `bowtie` | 🎀 Метелик | neck |
| `tie` | 👔 Краватка | neck |
| `scarf` | 🇺🇦 Шарф | neck |
| `medal` | 🏅 Медаль | neck |
| `bell` | 🔔 Нашийник з дзвіночком | neck |
| `korali` | 📿 Коралі | neck |
| `vyshyvanka` | 🇺🇦 Вишиванка | outfit |
| `suit` | 🤵 Костюм | outfit |
| `hoodie` | 🧥 Худі | outfit |
| `tracksuit` | 🏃 Спортивка з 3 смужками | outfit |
| `bronik` | 🦺 Бронік | outfit |
| `prison` | 🦓 Тюремна роба | outfit |
| `coat` | 🥼 Халат лікаря | outfit |
| `apron` | 🍳 Фартух | outfit |
| `robe` | 🕯 Мантія сектанта | outfit |
| `spacesuit` | 👨‍🚀 Скафандр | outfit |
| `cape` | 🦸 Плащ | back |
| `angel_wings` | 🪽 Крила ангела | back |
| `bat_wings` | 🦇 Крила кажана | back |
| `jetpack` | 🚀 Реактивний ранець | back |
| `backpack` | 🎒 Рюкзак | back |
| `coffee` | ☕ Кава | held |
| `mic` | 🎤 Мікрофон | held |
| `sabre` | 🗡 Шабля | held |
| `phone` | 📱 Смартфон | held |
| `bottle` | 🍾 Пляшка | held |
| `moneybag` | 💰 Мішок грошей | held |
| `book` | 📘 Книга | held |
| `flowers` | 💐 Букет | held |
| `guitar` | 🎸 Гітара | held |
| `balloon` | 🎈 Кулька | held |
| `cane` | 🦯 Ціпок | held |
| `drone` | 🛩 Дрон | held |
| `wand` | 🪄 Чарівна паличка | held |
| `laptop` | 💻 Ноутбук | held |
| `sausage` | 🌭 Кільце ковбаси | held |
| `cards` | 🃏 Карти | held |
| `sparkles` | ✨ Сяйво | aura |
| `hearts` | 💕 Сердечка | aura |
| `flames` | 🔥 Полум'я | aura |
| `money_rain` | 💸 Грошовий дощ | aura |
| `storm` | 🌧 Хмаринка депресії | aura |
| `notes` | 🎵 Ноти | aura |
| `flies` | 🪰 Мухи | aura |
| `bars` | ⛓ Ґрати | fg |
| `rain` | 🌧 Дощ | fg |

## Гени (`gene={...}`)

| Ген | Значення |
|---|---|
| `ears` | `cat_pointy`, `cat_big`, `cat_lynx`, `cat_fold`, `dog_floppy`, `dog_pointy`, `dog_round`, `dog_long`, `pig_floppy`, `pig_up`, `fox_ears`, `fennec`, `horse_ears`, `unicorn_mane`, `gills`, `gills_big`, `crest`, `crest_big`, `bunny`, `devil` |
| `tail` | `cat_long`, `cat_fluffy`, `bobtail`, `dog_wag`, `dog_curl`, `pig_curl`, `pig_straight`, `fox`, `horse_tail`, `axo_fin`, `bird_fan`, `bird_fork`, `devil_tail` |
| `face` | `cat`, `dog`, `dog_muzzle`, `pig`, `pig_big`, `fox_snout`, `horse_muzzle`, `axo_smile`, `beak`, `beak_hook`, `heart_nose` |
| `head` | `round`, `wide`, `tall`, `small`, `big` |
| `body` | `round`, `chubby`, `slim`, `tall` |
| `eyes` | `dot`, `big`, `slit`, `sleepy`, `button`, `hetero`, `cyclops`, `three`, `star` |
| `pattern` | `none`, `spots`, `patch`, `tabby`, `tuxedo`, `calico`, `socks`, `mask`, `gradient`, `saddle`, `dalmatian`, `tiger`, `leopard`, `points`, `pinto` |
| `mark` | `none`, `star`, `heart`, `moon`, `diamond`, `lightning`, `trident`, `sun`, `drop`, `flame`, `spiral` |
| `extra` | `none`, `freckles`, `tongue`, `mohawk`, `curl`, `fangs`, `antennae`, `unicorn`, `whiskers`, `fluff`, `beard`, `brows`, `horns`, `wings` |
| `color` | `natural`, `neon`, `albino`, `melanistic`, `shiny`, `rainbow`, `galaxy`, `pastel`, `zombie`, `frost`, `sunset` |

## Світові події (рушій, не DSL)

| id | Назва |
|---|---|
| `meteor` | ☄️ Метеорит над чатом! |
| `blackout` | 🔌 Відключення світла в усьому районі! |
| `fair` | 🎪 Ярмарок на площі! |
| `flood` | 🌊 Сусіди зверху затопили весь під'їзд! |
| `eclipse` | 🌑 Сонячне затемнення! |
| `tax` | 🧾 Податкова перевірка всього району! |
| `vaccine` | 🩺 Безкоштовна вакцинація у ветклініці! |
| `drop` | 🪂 Гуманітарка з неба! |
| `moon` | 🌕 Повня над чатом! |
| `ufo` | 🛸 НЛО зависло над районом! |
| `atm` | 💸 Банкомат на розі глючить і видає гроші! |
| `concert` | 🎤 Безкоштовний концерт на площі! |
| `bees` | 🐝 Рій бджіл атакує двір! |
