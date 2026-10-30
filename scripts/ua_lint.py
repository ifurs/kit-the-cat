"""Ukrainian text lint for everything players read: every Cyrillic string literal in src/kit_the_cat (events,
items, tiers, notes, achievements…), found with `ast`, so comments and docstrings are skipped.

    uv run python scripts/ua_lint.py              # report
    uv run python scripts/ua_lint.py --strict     # CI: exit 1 on errors (warnings never fail)
    uv run python scripts/ua_lint.py --warnings   # also list warnings (russisms, typography)

Errors (always wrong): Russian-only letters (ы э ъ ё), Latin look-alikes inside a Cyrillic word, typographic
apostrophes (’ ʼ ` ´) instead of ', unknown {placeholders}, unbalanced «».
Warnings (usually wrong, a human decides): russisms and surzhyk from RUSSISMS (with the fix), a missing apostrophe
in common words, "..." instead of …, " - " instead of " — ", ASCII "quotes" instead of «», double spaces.
Intentional jokes (a character speaking surzhyk) go to scripts/ua_allow.txt as `file:line:word`.

This is the cheap, deterministic half of language review; the other half is the content-reviewer agent
(.claude/agents/content-reviewer.md), which reads for naturalness, tone and boundaries.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "kit_the_cat"
ALLOW = ROOT / "scripts" / "ua_allow.txt"
CASE_FORMS = {f"{who}_{c}" for who in ("name", "other") for c in ("gen", "dat", "acc", "ins", "loc", "voc")}
PLACEHOLDERS = {"name", "owner", "food", "dream", "fear", "quirk", "temper", "money", "role", "other", "other_owner",
                "w", "l"} | CASE_FORMS  # w/l: battle winner/loser
CYR = re.compile(r"[А-Яа-яЇїІіЄєҐґ]")
WORD = re.compile(r"[A-Za-zА-Яа-яЇїІіЄєҐґ'’ʼ`´]+")
L = "а-яїієґ'"  # letters that may continue a word
# russism / surzhyk → better Ukrainian. Whole words (or phrases); a trailing * marks a stem («получи*» = получив…)
RUSSISMS = {
    "нащадниц*": "нащадкиня", "добровольиц*": "добровольчиня", "смотрящ*": "старший по камері", "вороная": "гніда",
    "перепідар*": "передар…", "переподар*": "передар…", "сперечальник*": "той, хто сперечається",
    "пожалуйста": "будь ласка", "рішати": "вирішувати", "рішив": "вирішив", "рішила": "вирішила",
    "слідуюч*": "наступн…", "мероприят*": "захід", "міроприємств*": "захід", "ізвініть": "вибачте",
    "ізвини": "вибач", "получи*": "отрима…", "получа*": "отриму…", "вообще": "взагалі", "конечно": "звісно",
    "тоже": "теж", "ладно": "гаразд", "являється": "є", "являюсь": "є", "співпада*": "збіга…",
    "на протязі": "протягом", "в залежності від": "залежно від", "приймати участь": "брати участь",
    "прийняв участь": "взяв участь", "прийшлось": "довелося", "кушати": "їсти", "кстаті": "до речі",
    "сдача": "решта", "ковьор": "килим", "відноситься до": "стосується", "приймати міри": "вживати заходів",
    "на рахунок": "щодо", "самий кращий": "найкращий", "самий гарний": "найгарніший", "більш кращ*": "кращ…",
    "чим раніше": "що раніше", "згідно закону": "згідно із законом", "по крайній мірі": "принаймні",
    "убєжище": "укриття", "щас": "зараз", "всьо": "все", "канєшно": "звісно", "тіпа": "типу",
}
NEEDS_APOSTROPHE = {  # common words written without the apostrophe (stems)
    "мяс*": "м'яс…", "памят*": "пам'ят…", "пять*": "п'ять…", "пяти*": "п'яти…", "пятн*": "п'ятн…",
    "пятий": "п'ятий", "обєкт*": "об'єкт…", "обєдн*": "об'єдн…", "зїв*": "з'їв…", "зїс*": "з'їс…",
    "зявив*": "з'явив…", "сімя": "сім'я", "мяк*": "м'як…", "вяза*": "в'яза…", "звязок": "зв'язок",
    "компютер*": "комп'ютер…", "інтервю": "інтерв'ю",
}


def hits(low: str, table: dict) -> list[str]:
    out = []
    for bad, good in table.items():
        stem = bad.endswith("*")
        pat = rf"(?<![{L}]){re.escape(bad.rstrip('*'))}" + ("" if stem else rf"(?![{L}])")
        if re.search(pat, low):
            out.append(f"«{bad.rstrip('*')}» → «{good}»")
    return out


def strings():
    """(file, line, text) for every Cyrillic str constant, skipping docstrings."""
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docs.add(id(first.value))
        parts = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs \
                    and CYR.search(node.value):
                yield path.relative_to(ROOT).as_posix(), node.lineno, node.value, id(node) in parts


def allowed() -> set[str]:
    if not ALLOW.exists():
        return set()
    return {ln.strip() for ln in ALLOW.read_text().splitlines() if ln.strip() and not ln.startswith("#")}


def check(text: str, fragment: bool = False) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if m := re.search(r"[ЫыЭэЪъЁё]", text):
        errors.append(f"Russian letter «{m.group()}»")
    for w in WORD.findall(text):
        if CYR.search(w) and re.search(r"[A-Za-z]", w):
            errors.append(f"Latin look-alike letters inside «{w}»")
        if CYR.search(w) and re.search(r"[’ʼ`´]", w):
            errors.append(f"typographic apostrophe in «{w}» → «{re.sub('[’ʼ`´]', chr(39), w)}»")
    for ph in re.findall(r"\{([a-z_]+)\}", text):
        if ph not in PLACEHOLDERS:
            errors.append(f"unknown placeholder {{{ph}}}")
    if not fragment and text.count("«") != text.count("»"):
        errors.append("unbalanced «»")
    low = text.lower()
    warnings += hits(low, RUSSISMS) + hits(low, NEEDS_APOSTROPHE)
    if "..." in text:
        warnings.append('"..." → "…"')
    if re.search(r"[А-Яа-яЇїІіЄєҐґ] - [А-Яа-яЇїІіЄєҐґ]", text):
        warnings.append('" - " → " — "')
    if re.search(r'"[А-Яа-яЇїІіЄєҐґ]', text):
        warnings.append('ASCII "quotes" → «»')
    if "  " in text.strip():
        warnings.append("double space")
    return errors, warnings


def main() -> None:
    allow = allowed()
    n = errs = warns = 0
    out_e, out_w = [], []
    for f, line, text, fragment in strings():
        n += 1
        e, w = check(text, fragment)
        e = [x for x in e if not any(f"{f}:{line}:{a}" in allow for a in re.findall(r"«([^»]+)»", x))]
        w = [x for x in w if not any(f"{f}:{line}:{a}" in allow for a in re.findall(r"«([^»]+)»", x))]
        errs += len(e)
        warns += len(w)
        out_e += [f"  {f}:{line}: {x}   «{text[:60]}»" for x in e]
        out_w += [f"  {f}:{line}: {x}   «{text[:60]}»" for x in w]
    print(f"# Ukrainian lint: {n} strings · {errs} errors · {warns} warnings")
    if out_e:
        print("\n## Errors\n" + "\n".join(out_e))
    if out_w and "--warnings" in sys.argv:
        print("\n## Warnings\n" + "\n".join(out_w))
    elif out_w:
        print("(run with --warnings to list them)")
    if "--strict" in sys.argv and errs:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
