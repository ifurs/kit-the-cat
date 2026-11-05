"""Deterministic checks over the journals of scripts/playtest_lives.py: the issue classes the first playtest confirmed
(docs/PLAYTEST.md). Some are exact (STRICT: a hit is a bug); the word-based ones are leads to read, not verdicts.

    uv run python scripts/playtest_checks.py build/lives [--examples N] [--strict]
"""
import collections
import re
import sys
from pathlib import Path

from kit_the_cat import engine as E

STRANGER_EVENTS = {e.id for e in E.EVENTS.values() if list(e.req.get("status", ())) == [""]}

STEP = re.compile(r"^## Крок (\d+) · (\d+) р\. · .*?робота: ([^·]+)·")
EV = re.compile(r"^ПОДІЯ \[([^\]]+)\](?: з (.+?) \((дівчинка|хлопчик), (\d+) р\., статус: ([^)]*)\))?")
BOOZE = re.compile(r"\bпив[оауі]\b|\bпивом\b|пивк|самогон|горілк|шампанськ|\bвин[оау]\b|коньяк|настоянк|цигар|сигарет"
                   r"|вейп|похмілл|бармен|\bчарк", re.I)
SCHOOL = re.compile(r"\bшкол|садоч|\bвчител|\bоцінк|\bурок|домашк", re.I)
WORK = re.compile(r"на роботу|— робота|начальник|нарад[аіу]|колег|\bшеф\b", re.I)
ROMANCE_ID = re.compile(r"^(_date|soc_crush|soc_date|dt_|hol_kupala_jump|soc_baby|soc_proposal)")
ROMANCE_TXT = re.compile(r"пропозиці|💍|поцілу|про дітей", re.I)
FRACT = re.compile(r"[+−-]\d+\.\d+ ₴")

CHECKS = {
    "booze<18": "alcohol / smoking words while the pet is under 18",
    "romance-minor": "date/crush/proposal event across the 18 line, or a proposal under 16",
    "school<3": "school / kindergarten words under age 3",
    "lock-0": "locked-choice text «потрібно 0 ₴»",
    "meet-again": "a «never met» event (status=[\"\"]) with a pet met before",
    "work-nojob": "work words (boss, meeting, «на роботу») in the event/choices with no job",
    "mama-adult": "«Покликати маму» offered at 25+",
    "fract-money": "fractional money in notes",
    "girl-zastryah": "«застряг» about a girl pet",
}


def scan(path: Path, hits: dict) -> int:
    age, job, ev, other, oage, met, steps = 0, "—", "", "", 0, set(), 0
    girl = "дівчинка" in path.read_text().split("\n", 1)[0]
    for line in path.read_text().split("\n"):
        m = STEP.match(line)
        if m:
            steps, age, job = int(m[1]), int(m[2]), m[3].strip()
            continue
        where = f"{path.name} крок {steps} ({age} р.)"
        m = EV.match(line)
        if m:
            ev, other, oage = m[1], m[2] or "", int(m[4] or 0)
            if ev in STRANGER_EVENTS and other in met:
                hits["meet-again"].append(f"{where} [{ev}] з {other}")
            if other:
                met.add(other)
            if other and ROMANCE_ID.match(ev) and (age >= 18) != (oage >= 18):
                hits["romance-minor"].append(f"{where} [{ev}] з {other} ({oage} р.)")
        body = line.startswith(("ПОДІЯ", "ВАРІАНТИ", "ВИБІР", "РЕЗУЛЬТАТ", "ХВІСТ", "  · [event]", "  · [social]"))
        if not body:
            continue
        if age < 18 and BOOZE.search(line):
            hits["booze<18"].append(f"{where} [{ev}] {line[:140]}")
        if age < 16 and line.startswith("ВАРІАНТИ") and ROMANCE_TXT.search(line) and ROMANCE_ID.match(ev):
            hits["romance-minor"].append(f"{where} [{ev}] {line[:140]}")
        if age < 3 and SCHOOL.search(line) and not line.startswith("  ·"):
            hits["school<3"].append(f"{where} [{ev}] {line[:140]}")
        if "потрібно 0 ₴" in line:
            hits["lock-0"].append(f"{where} [{ev}]")
        if job == "—" and line.startswith(("ПОДІЯ", "ВАРІАНТИ", "ХВІСТ")) and WORK.search(line):
            hits["work-nojob"].append(f"{where} [{ev}] {line[:140]}")
        if age >= 25 and line.startswith("ВАРІАНТИ") and "Покликати маму" in line:
            hits["mama-adult"].append(f"{where} [{ev}]")
        if FRACT.search(line):
            hits["fract-money"].append(f"{where} [{ev}] {FRACT.search(line)[0]}")
        if girl and "застряг " in line:
            hits["girl-zastryah"].append(f"{where} {line[:120]}")
    return steps


STRICT = ("romance-minor", "lock-0", "mama-adult", "fract-money")   # exact: any hit is a bug


def main() -> None:
    d = Path(sys.argv[1])
    n_ex = int(sys.argv[sys.argv.index("--examples") + 1]) if "--examples" in sys.argv else 3
    hits: dict[str, list[str]] = collections.defaultdict(list)
    files = sorted(d.glob("life_*.md"))
    steps = sum(scan(f, hits) for f in files)
    print(f"{len(files)} lives, {steps} decisions")
    for k, desc in CHECKS.items():
        xs = hits.get(k, [])
        lives = len({x.split(" ", 1)[0].rstrip(":") for x in xs})
        print(f"{k:14} {len(xs):4} hits in {lives:3} lives · {desc}")
        for x in xs[:n_ex]:
            print("     ", x)
    bad = [k for k in STRICT if hits.get(k)]
    if "--strict" in sys.argv and bad:
        raise SystemExit(f"strict checks failed: {', '.join(bad)}")


if __name__ == "__main__":
    main()
