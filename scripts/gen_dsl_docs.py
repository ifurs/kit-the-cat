"""Generate docs/DSL.md — the reference for writing life events — from the code itself.

    uv run python scripts/gen_dsl_docs.py            # write docs/DSL.md
    uv run python scripts/gen_dsl_docs.py --check    # CI: fail if docs/DSL.md is stale or a contract key is undocumented

Everything here is read from the package (dsl docstring + contract sets, engine vocabularies, sprite registries),
so the reference can't drift from what the engine actually accepts.
"""
import sys
from pathlib import Path

from kit_the_cat import engine as E
from kit_the_cat import sprites
from kit_the_cat.content import dsl
from kit_the_cat.content.economy import EDUCATION, FOOD, JOBS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "DSL.md"
PLACEHOLDERS = {
    "{name}": "ім'я пета", "{owner}": "ім'я власника", "{food}": "улюблена їжа пета", "{dream}": "мрія",
    "{fear}": "страх", "{quirk}": "дивна звичка", "{temper}": "темперамент", "{money}": "гроші пета (число)",
    "{role}": "назва ролі (🧛 Вампір…)", "{other}": "ім'я іншого пета (лише social)",
    "{other_owner}": "власник іншого пета (лише social)",
    "{name_gen}": "ім'я пета в родовому відмінку (немає кого? — «Мурки»)",
    "{name_dat}": "давальний (кому? — «Мурці»)", "{name_acc}": "знахідний (кого? — «Мурку»)",
    "{name_ins}": "орудний (з ким? — «Муркою»)", "{name_loc}": "місцевий, без прийменника (на кому? — «Мурці»)",
    "{name_voc}": "кличний (Ей, «Мурко»!)",
    "{other_gen}…{other_voc}": "ті самі відмінки для імені іншого пета (лише social)",
}


def table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |" for r in rows]
    return "\n".join(out)


def undocumented() -> list[str]:
    doc = dsl.__doc__ or ""
    return sorted(k for k in dsl.KNOWN_FX | dsl.KNOWN_REQ if k not in doc)


