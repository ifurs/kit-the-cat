"""Find masculine words in content texts that probably speak about the pet — a helper for a human, and a gate.

    uv run python scripts/gender_scan.py                 # every unreviewed hit: file:line: [kind] word — sentence
    uv run python scripts/gender_scan.py --strict        # exit 1 if anything is left (verbs, predicate adjectives)
    uv run python scripts/gender_scan.py --all           # also the weak kinds (він/його…, role nouns), for a human
    uv run python scripts/gender_scan.py --who           # also the words guessed to be about somebody else
    uv run python scripts/gender_scan.py --module life   # one content module

A pet is a boy or a girl, so a text about it says «{знайшов|знайшла}» (see content/dsl.py) or avoids the gender.
The scan reads every text of src/kit_the_cat/content/*.py, skips the pairs already written, and guesses who a
masculine word is about: the pet (an elided subject, «{name}», «Ти», «Я»), the other pet (`{other}`), or somebody
else («Кум забрав…»). Kinds: verb (a past-tense verb), adj (a predicate adjective: «Щасливий.», «був радий»),
noun (a role noun: «Ти — переможець»), pron (він / його / йому about someone), who (the subject is unclear).
Answers go to scripts/gender_allow.txt, one per line:  `<first 40 characters of the sentence> | reason`  — a word
that is about somebody else, an object, or a deliberately masculine joke. `# gender-ok` on the line of the string
silences the whole string. Pure functions at the top (feminine(), scan_text()) are reused by tests and tools.
"""
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "src" / "kit_the_cat" / "content"
ALLOW = ROOT / "scripts" / "gender_allow.txt"

# --- the lexicon -------------------------------------------------------------------------------------
# past-tense verbs that do not end in -в / -вся / -шов, and -ів verbs (the other -ів words are plural nouns)
VERB_IV = set("""вивів вилетів влетів відлетів долетів залетів злетів прилетів полетів обгорів вигорів захворів заболів
хворів гудів загудів горів ревів сидів хотів зрозумів знепритомнів зніяковів почервонів потьмянів позеленів
розбагатів облисів звів підвів провів перевів навів летів сів їв з'їв поїв наїв доїв об'їв відповів розповів прошепотів заклеїв зустрів надів
подвоїв пересів переїв просів""".split())
VERB_OTHER = {"вивів": "вивела", "звів": "звела", "підвів": "підвела", "провів": "провела", "перевів": "перевела",
              "навів": "навела", "втік": "втекла", "утік": "утекла", "витік": "витекла", "виріс": "виросла", "виніс": "винесла",
              "заніс": "занесла", "приніс": "принесла", "проніс": "пронесла", "заліз": "залізла", "виліз": "вилізла",
              "зліг": "злягла", "переміг": "перемогла", "допоміг": "допомогла", "зміг": "змогла", "наполіг": "наполягла",
              "помер": "померла", "витер": "витерла", "здох": "здохла", "заглох": "заглохла", "ішов": "йшла",
              "міг": "могла", "ліг": "лягла", "ніс": "несла", "ліз": "лізла", "ріс": "росла", "зріс": "зросла",
              "завмер": "завмерла", "замовк": "замовкла", "застряг": "застрягла", "встиг": "встигла", "помовк": "помовкла"}
NOT_VERB = set("колектив корпоратив креатив детектив актив мотив позитив негатив страв справ забав лав гав шов вся "
               "двох трьох".split())
# regular endings: -в → -ла (взяв → взяла), -вся → -лася, -шов → -шла (прийшов → прийшла)
VERB_RX = re.compile(r"^[а-яіїєґ']*(?:ав|яв|ив|ув|юв|еув)(?:ся)?$")

