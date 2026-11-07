"""The cast: recurring characters who live alongside every pet (баба Галя, лікар Остап, двірняга Гаврик…).

A character has a fixed name and gender (so the texts below spell the cases out by hand), and each pet has its own
history with them: a bond (−6..6) that its decisions move, a state (here / away / gone) and the age at which they met.
The engine keeps it in `Pet.cast`; events read it with `req=dict(cast=…, cast_state=…, cast_for=…, nocast=…)` and
write it with `cast={"galya": +1}` / `cast_state={"galya": "away"}` (contract: content/dsl.py).
"""

BOND_MIN, BOND_MAX = -6, 6

# id: who they are. `name` is the short form for lists and notes; `who` says in a few words where they live.
CAST = {
    "galya": dict(name="баба Галя", who="сусідка з третього поверху", icon="👵", gender="f"),
    "ostap": dict(name="лікар Остап", who="ветеринар на розі", icon="🩺", gender="m"),
    "gavryk": dict(name="Гаврик", who="двірняга з гаражів", icon="🐕", gender="m"),
    "oksana": dict(name="Оксана з АТБ", who="касирка в «АТБ» за рогом", icon="🛒", gender="f"),
    "bohdan": dict(name="пан Богдан", who="старший колега", icon="🧑‍💼", gender="m"),
    "myron": dict(name="сусід Мирон", who="майстер із гаражу", icon="🔧", gender="m"),
    "solomiya": dict(name="Соломія Андріївна", who="вчителька", icon="📚", gender="f"),
    "iryna": dict(name="пані Ірина", who="бібліотекарка з районної бібліотеки", icon="📖", gender="f"),
    "petro": dict(name="дід Петро", who="голуб'ятник із даху дев'ятиповерхівки", icon="🕊", gender="m"),
    "yaroslav": dict(name="Ярослав Іванович", who="краєзнавець і сторож музею", icon="🗺", gender="m"),
}

# (lowest bond, how the relationship is called), read from the top
BOND_WORDS = [(5, "рідні"), (3, "дружні"), (1, "приязні"), (0, "знайомі"), (-2, "холодні"), (-6, "у сварці")]


def bond_word(bond: int) -> str:
    return next(w for lo, w in BOND_WORDS if bond >= lo)