def render() -> str:
    doc = (dsl.__doc__ or "").strip("\n")
    parts = [
        "# Довідник DSL пригод",
        "",
        "> Згенеровано `scripts/gen_dsl_docs.py` з коду — не редагуй вручну. Як писати гарні пригоди: "
        "[CONTENT_GUIDE.md](CONTENT_GUIDE.md).",
        "",
        f"Контракт: **{len(dsl.KNOWN_FX)} ефектів**, **{len(dsl.KNOWN_REQ)} вимог**, ролі: "
        f"{', '.join(sorted(dsl.ROLES))}. Рушій гарантовано підтримує кожен ключ; невідома вимога = подія недоступна.",
        "",
        "## Синтаксис (з `content/dsl.py`)",
        "",
        "```text",
        doc,
        "```",
        "",
        "## Підстановки в тексті",
        "",
        table(["Підстановка", "Що це"], [[f"`{k}`", v] for k, v in PLACEHOLDERS.items()]),
        "",
        "## Стати, навички, риси",
        "",
        table(["Ключ", "Що це"], [[f"`{k}`", v] for k, v in E.STATS.items()] if isinstance(E.STATS, dict)
              else [[f"`{k}`", "стат 0–100"] for k in sorted(dsl.STATS)]),
        "",
        table(["Навичка", "Значок"], [[f"`{k}`", v] for k, v in E.SKILLS.items()]),
        "",
        table(["Риса", "Назва"], [[f"`{k}`", v] for k, v in E.TRAITS.items()]),
        "",
        "## Життєві стати (`fame`, `auth`, `blat`, `fin`, `attr`) і рівні",
        "",
        "Значення 0–100; рівні з порогами " + " / ".join(str(x) for x in E.LIFE_STEPS)
        + ". Вимога `tier={\"fame\": 2}` = щонайменше 2-й рівень (рахуємо з 0). Гроші теж мають рівні (`tier={\"money\": 3}`).",
        "",
        table(["Ключ", "Що це", "Рівні"], [[f"`{k}`", f"{v[0]} {v[1]}", " → ".join(v[2])] for k, v in E.LIFE.items()]
              + [["`money`", "💰 статки (₴)", " → ".join(f"{n} ({'<0' if lo < 0 else f'≥{lo:g}'})" for lo, n in E.MONEY_TIERS)]]),
        "",
        "Високі рівні приносять дохід (реклама, «дах», відсотки, зарплата з блатом) і ризики (облави, НАБУ, скандали, "
        "податкова). Привабливість підсилює ріст популярності, фінграмотність зменшує втрати грошей.",
        "",
        "## 🎰 Казино (дія, не DSL)",
        "",
        table(["venue", "Назва", "Рівень статків", "Ставка ₴", "Час"],
              [[f"`{k}`", v[0], v[1], f"{v[2]}–{v[3]}", v[4]] for k, v in E.CASINO.items()]),
        "",
        "## Етапи життя",
        "",
        table(["stage", "Назва", "Від віку (років)"],
              [[s, n, "яйце ~%g год" % E.EGG_HOURS if s == 0 else E.STAGE_YEARS.get(s, 0)] for s, n in E.STAGES.items()]),
        "",
        "## Ролі (`role=`)",
        "",
        table(["role", "Назва", "Пасивка"], [[f"`{k}`", v["name"], v.get("desc", "")] for k, v in E.ROLES.items()]),
        "",
        "## Стосунки (`status=`)",
        "",
        table(["status", "Назва"], [[f"`{k}`", v] for k, v in E.STATUS_NAMES.items()]),
        "",
        "## Сезони й свята (`season=`)",
        "",
        table(["season", "Вікно (місяць, день)"], [[f"`{k}`", f"{a} → {b}"] for k, (a, b) in E.HOLIDAYS.items()]
              + [[f"`{s}`", ", ".join(str(m) for m, x in E.SEASON_OF_MONTH.items() if x == s)]
                 for s in ("winter", "spring", "summer", "autumn")]),
        "",
        "## Роботи (`job=`)",
        "",
        table(["job", "Назва", "₴/день", "Вимоги"],
              [[f"`{k}`", j["name"], j.get("pay") or "різна", j.get("req") or "—"] for k, j in JOBS.items()]),
        "",
        "## Освіта (`edu=`)",
        "",
        table(["edu", "Назва"], [[f"`{k}`", v] for k, v in EDUCATION.items()]),
        "",
        "## Їжа",
        "",
        table(["id", "Назва", "Ціна ₴"], [[f"`{k}`", v[0], v[1]] for k, v in FOOD.items()]),
        "",
        "## Дім / фон (`home=`, `bg=`)",
        "",
        "Модифікатори фону: " + ", ".join(f"`~{m}`" for m in getattr(sprites, "BG_MODS", {})) + " (напр. `farm~winter~snow`).",
        "",
        table(["id", "Назва"], [[f"`{k}`", v[0]] for k, v in sprites.BACKGROUNDS.items()]),
        "",
        "## Речі (`item=`)",
        "",
        f"Фіксовані речі нижче; будь-яку можна перефарбувати: `id@1…{len(sprites.TINTS) - 1}` "
        f"({', '.join(t[0] for t in sprites.TINTS[1:])}). Згенеровані речі: `item_slot=\"head\"` або "
        f"`gen:<slot>:<код>`.",
        "",
        table(["id", "Назва", "Слот"], [[f"`{k}`", v[0], v[1]] for k, v in sprites.ITEMS.items()]),
        "",
        "## Гени (`gene={...}`)",
        "",
        table(["Ген", "Значення"], [[f"`{g}`", ", ".join(f"`{v}`" for v in vals)] for g, vals in sprites.GENES.items()]),
        "",
        "## Світові події (рушій, не DSL)",
        "",
        table(["id", "Назва"], [[f"`{k}`", w.get("title", "")] for k, w in E.WORLD.items()]),
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    missing = undocumented()
    if missing:
        raise SystemExit(f"contract keys missing from the dsl.py docstring: {missing}")
    text = render()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != text:
            raise SystemExit("docs/DSL.md is stale: run `uv run python scripts/gen_dsl_docs.py`")
        print("docs/DSL.md is up to date")
        return
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    main()
