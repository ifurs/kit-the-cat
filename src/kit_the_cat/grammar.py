"""Ukrainian declension of pet names, so a text can say «Крилатого з Троєщини» instead of «Крилатий з Троєщини».

    decline("Крилатий з Троєщини")  →  {"nom": "Крилатий з Троєщини", "gen": "Крилатого з Троєщини", …}

A name is a *head* that declines and a *tail* that stays as it is: the tail starts at the first preposition
(«з», «із», «від», «№»…), so «Бублик Грозний із Жмеринки» → «Бублика Грозного із Жмеринки». Every word of the
head is declined by its own ending: adjectives («Крилатий», «Велика», «Третій»), masculine nouns on a consonant,
«-ь», «-й», «-о» («Барсик», «Пельмень», «Бровко») and nouns on «-а»/«-я» («Мурка», «Гоша», «Кузя»). Words the
rules get wrong live in EXCEPTIONS; anything that is not plain Ukrainian (Latin letters, digits, emoji) and every
indeclinable word («Ферарі», «Цок-Цок», a feminine name on a consonant) stays in the nominative. Pure functions,
stdlib only, never raise: user-chosen names go through here.

    inflect(name, "gen")  is the one-form shortcut for f-strings:  f"До {inflect(p.name, 'gen')} прийшли колектори".

Gendered words in a text are written as a pair, «{вилупився|вилупилася}» for the pet and «{other:відмовив|відмовила}»
for the other pet; pick(text, gender, other_gender) keeps the first alternative for "m" and the second for "f".
"""
import re
from functools import lru_cache

CASES = ("nom", "gen", "dat", "acc", "ins", "loc", "voc")
GENDERS = ("m", "f")
# {masculine|feminine} for the pet, {other:masculine|feminine} for the other pet: no braces, colons or bars inside
GENDER_RX = re.compile(r"\{(?:(other):)?([^{}|:]*)\|([^{}|]*)\}")

# a tail starts at one of these words (compared in lower case) or at «№»
PREPOSITIONS = {"з", "із", "зі", "від", "з-за", "із-за", "з-під", "до", "біля", "на", "в", "у", "по", "при", "над",
                "під", "за", "для", "без"}
INDECLINABLE = {"вічно", "і", "й", "та", "чи", "не", "як", "де"}
# whole words (lower case) → the seven forms; also fixes hyphenated names, which would otherwise decline their tail
EXCEPTIONS = {
    "цок-цок": ("цок-цок",) * 7,
    "овес": ("овес", "овса", "овсові", "овса", "овсом", "овсові", "овсе"),  # «Овса», not «вівса»: it is a name
    "пташеня": ("пташеня", "пташеняти", "пташеняті", "пташеня", "пташеням", "пташеняті", "пташеня"),
    "зернятко": ("зернятко", "зернятка", "зернятку", "зернятко", "зернятком", "зернятку", "зернятко"),
}
# feminine adjectives look like nouns on «-а»; these are the ones that appear in names
ADJ_F = {"велика", "мала", "руда", "мудра", "хитра", "грозна", "нова", "стара", "мила", "гарна", "третя", "перша",
         "друга", "молодша", "старша", "хитромудра", "неймовірна", "безсмертна", "пухнаста", "жахлива", "залізна",
         "непереможна", "мрійлива", "сором'язлива", "солоденька", "голодна", "сильна", "швидка", "смілива"}
ADJ_F_SUFFIX = re.compile(r"(ськ|цьк|зьк|ньк)а$")
# the few adjectives on «-ій» (the rest of «-ій» words, like «Буревій», are nouns)
ADJ_SOFT = {"третій", "синій", "крайній", "давній", "нижній", "верхній", "середній", "ранній", "пізній", "дальній",
            "ближній", "сторонній", "безодній"}
HUSH = "жчшщ"
BACK = {"к": "ц", "г": "з", "х": "с"}  # k → ц before the «-і» of the dative of a noun on «-а»
APOSTROPHES = "'" + chr(0x2019) + chr(0x02BC)  # built, not typed: the lint bans typographic ones in literals
CYR = re.compile(f"[а-яїієґ{APOSTROPHES}-]+")
EDGES = re.compile(r"([^\w']*)(.*?)([^\w']*)", re.S)


def _adjective(low: str) -> tuple | None:
    """Seven forms of an adjective (masculine or feminine nominative), or None when the word is not one."""
    if low.endswith("ий") and len(low) > 3:
        s = low[:-2]
        return low, s + "ого", s + "ому", s + "ого", s + "им", s + "ому", low
    if low in ADJ_SOFT:
        s = low[:-2]
        return low, s + "ього", s + "ьому", s + "ього", s + "ім", s + "ьому", low
    if low in ADJ_F or ADJ_F_SUFFIX.search(low):
        s = low[:-1]
        if low.endswith("я"):  # Третя → Третьої
            return low, s + "ьої", s + "ій", s + "ю", s + "ьою", s + "ій", low
        return low, s + "ої", s + "ій", s + "у", s + "ою", s + "ій", low
    return None