PRED_ADJ = {"радий": "рада", "готовий": "готова", "щасливий": "щаслива", "задоволений": "задоволена",
            "вдячний": "вдячна", "злий": "зла", "голодний": "голодна", "сонний": "сонна", "мокрий": "мокра",
            "п'яний": "п'яна", "впевнений": "впевнена", "певен": "певна", "винен": "винна", "вільний": "вільна",
            "сам": "сама", "самотній": "самотня", "живий": "жива", "мертвий": "мертва", "зайнятий": "зайнята",
            "схвильований": "схвильована", "шокований": "шокована", "здивований": "здивована",
            "наляканий": "налякана", "розгублений": "розгублена", "втомлений": "втомлена", "ображений": "ображена",
            "закоханий": "закохана", "відомий": "відома", "багатий": "багата", "бідний": "бідна", "розумний": "розумна",
            "здоровий": "здорова", "чистий": "чиста", "брудний": "брудна", "веселий": "весела", "сумний": "сумна",
            "гордий": "горда", "спокійний": "спокійна", "одинокий": "одинока", "щасливіший": "щасливіша",
            "красивий": "красива", "прав": "права", "голий": "гола", "тверезий": "тверез" + "а", "сильний": "сильна",
            "слабкий": "слабка", "хворий": "хвора", "порожній": "порожня", "ситий": "сита", "босий": "боса"}
PART_RX = re.compile(r"^[а-яіїєґ']+(?:ований|ений|аний|ітий|ятий|утий)$")
ROLE_NOUNS = {"переможець": "переможниця", "чемпіон": "чемпіонка", "герой": "героїня", "блогер": "блогерка",
              "король": "королева", "президент": "президентка", "мільйонер": "мільйонерка", "олігарх": "олігархиня",
              "власник": "власниця", "директор": "директорка", "майстер": "майстриня", "тренер": "тренерка",
              "мер": "мерка", "лідер": "лідерка", "експерт": "експертка", "фермер": "фермерка",
              "інфлюенсер": "інфлюенсерка", "тіктокер": "тіктокерка", "ветеран": "ветеранка", "пенсіонер": "пенсіонерка",
              "студент": "студентка", "програміст": "програмістка", "пророк": "пророчиця", "кандидат": "кандидатка",
              "інвестор": "інвесторка", "супергерой": "супергероїня", "красень": "красуня", "щасливчик": "щасливиця",
              "переселенець": "переселенка", "волонтер": "волонтерка", "художник": "художниця", "співак": "співачка",
              "актор": "акторка", "учасник": "учасниця", "автор": "авторка", "засновник": "засновниця",
              "підприємець": "підприємиця", "дід": "баба", "кіт": "кішка"}
PRONOUNS = {"він", "його", "йому", "нього", "ним", "нім", "ньому", "ніго"}

PREPS = set("""в у до від для без біля про на за над під перед між з із зі по при через серед замість проти навколо коло
заради навпроти окрім крізь після з-за з-під""".split())
FUNC = set("""і й та а але або чи не ні ще вже тоді потім тепер нарешті раптом там тут одразу швидко навіть лише тільки
зовсім цілком майже згодом врешті все ж б би також теж якось колись ніколи завжди так то коли поки бо що як якщо
хоч хоча щоб ніби наче мов ледь ледве спершу спочатку потому знов знову ось от це ця цей ці той та те оте всі
усі весь вся все кожен кожна кожне ніхто ніщо хтось щось ніколи тому тож отже зате однак проте
пів ну ой ох ах ех гей ей агов оце ото аж якраз саме просто дуже так само трохи майже зовсім мало багато
також вночі вдень вранці ввечері вдома сьогодні вчора завтра потім далі пізніше раніше разом""".split())
# masculine nouns and names on «-а»/«-я»/«-о» that open a sentence («Суддя прочитав…»): the scan cannot tell them
# from a fem. adjective or an adverb by their ending
SUBJECT_A = {"суддя", "дядько", "марко", "тамада", "голова", "батюшка", "лелека", "бариста", "колега", "микола",
             "тато", "батько", "собака", "дніпро", "вітя", "микита", "зеник", "юрко", "сашко", "петро"}
# a verb that takes its subject after it («Приїхав патруль», «Там був однокласник») — an object would not follow it
SUBJECT_AFTER = {"приїхав", "прийшов", "прилетів", "з'явився", "настав", "відбувся", "почався", "закінчився",
                 "вибухнув", "залетів", "влетів", "був", "прокинувся", "стався", "виявився", "залишився", "лишився",
                 "спрацював", "вийшов", "минув", "зазвучав", "зайшов", "підійшов", "приземлився", "сів"}
