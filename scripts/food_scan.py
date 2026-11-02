"""List the {food} placeholders that probably stand in the wrong case — a helper for a human, not a judge.

    uv run python scripts/food_scan.py              # every suspicious {food}: file:line: [kind] context
    uv run python scripts/food_scan.py --strict     # exit 1 on any of them; CI gate (content_gate.py)
    uv run python scripts/food_scan.py --all        # also every {food} that stays, to read them one by one

{food} is the accusative («їсть шаурму», «піти по борщ»). Everywhere else the food needs its own form: {food_nom}
(«Головне — шаурма»), {food_gen}, {food_dat}, {food_ins}, {food_loc} (see content/persona.py FOOD_FORMS and dsl.py).
Kinds: prep (a preposition that takes another case right before it: «з {food}», «банок з-під {food}», «в {food}»),
head (a word that wants the genitive: «ящик {food}», «поменше {food}»), dat (a verb that takes the dative:
«подякувати {food}»), ins (a verb that takes the instrumental: «обмінялися {food}»), nom (after «є», «був»…),
subj (the placeholder starts a clause, so it is probably the subject, and a verb after it would have to agree with a
plural food), adj (an adjective before it, which would have to agree with any gender and number of the food).
`# food-ok` on the line of a string silences it.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "kit_the_cat"

W = r"[\w'’-]"
PH = r"\{food\}"
# prepositions that do not take the accusative (a state in «в/у» is the locative; «на», «за», «по», «про» do take it)
PREPS = ("в", "у", "до", "від", "для", "без", "біля", "з", "із", "зі", "з-за", "з-під", "із-під", "над", "перед", "між", "при",
         "замість", "проти", "навколо", "коло", "заради", "навпроти", "окрім", "крім", "після", "серед", "завдяки")
HEADS = ("ящик", "ящики", "ящиків", "колекція", "колекцію", "доставка", "доставку", "тарілка", "порція", "порцію",
         "миска", "миску", "запах", "смак", "смаку", "рецепт", "рецепти", "кількість", "гора", "гори", "купа", "купу",
         "пачка", "пачку", "пачки", "банка", "банки", "банок", "форма", "формі", "формою", "склад", "ціна", "ціни",
         "фанат", "фанати", "фанатів", "любитель", "любителі", "любителів", "культ", "королева", "король", "бог",
         "богиня", "кіоск", "палатка", "вікно", "меню", "день", "свято", "фестиваль", "шматок", "шматка", "кусок",
         "тарілку", "столик", "стіл", "магазин", "ринок", "торговка", "торговці", "торговки", "вартість", "витрати",
         "витрат", "поменше", "більше", "менше", "багато", "мало", "трохи", "чимало", "повно", "стільки", "скільки",
         "немає", "нема", "не було", "не буде", "ні краплі", "ні грама", "запаси", "запасів", "запас", "залишки", "залишків", "нестача", "дефіцит", "бракує", "бракувати")
DAT_VERBS = ("подякувати", "дякувати", "дякую", "дякуєш", "дякує", "дякують", "дякуємо", "радий", "рада", "радіє",
             "радіти", "вірити", "вірить", "повірити", "відповідає", "допомагає", "допомогти", "присвятити",
             "присвячує", "присвятила", "присвятив", "поклонитися", "поклоняється", "вклонитися", "дивується")
INS_VERBS = ("обмінялися", "обмінявся", "обмінялася", "обмінялись", "обмінятися", "обмінюються", "ласувати", "ласує",
             "ласував", "ласувала", "ласували", "ділитися", "ділиться", "поділитися", "поділився", "поділилася",
             "ділилися", "пахне", "пахло", "смердить", "смерділо", "захоплюється", "захоплюватися", "пишається",
             "пишатися", "харчується", "харчуватися", "торгує", "торгувати", "торгували", "годує", "годувати",
             "накрити", "накрив", "накрила", "ситий", "ситі", "сита", "наїстися", "наївся", "наїлася", "об'їсться",
             "об'їлася", "об'ївся", "обпився", "обпилася", "поласувати", "поласував", "поласувала")
STARTS = re.compile(rf"(?:^|[.!?…:—«(\"]\s*|[,;]\s*(?:і|та|й|а|але|бо|що|коли|поки|якщо|як|тому що)?\s*|"
                    rf"(?<!{W})(?:і|та|й|а|але|бо|що|коли|поки|якщо|тому|ніж|чи|навіть|теж|також|"
                    rf"тепер|потім|тоді|вже|ще|лише|тільки|просто|раптом|нарешті|врешті|згодом|одразу|майже)\s+)"
                    rf"{PH}")
KINDS = {
    "prep": re.compile(rf"(?<!{W})(?:{'|'.join(PREPS)})\s+{PH}", re.I),
    "head": re.compile(rf"(?<!{W})(?:{'|'.join(HEADS)})\s+{PH}", re.I),
    "dat": re.compile(rf"(?<!{W})(?:{'|'.join(DAT_VERBS)})\s+(?:\w+\s+)?{PH}", re.I),
    "ins": re.compile(rf"(?<!{W})(?:{'|'.join(INS_VERBS)})\s+(?:\w+\s+)?{PH}", re.I),
    "nom": re.compile(rf"(?<!{W})(?:є|був|була|було|були|буде|будуть|стане|стало|лишився|лишилась|залишився|залишилась)\s+{PH}"),
    "adj": re.compile(rf"(?<!{W})(?!собою|мною|тобою|ним|нею)\w+(?:ий|ій|ого|ому|ою|ним|ній|ні|ої)\s+{PH}", re.I),
    "subj": re.compile(rf"(?:^|[.!?…—«(\"]\s*|,\s*(?:і|та|й|а|але|бо|що|коли|поки|якщо|як)?\s*|(?<!{W})(?:що|коли|якщо|бо|поки)\s+){PH}"),
}


def strings():
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text()
        lines = text.splitlines()
        tree = ast.parse(text, str(path))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(PH, node.value):
                if "food-ok" not in lines[node.lineno - 1] and id(node) not in docs:
                    yield path.relative_to(ROOT).as_posix(), node.lineno, node.value


def scan(every: bool = False) -> list[tuple[str, int, str, str]]:
    out = []
    for f, line, text in strings():
        marks = []
        for kind, rx in KINDS.items():
            marks += [(m.end() - len("{food}"), kind) for m in rx.finditer(text)]
        if every:
            marks += [(m.start(), "ok") for m in re.finditer(PH, text) if not any(abs(p - m.start()) < 2 for p, _ in marks)]
        for pos, kind in sorted(set(marks)):
            out.append((f, line, kind, text[max(0, pos - 40):pos + 50].replace("\n", " ")))
    return out


def main() -> None:
    hits = scan("--all" in sys.argv)
    for f, line, kind, ctx in hits:
        print(f"{f}:{line}: [{kind}] …{ctx}…")
    bad = [h for h in hits if h[2] != "ok"]
    print(f"# {len(bad)} suspicious {{food}}" + (f", {len(hits) - len(bad)} others" if len(hits) != len(bad) else ""))
    if "--strict" in sys.argv and bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
