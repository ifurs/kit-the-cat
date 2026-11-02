"""The favourite food in every case (persona.FOOD_FORMS, Pet.fmt {food_*}) and the scanner that keeps {food} an
accusative. The table below is the spec: every form was checked by hand, not produced by the code under test.
Order of a row: називний, родовий, давальний, орудний, місцевий; the key is the stored accusative."""
import sys
from pathlib import Path

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content.events import ALL
from kit_the_cat.content.persona import FOOD_CASES, FOOD_FORMS, FOODS, food_in
from test_perks_dreams_health import _pet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import food_scan  # noqa: E402

SPEC = {
    "сало": ("сало", "сала", "салу", "салом", "салі"),
    "вареники з вишнями": ("вареники з вишнями", "вареників з вишнями", "вареникам з вишнями", "варениками з вишнями", "варениках з вишнями"),
    "борщ": ("борщ", "борщу", "борщу", "борщем", "борщі"),
    "шаурму": ("шаурма", "шаурми", "шаурмі", "шаурмою", "шаурмі"),
    "мівіну": ("мівіна", "мівіни", "мівіні", "мівіною", "мівіні"),
    "холодець": ("холодець", "холодцю", "холодцю", "холодцем", "холодці"),
    "сирники": ("сирники", "сирників", "сирникам", "сирниками", "сирниках"),
    "кавун": ("кавун", "кавуна", "кавуну", "кавуном", "кавуні"),
    "деруни": ("деруни", "дерунів", "дерунам", "дерунами", "дерунах"),
    "оселедець під шубою": ("оселедець під шубою", "оселедця під шубою", "оселедцю під шубою", "оселедцем під шубою", "оселедці під шубою"),
    "олів'є": ("олів'є", "олів'є", "олів'є", "олів'є", "олів'є"),
    "банош": ("банош", "баношу", "баношу", "баношем", "баноші"),
    "пампушки з часником": ("пампушки з часником", "пампушок з часником", "пампушкам з часником", "пампушками з часником", "пампушках з часником"),
    "голубці": ("голубці", "голубців", "голубцям", "голубцями", "голубцях"),
    "київський торт": ("київський торт", "київського торта", "київському торту", "київським тортом", "київському торті"),
    "зелений борщ": ("зелений борщ", "зеленого борщу", "зеленому борщу", "зеленим борщем", "зеленому борщі"),
    "налисники": ("налисники", "налисників", "налисникам", "налисниками", "налисниках"),
    "капусняк": ("капусняк", "капусняку", "капусняку", "капусняком", "капусняку"),
    "пиріжки з печінкою": ("пиріжки з печінкою", "пиріжків з печінкою", "пиріжкам з печінкою", "пиріжками з печінкою", "пиріжках з печінкою"),
    "шашлик": ("шашлик", "шашлику", "шашлику", "шашликом", "шашлику"),
    "кров'янку": ("кров'янка", "кров'янки", "кров'янці", "кров'янкою", "кров'янці"),
    "гречку з котлетою": ("гречка з котлетою", "гречки з котлетою", "гречці з котлетою", "гречкою з котлетою", "гречці з котлетою"),
    "хот-дог з АЗС": ("хот-дог з АЗС", "хот-дога з АЗС", "хот-догу з АЗС", "хот-догом з АЗС", "хот-догу з АЗС"),
    "шоколадку «Корона»": ("шоколадка «Корона»", "шоколадки «Корона»", "шоколадці «Корона»", "шоколадкою «Корона»", "шоколадці «Корона»"),
    "вергуни": ("вергуни", "вергунів", "вергунам", "вергунами", "вергунах"),
    "мандарини": ("мандарини", "мандаринів", "мандаринам", "мандаринами", "мандаринах"),
    "крученики": ("крученики", "кручеників", "крученикам", "кручениками", "кручениках"),
    "печеню в горщику": ("печеня в горщику", "печені в горщику", "печені в горщику", "печенею в горщику", "печені в горщику"),
    "чебуреки з вокзалу": ("чебуреки з вокзалу", "чебуреків з вокзалу", "чебурекам з вокзалу", "чебуреками з вокзалу", "чебуреках з вокзалу"),
    "куліш": ("куліш", "куліша", "кулішеві", "кулішем", "куліші"),
}