WHO_WORDS = {"ніхто", "хтось", "хто", "кожен", "ніщо", "це"}
OBJECT_PRONOUNS = {"тебе", "мене", "його", "її", "нас", "вас", "їх", "тобі", "мені"}
OBLIQUE_NAME = re.compile(r"\{name_(?:gen|dat|acc|ins|loc|voc)\}")
RELATIVE_WORDS = {"який", "яка", "яке", "які", "якого", "якому", "якій", "яку", "якою", "яким", "якими", "якої", "чий",
                  "чиї", "чиєї", "чиїх", "чиїй", "де", "куди", "звідки", "якого", "котрий", "котрого", "котрому"}
COMP_HEADS = {"так", "настільки", "вигляд", "відчуття", "виявилося", "з'ясувалося", "хоч", "тільки", "поки"}
RELATIVE = {"який", "яка", "яке", "які", "котрий", "котра", "що", "хто", "де", "куди"}

TOKEN = re.compile(r"\{[^{}]*\}|[А-Яа-яІіЇїЄєҐґ'’-]+|[.!?…]+|[,;:—–()«»\"]|\S")
PAIR = re.compile(r"\{(?:other:)?[^{}|:]*\|[^{}|]*\}")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
NAME_PH = {"name"}


def feminine(w: str) -> str | None:
    """Feminine past-tense form of a masculine verb, or None when the word is not one."""
    lw = w.lower()
    refl = lw.endswith("ся")
    base = lw[:-2] if refl else lw
    if base in NOT_VERB or lw in NOT_VERB:
        return None
    if base in VERB_OTHER:
        stem = VERB_OTHER[base]
    elif base.endswith("шов"):
        stem = base[:-3] + "шла"
    elif base.endswith("в") and (base in VERB_IV or VERB_RX.match(base)):
        stem = base[:-1] + "ла"
    else:
        return None
    out = stem + "ся" if refl else stem
    if len(w) > 1 and w.isupper():
        return out.upper()
    return out[:1].upper() + out[1:] if w[:1].isupper() else out


def adjective(w: str) -> str | None:
    lw = w.lower()
    out = PRED_ADJ.get(lw)
    if out is None and PART_RX.match(lw):
        out = lw[:-2] + "а"
    if out is not None and w[:1].isupper():
        out = out[:1].upper() + out[1:]
    return out


@dataclass
class Hit:
    start: int      # offset of the word in the text
    end: int
    word: str
    kind: str       # verb | adj | noun | pron | who
    subj: str       # pet | other | who  — who the word is guessed to be about
    fem: str        # the feminine form to put in the pair
    sentence: str


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def _is_word(tok: str) -> bool:
    return bool(tok) and tok[0].isalpha()


def scan_text(text: str, social: bool = False) -> list[Hit]:
    """Masculine words about someone in one text; pairs already written are skipped."""
    toks = _tokens(text)
    hits: list[Hit] = []
    i = 0
    n = len(toks)
    while i < n:
        j = i
        while j < n and not re.fullmatch(r"[.!?…]+", toks[j][0]):
            j += 1
        sentence = text[toks[i][1]:toks[min(j, n - 1)][2]] if n else ""
        hits += _scan_sentence(toks[i:j], sentence, social)
        i = j + 1
    return hits


def _scan_sentence(toks: list, sentence: str, social: bool) -> list[Hit]:
    hits: list[Hit] = [Hit(s, e, w, "pred", "pet", "?", sentence) for w, s, e in predicate_nouns(toks)]
    clauses: list[list] = [[]]
    for t in toks:
        if t[0] in {",", ";", ":", "—", "–", "(", ")", "«", "»", '"'}:
            clauses.append([])
        else:
            clauses[-1].append(t)
    inherited = "pet"
    for ci, words in enumerate(clauses):
        first = next((k for k, (tok, _, _) in enumerate(words) if _is_word(tok) and _predicate(words, k)), None)
        pre = words[:first] if first is not None else words
        tail = next((w[0].lower() for w in reversed(clauses[ci - 1]) if _is_word(w[0])), "") if ci else ""
        subj = _subject(pre, inherited if ci else "pet", ci == 0, sentence, social, tail)
        if not any(tok.lower() in RELATIVE_WORDS for tok, _, _ in words):
            inherited = subj  # a relative clause («якого {name} підібрав») does not change who the sentence is about
        for k, (tok, s, e) in enumerate(words):
            if not _is_word(tok):
                continue
            fem, kind = _predicate(words, k) or (None, None)
            if fem is None:
                low = tok.lower()
                if low in ROLE_NOUNS and k and _role_position(words, k):
                    fem, kind = ROLE_NOUNS[low], "noun"
                elif low in PRONOUNS:
                    fem, kind = "?", "pron"
            if kind:
                who = subj
                if kind == "verb" and tok.lower() in SUBJECT_AFTER and k + 1 < len(words) and subj == "pet":
                    nxt = words[k + 1][0]
                    if _is_word(nxt) and nxt.lower() not in FUNC | PREPS and _masculine_subject(nxt, False) \
                            and not PAIR.fullmatch(nxt) and feminine(nxt) is None:
                        who = "who"
                        inherited = "who"
                hits.append(Hit(s, e, tok, kind, who, fem, sentence))
    return hits