def _masculine(low: str) -> tuple | None:
    """Masculine noun on a consonant, «-ь», «-й» or «-о» (second declension)."""
    last = low[-1]
    if last == "ь":
        s = low[:-1]
        if low.endswith("ець") and len(low) > 4:  # fleeting vowel: Перець → Перця
            s = low[:-3] + "ц"
        return low, s + "я", s + "еві", s + "я", s + "ем", s + "еві", s + "ю"
    if last == "й":
        s = low[:-1]
        return low, s + "я", s + "єві", s + "я", s + "єм", s + "єві", s + "ю"
    if last == "о":
        s = low[:-1]
        voc = s + ("у" if s[-1:] in "кгх" else "е")
        return low, s + "а", s + "ові", s + "а", s + "ом", s + "ові", voc
    if last in "бвгґджзклмнпрстфхцчшщ":
        s = low[:-2] + "к" if low.endswith("ок") and len(low) > 3 else low  # fleeting vowel: Пуголовок → Пуголовка
        if s[-1] in HUSH:
            return low, s + "а", s + "еві", s + "а", s + "ем", s + "еві", s + "у"
        if s.endswith("ак"):  # Козак → Козаче
            voc = s[:-1] + "че"
        elif s[-1] in "кгх":
            voc = s + "у"
        else:
            voc = s + "е"
        return low, s + "а", s + "ові", s + "а", s + "ом", s + "ові", voc
    return None


def _feminine_a(low: str) -> tuple | None:
    """Nouns on «-а»/«-я»: Мурка, Гоша, Кузя, Марія (masculine ones like Микита decline the same way)."""
    s = low[:-1]
    if not s:
        return None
    if low.endswith("я"):
        if s.endswith("і"):  # Марія → Марії
            return low, s + "ї", s + "ї", s + "ю", s + "єю", s + "ї", s + "є"
        return low, s + "і", s + "і", s + "ю", s + "ею", s + "і", s + "ю"
    c = s[-1]
    if c in HUSH:
        return low, s + "і", s + "і", s + "у", s + "ею", s + "і", s + "о"
    dat = s[:-1] + BACK[c] + "і" if c in BACK else s + "і"
    return low, s + "и", dat, s + "у", s + "ою", dat, s + "о"


def _word_forms(low: str, gender: str) -> tuple | None:
    """The seven forms of one lower-case word, or None when it stays as it is."""
    if low in EXCEPTIONS:
        return EXCEPTIONS[low]
    if low in INDECLINABLE or not CYR.fullmatch(low) or "-" in low.strip("-") or len(low) < 2:
        return None
    forms = _adjective(low)
    if forms is None and low[-1] in "ая":
        forms = _feminine_a(low)
    elif forms is None and gender != "f":  # a feminine name on a consonant («Любов», «Жуж») stays as it is
        forms = _masculine(low)
    return forms


def _recase(word: str, forms: tuple) -> tuple:
    if len(word) > 1 and word.isupper():
        return tuple(f.upper() for f in forms)
    caps = [p[:1].isupper() for p in word.split("-")]  # «Гуппі-Бос»: a capital after each hyphen, like the source

    def like(form: str) -> str:
        parts = form.split("-")
        if len(parts) != len(caps):
            caps_ = [caps[0]] * len(parts)
        else:
            caps_ = caps
        return "-".join(p[:1].upper() + p[1:] if up else p for p, up in zip(parts, caps_))
    return tuple(like(f) for f in forms)


def _token(tok: str, gender: str) -> tuple:
    """One space-free piece: strip quotes and commas, decline the last part of a hyphenated word."""
    pre, core, post = EDGES.fullmatch(tok).groups()
    if not core:
        return (tok,) * 7
    if "-" in core.strip("-") and core.lower() not in EXCEPTIONS:
        head, _, last = core.rpartition("-")
        forms = _word_forms(last.lower(), gender)
        forms = tuple(f"{head}-{f}" for f in _recase(last, forms)) if forms else (core,) * 7
    else:
        forms = _word_forms(core.lower(), gender)
        forms = _recase(core, forms) if forms else (core,) * 7
    return tuple(pre + f + post for f in forms)


@lru_cache(maxsize=4096)
def _decline(name: str, gender: str) -> tuple:
    words = name.split(" ")
    cut = len(words)
    for i, w in enumerate(words):
        if w.lower() in PREPOSITIONS or w.startswith("№"):
            cut = i
            break
    head = [_token(w, gender) for w in words[:cut]]
    tail = " ".join(words[cut:])
    out = []
    for k in range(7):
        part = " ".join(f[k] for f in head)
        out.append(f"{part} {tail}" if part and tail else part or tail)
    return tuple(out)


def decline(name: str, gender: str = "m") -> dict[str, str]:
    """All seven forms of a pet name (see the module docstring); `gender` is "m" or "f"."""
    return dict(zip(CASES, _decline(name or "", "f" if gender == "f" else "m")))


def inflect(name: str, case: str, gender: str = "m") -> str:
    """One form of a pet name: inflect("Мурка", "acc") → «Мурку»."""
    return decline(name, gender)[case]


def pick(text: str, gender: str = "m", other_gender: str | None = None) -> str:
    """Resolve the «{він|вона}» pairs of a template: the pet's own, and «{other:…|…}» for the other pet
    (masculine when there is no other pet). Run it before str.format, so names never pass through it."""
    def one(m: re.Match) -> str:
        return m.group(3) if (other_gender if m.group(1) else gender) == "f" else m.group(2)
    return GENDER_RX.sub(one, text)


def template_errors(text: str) -> list[str]:
    """Problems in the gender pairs of a template: a bar outside a well-formed {a|b}/{other:a|b} (three
    alternatives, a colon, nested or unclosed braces), or an empty pair."""
    errors = []
    rest = GENDER_RX.sub(lambda m: "" if m.group(2) or m.group(3) else "\0", text)
    if "\0" in rest:
        errors.append("empty gender pair {|}")
    if "|" in rest.replace("\0", ""):
        errors.append("malformed gender pair: use exactly {masculine|feminine} or {other:masculine|feminine}")
    return errors