def _girl() -> E.Pet:
    g = _pet()
    g.gender = "f"
    return g


@pytest.mark.parametrize("acc,forms", SPEC.items())
def test_every_food_has_its_five_forms(acc, forms):
    assert FOOD_FORMS[acc] == forms
    assert [food_in(acc, c) for c in FOOD_CASES] == list(forms)
    assert food_in(acc) == food_in(acc, "acc") == acc


def test_the_spec_covers_exactly_the_foods_a_pet_can_get():
    assert set(SPEC) == set(FOODS) == set(FOOD_FORMS)
    assert len(FOODS) == len(set(FOODS))


def test_a_food_the_table_does_not_know_stays_as_it_is_in_every_case():
    for case in (*FOOD_CASES, "acc"):
        assert food_in("піцу з ананасами", case) == "піцу з ананасами"
    assert food_in("", "gen") == ""


@pytest.mark.parametrize("me", [_pet, _girl], ids=["boy", "girl"])
def test_fmt_fills_every_case_of_the_food(me):
    p = me()
    p.persona["food"] = "шаурму"
    got = p.fmt("{food} | {food_nom} | {food_gen} | {food_dat} | {food_ins} | {food_loc}")
    assert got == "шаурму | шаурма | шаурми | шаурмі | шаурмою | шаурмі"
    p.persona["food"] = "вареники з вишнями"
    assert p.fmt("{food_gen} {food_ins}") == "вареників з вишнями варениками з вишнями"


def test_an_old_document_keeps_its_stored_food_and_loads():
    p = _pet()
    p.persona["food"] = "шаурму"
    q = E.Pet.from_dict(p.to_dict())
    assert q.persona["food"] == "шаурму"
    assert q.fmt("Головне — {food_nom}, а не {food}") == "Головне — шаурма, а не шаурму"
    q.persona["food"] = "суші з лососем"  # a food from an older or a foreign list
    assert q.fmt("{food_gen}|{food_nom}|{food}") == "суші з лососем|суші з лососем|суші з лососем"
    q.persona.pop("food")  # a document without one falls back to the default
    assert q.fmt("{food_nom} {food}") == "борщ борщ"


def test_every_text_with_a_food_renders_for_every_food_and_both_genders():
    texts = []
    for e in ALL:
        texts += [(e.id, e.text)] + [(e.id, c.label) for c in e.choices]
        texts += [(e.id, o.text) for c in e.choices for o in c.outs + c.fail]
    texts += [("tail", t[0]) for t in E.TAILS]
    texts = [(i, s) for i, s in texts if "{food" in s]
    assert len(texts) > 50
    for me in (_pet(), _girl()):
        for acc in FOODS:
            me.persona["food"] = acc
            for eid, s in texts:
                out = me.fmt(s, _girl() if me.gender == "m" else _pet())
                assert "{" not in out and "}" not in out and "|" not in out, (eid, acc, out)


def test_the_scanner_finds_a_food_in_the_wrong_case():
    def kinds(text):
        return [k for k, rx in food_scan.KINDS.items() if rx.search(text)]
    assert kinds("Головне — {food}.") == ["subj"]
    assert kinds("Вам би поменше {food}") == ["head"]
    assert kinds("Колекцію банок з-під {food} продали.") == ["prep"]
    assert kinds("Обидва в {food}.") == ["prep"]
    assert kinds("Ми обмінялися {food}.") == ["ins"]
    assert kinds("Подякувати терапевтові {food}") == ["dat"]
    assert kinds("Принести домашній {food}") == ["adj"]
    assert kinds("Добре, що є {food}.") == ["nom"]
    assert kinds("У новинах сказали, що {food} дарує безсмертя.") == ["subj"]
    for fine in ("{name} їсть {food}.", "Піти по {food}", "Запросити на {food}", "Взяти з собою {food}",
                 "{Наготував|Наготувала} {food} на всіх", "Головне — {food_nom}.", "банок з-під {food_gen}"):
        assert kinds(fine) == [], fine


def test_no_food_in_the_content_stands_in_the_wrong_case():
    left = food_scan.scan()
    assert not left, "\n".join(f"{f}:{line}: [{k}] {ctx}" for f, line, k, ctx in left[:10])
