"""List the {name} / {other} placeholders that probably stand in the wrong case — a helper for a human, not a judge.

    uv run python scripts/case_scan.py              # every suspicious placeholder: file:line: [kind] context
    uv run python scripts/case_scan.py --strict     # exit 1 on the obvious kind (preposition + {name}); CI gate
    uv run python scripts/case_scan.py --all        # also the weak kinds (mid-sentence objects), for a full review

{name} is the nominative. After a preposition, as an object, as a possessor or in a call it needs {name_gen},
{name_dat}, {name_acc}, {name_ins}, {name_loc} or {name_voc} (see content/dsl.py and grammar.py).
Kinds: prep (preposition right before the placeholder — always wrong), plural (an impersonal plural verb right
after it: «{name} запросили»), head (a noun that wants the genitive right before it: «пости {name}»), voc (a
call: «Ей, {name}!»), mid (the placeholder is neither the start of a clause nor next to a conjunction; may be an
object or a subject after its verb — read it). `# case-ok` on the line of a string silences it.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "kit_the_cat"

W = r"[\w'’-]"
PH = r"\{(?:name|other)\}"
PREPS = ("у", "в", "до", "від", "для", "без", "біля", "про", "на", "за", "над", "під", "перед", "між", "з", "із",
         "зі", "з-за", "з-під", "по", "при", "через", "серед", "замість", "проти", "навколо", "коло", "заради",
         "навпроти", "окрім", "крізь", "після", "біля")
HEADS = ("відео", "фото", "фотка", "фотку", "фотографію", "пост", "пости", "постів", "мама", "мамі", "тато", "батьки",
         "бабуся", "бабусі", "дід", "кум", "двері", "дверей", "хвіст", "голос", "ім'я", "імені", "історія", "історію",
         "лапи", "лапу", "лапа", "друзі", "друзям", "підписники", "підписників", "фани", "канал", "блог", "сторінка",
         "сторінку", "профіль", "гаманець", "гаманця", "вухо", "вуха", "очі", "ніс", "морда", "мордочка", "шерсть",
         "дім", "квартира", "квартиру", "будка", "будку", "кімната", "кімнату", "миска", "миску", "вечеря", "день",
         "весілля", "похорон", "концерт", "виступ", "ювілей", "портрет", "статуя", "пам'ятник", "відповідь",
         "власник", "хазяїн", "господар", "господиня", "сусід", "сусіди", "життя", "кар'єра", "кар'єру", "мрія",
         "мрію", "страх", "борг", "борги", "рахунок", "картка", "картку", "паспорт", "диплом", "лист", "листи")
PLURAL_VERB = r"\w+(?:ли|лись|ють|уть|ять|мо|ємо|ите)"
KINDS = {
    "prep": re.compile(rf"(?<!{W})(?:{'|'.join(PREPS)})\s+{PH}", re.I),
    "plural": re.compile(rf"{PH}\s+(?!і\b|й\b|та\b|з\b|із\b|зі\b|разом\b)(?:не\s+)?{PLURAL_VERB}\b"),
    "head": re.compile(rf"(?<!{W})(?:{'|'.join(HEADS)})\s+{PH}", re.I),
    "voc": re.compile(rf"(?:^|[«\"—:] ?|(?:Ей|Гей|Агов|Слухай|Слухайте|Привіт|Дякую|Вибач|Вітаю|Ну|О|Ах),? ){PH}[,!?]"),
}
STARTS = re.compile(rf"(?:^|[.!?…:—«(\"]\s*|[,;]\s*(?:і|та|й|а|але|бо|що|коли|поки|якщо|як|тому що)?\s*|"
                    rf"(?<!{W})(?:і|та|й|а|але|бо|що|коли|поки|якщо|як|тому|поки|ніж|чи|навіть|теж|також|"
                    rf"тепер|потім|тоді|вже|ще|лише|тільки|просто|раптом|нарешті|врешті|згодом|одразу|майже|навіть)\s+)"
                    rf"{PH}$")  # the placeholder ends the window: only this one counts


def strings():
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text()
        lines = text.splitlines()
        tree = ast.parse(text, str(path))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(PH, node.value):
                if "case-ok" not in lines[node.lineno - 1] and id(node) not in docs:
                    yield path.relative_to(ROOT).as_posix(), node.lineno, node.value


def scan(weak: bool = False) -> list[tuple[str, int, str, str]]:
    out = []
    for f, line, text in strings():
        marks = []
        for kind, rx in KINDS.items():
            marks += [(m.start(), kind) for m in rx.finditer(text)]
        if weak:
            for m in re.finditer(PH, text):
                if not STARTS.search(text[max(0, m.start() - 40):m.end()]) and not any(m.start() <= p <= m.end() + 40 for p, _ in marks):
                    marks.append((m.start(), "mid"))
        for pos, kind in sorted(set(marks)):
            out.append((f, line, kind, text[max(0, pos - 30):pos + 60].replace("\n", " ")))
    return out


def main() -> None:
    weak = "--all" in sys.argv
    hits = scan(weak)
    for f, line, kind, ctx in hits:
        print(f"{f}:{line}: [{kind}] …{ctx}…")
    counts = {k: sum(1 for h in hits if h[2] == k) for k in (*KINDS, "mid")}
    print(f"# {len(hits)} hits " + " ".join(f"{k}={n}" for k, n in counts.items() if n))
    if "--strict" in sys.argv and counts["prep"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
