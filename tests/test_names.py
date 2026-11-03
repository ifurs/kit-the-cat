"""Names in the text: the short form («Мурчик»), the whole name only when two names would be confused."""
import random

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content.persona import NAME_SUFFIX, NAMES, short_name
from test_perks_dreams_health import _pet


def _named(name: str, gender: str = "m") -> E.Pet:
    p = _pet()
    p.name, p.gender = name, gender
    return p


@pytest.mark.parametrize("name,short", [
    ("Мурчик Великий", "Мурчик"), ("Мурка Велика", "Мурка"), ("Бублик з Троєщини", "Бублик"),
    ("Бублик Із Жмеринки", "Бублик"), ("Мурка Вічно Голодна", "Мурка"), ("Пуфик №7", "Пуфик"),
    ("Мурчик", "Мурчик"), ("Пан Кіт", "Пан Кіт"), ("", ""),
])
def test_short_name_drops_only_a_known_tail(name, short):
    assert short_name(name) == short


def test_every_generated_name_has_a_base_from_the_pool():
    for species, by_gender in NAMES.items():
        for g, col in (("m", 0), ("f", 1)):
            for base in by_gender[g]:
                for pair in NAME_SUFFIX:
                    assert short_name(base + pair[col]) == base, (base, pair)


def test_the_text_uses_the_short_name_and_its_cases():
    p = _named("Барсик Великий")
    assert p.fmt("{name} їсть. Дати {name_dat}. Не бійся {name_gen}.") == "Барсик їсть. Дати Барсикові. Не бійся Барсика."
    assert p.fmt("{other} і {other_ins}", _named("Рекс з Троєщини")) == "Рекс і Рексом"


def test_two_pets_with_the_same_short_name_keep_the_whole_names():
    a, b = _named("Барсик Великий"), _named("Барсик з Троєщини")
    assert a.fmt("{name} і {other}", b) == "Барсик Великий і Барсик з Троєщини"
    assert a.fmt("{name_gen} і {other_gen}", b) == "Барсика Великого і Барсика з Троєщини"
    assert a.fmt("{name}", None) == "Барсик"  # alone in the scene: no confusion


def test_a_pet_named_like_someone_it_knows_keeps_the_whole_name():
    p = _named("Гаврик Молодший")
    assert p.fmt("{name}") == "Гаврик"
    p.meet("gavryk")  # the stray dog Гаврик
    assert p.fmt("{name}") == "Гаврик Молодший"


def test_journal_notes_use_the_short_name_too():
    p = _named("Барсик Великий")
    p.money = -4000
    p.stage = 3
    p._daily(random.Random(1))
    p.note("x", "-")
    p.note("tier", f"{p.called()} {p.g('піднявся', 'піднялася')}")
    p._tiers()
    text = " ".join(x[2] for x in p.log)
    assert "Барсик" in text and "Великий" not in text


def test_make_name_gives_most_pets_a_plain_name_and_avoids_a_taken_short_name():
    rng = random.Random(7)
    names = [E.make_name("cat", set(), rng, "m") for _ in range(400)]
    tailed = sum(n != short_name(n) for n in names) / len(names)
    assert 0.2 < tailed < 0.4
    taken = {"Мурчик", "Барсик з Троєщини"}
    for i in range(60):
        n = E.make_name("cat", taken, random.Random(i), "m")
        assert short_name(n) not in {"Мурчик", "Барсик"}