OBLIQUE = ("ом", "ем", "єм", "ам", "ям", "ах", "ях", "ів", "їв", "ми", "ою", "ею")


def _masculine_subject(tok: str, first: bool) -> bool:
    """Can this word be a masculine nominative noun (or a name)? Consonant, «-ь», «-й», or a capitalised name
    that does not open the sentence."""
    low = tok.lower()
    if low in SUBJECT_A:
        return True
    if len(low) < 3 or (len(low) > 4 and low.endswith(OBLIQUE)):
        return False
    return low[-1] in "бвгґджзклмнпрстфхцчшщьй" or (tok[:1].isupper() and not first and low[-1] in "ая")


PRED_SKIP = {"тепер", "знову", "все", "ще", "вже", "і", "й", "просто", "тільки", "справді", "таки", "ж", "не", "аж", "зараз",
             "одразу", "тоді", "теж", "також", "дуже", "майже", "вічно", "ніби", "наче", "єдиний", "перший"}


def predicate_nouns(sentence_tokens: list) -> list[tuple[str, int, int]]:
    """«Ти — герой», «Тепер ти сам», «я незалежний»: a masculine noun or adjective right after «ти» / «я»."""
    out = []
    ws = [t for t in sentence_tokens if t[0] not in {",", ";", ":", "«", "»", '"', "(", ")"}]
    for i, (tok, _, _) in enumerate(ws):
        if tok.lower() not in {"ти", "я"}:
            continue
        j = i + 1
        while j < len(ws) and (ws[j][0] in {"—", "–"} or ws[j][0].lower() in PRED_SKIP):
            j += 1
        if j >= len(ws) or not _is_word(ws[j][0]) or tok.startswith("{") or ws[j][0].startswith("{"):
            continue
        w = ws[j][0]
        low = w.lower()
        if low in FUNC or low in PREPS or low in OBJECT_PRONOUNS or low in PRONOUNS or feminine(w):
            continue
        if low.endswith(("ий", "ій")) and len(low) > 4 or low in ROLE_NOUNS or (
                low[-1] in "бвгґджзклмнпрстфхцчщьй" and len(low) > 3 and not low.endswith(("ш", "ся", "сь", "ть", "єш", "їш"))
                and low not in {"їм", "нам", "вам"}):
            out.append((w, ws[j][1], ws[j][2]))
    return out


def _predicate(words: list, k: int) -> tuple[str, str] | None:
    """(feminine form, kind) when word k is a masculine verb or a predicate adjective."""
    tok = words[k][0]
    fem = feminine(tok)
    if fem:
        return fem, "verb"
    fem = adjective(tok)
    if fem and (_predicate_position(words, k) or tok.lower() == "сам"):
        return fem, "adj"
    return None


def _subject(pre: list, inherited: str, first: bool = False, sentence: str = "", social: bool = False,
             tail: str = "") -> str:
    """Who the verbs of a clause are about, from the words before its first predicate."""
    for tok, _, _ in pre:
        low = tok.lower()
        if tok == "{name}" or low == "ти":
            return "pet"
        if low == "я":
            return inherited if inherited in {"who", "other"} else "pet"
        if tok == "{other}":
            return "other"
        if low in WHO_WORDS or low in OBJECT_PRONOUNS:
            return "who"
    if OBLIQUE_NAME.search(sentence):  # «Записав {name_acc} у «хороші»»: the pet is the object, not the doer
        return "other" if social else "who"
    cands = []
    skip = 0
    for n, (tok, _, _) in enumerate(pre):
        low = tok.lower()
        if skip:
            if _is_word(tok) and (low in FUNC or low.endswith(ADJ_ENDINGS)):
                continue
            skip = 0
            continue  # the noun of the prepositional phrase
        if low in PREPS:
            skip = 1
            continue
        if low in RELATIVE:
            prev = pre[n - 1][0].lower() if n else tail
            if low == "що" and (feminine(prev) or prev.endswith(("ти", "ться", "ся", "ла", "ло", "ли")) or prev in COMP_HEADS):
                continue  # «зрозумів, що мріяв»: a complement clause keeps the subject of the main one
            rest = pre[n + 1:]
            if any(_is_word(x) and x.lower() not in FUNC and _masculine_subject(x, False) for x, _, _ in rest):
                return "who"
            return "rel"  # «ту, що купив»: the antecedent may be the pet or an object — read it
        if not _is_word(tok) or low in FUNC or tok.startswith("{") or not _masculine_subject(tok, first and n == 0):
            continue
        cands.append(tok)
    return "who" if cands else inherited


ADJ_ENDINGS = ("ий", "ій", "а", "я", "е", "є", "ого", "ому", "ої", "их", "ім", "им", "ою", "ю", "ьому", "ьої", "ьою")


def _predicate_position(words: list, k: int) -> bool:
    """An adjective stands as a predicate when nothing noun-like follows it in the clause."""
    nxt = words[k + 1][0].lower() if k + 1 < len(words) else ""
    return not nxt or nxt in FUNC or nxt in PREPS or PAIR.fullmatch(words[k + 1][0]) is not None


def _role_position(words: list, k: int) -> bool:
    prev = words[k - 1][0].lower()
    return prev in {"як", "став", "стала", "ти", "я"} or prev == "—"


# --- the allowlist ---------------------------------------------------------------------------------------

def allowed() -> dict[str, str]:
    out = {}
    if ALLOW.exists():
        for line in ALLOW.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                key, _, why = line.partition(" | ")
                out[key.strip()] = why.strip()
    return out


def key_of(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence).strip()[:40].strip()


# --- the walk ------------------------------------------------------------------------------------------------

def _ach_keys() -> set[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from kit_the_cat.engine import ACH_F
    return set(ACH_F)


def strings(modules: set[str] | None = None):
    """(file, lineno, text) of every string constant of the content modules, docstrings and `# gender-ok` aside."""
    keys = _ach_keys()  # achievement keys stay masculine (Pet.ach_name shows the feminine title)
    for path in sorted(CONTENT.glob("*.py")):
        if path.stem in {"dsl", "validate", "events", "persona", "economy", "__init__"}:
            continue
        if modules and path.stem not in modules:
            continue
        text = path.read_text()
        lines = text.splitlines()
        tree = ast.parse(text, str(path))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                if re.search(r"[а-яіїєґ]", node.value, re.I) and "gender-ok" not in lines[node.lineno - 1] \
                        and node.value not in keys:
                    yield path.relative_to(ROOT).as_posix(), node.lineno, node.value


def scan(weak: bool = False, modules: set[str] | None = None, who: bool = False) -> list[tuple[str, int, Hit]]:
    ok = allowed()
    out = []
    for f, line, text in strings(modules):
        for h in scan_text(text, f.endswith("/social.py")):
            if h.kind in {"noun", "pron"} and not weak:
                continue
            if key_of(h.sentence) in ok or (h.subj == "who" and not who):
                continue
            out.append((f, line, h))
    return out


def main() -> None:
    weak = "--all" in sys.argv
    mods = {a.split("=", 1)[1] if "=" in a else sys.argv[i + 2] for i, a in enumerate(sys.argv[1:])
            if a.startswith("--module")} or None
    hits = scan(weak, mods, "--who" in sys.argv)
    for f, line, h in hits:
        who = {"pet": "", "other": " (other pet)", "who": " (somebody)", "rel": " (relative)"}[h.subj]
        print(f"{f}:{line}: [{h.kind}] {h.word} → {h.fem}{who} — {h.sentence[:90]}")
    counts = {}
    for _, _, h in hits:
        counts[h.kind] = counts.get(h.kind, 0) + 1
    print(f"# {len(hits)} hits " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if "--strict" in sys.argv and hits:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
