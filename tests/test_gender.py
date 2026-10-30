"""Pet gender: the field, names, {він|вона} pairs in texts, gendered display words and achievements."""
import random
import re
import sys
from pathlib import Path

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content.events import ALL
from kit_the_cat.content.persona import EPITAPHS, NAME_SUFFIX, NAMES
from kit_the_cat.grammar import GENDER_RX, decline, pick, template_errors
from test_perks_dreams_health import _pet

SRC = Path(__file__).resolve().parent.parent / "src" / "kit_the_cat"


def _girl(name: str = "Мурка") -> E.Pet:
    p = _pet()
    p.name, p.gender = name, "f"
    return p


# --- the field -------------------------------------------------------------------------------------

def test_an_old_document_without_gender_is_a_boy():
    d = _pet().to_dict()
    del d["gender"]
    assert E.Pet.from_dict(d).gender == "m"


def test_a_broken_gender_in_a_document_becomes_m():
    d = _pet().to_dict()
    d["gender"] = "x"
    assert E.Pet.from_dict(d).gender == "m"


def test_gender_survives_the_json_round_trip():
    p = _girl()
    assert E.Pet.from_dict(p.to_dict()).gender == "f"


def test_new_pet_takes_the_gender_it_is_given():
    for g in ("m", "f"):
        assert E.new_pet(1, 1, "Оля", "cat", [], random.Random(1), gender=g).gender == g


def test_new_pet_flips_a_coin_without_a_gender_and_heirs_get_a_fresh_one():
    eggs = [E.new_pet(1, 1, "Оля", "cat", [], random.Random(i)) for i in range(40)]
    assert {e.gender for e in eggs} == {"m", "f"}
    first = E.new_pet(1, 1, "Оля", "cat", [], random.Random(3), gender="f")
    heirs = [E.new_pet(1, 1, "Оля", "cat", [], random.Random(i), predecessor=first) for i in range(40)]
    assert {h.gender for h in heirs} == {"m", "f"} and all(h.gen == 2 for h in heirs)
    assert E.new_pet(1, 1, "Оля", "cat", [], random.Random(3), predecessor=first, gender="f").gender == "f"


# --- names ------------------------------------------------------------------------------------------

def test_every_species_has_twelve_names_for_each_gender():
    assert set(NAMES) == set(E.sprites.SPECIES)
    for species, by_gender in NAMES.items():
        assert set(by_gender) == {"m", "f"}
        for g, pool in by_gender.items():
            assert len(pool) >= 12 and len(set(pool)) == len(pool), (species, g)
        assert not set(by_gender["m"]) & set(by_gender["f"]), species


def test_girls_names_decline_as_girls_and_boys_as_boys():
    for by_gender in NAMES.values():
        for g, pool in by_gender.items():
            for n in pool:
                forms = set(decline(n, g).values())
                if n not in {"Ферарі", "Цок-Цок"}:
                    assert len(forms) > 1, (g, n)  # nothing is left indeclinable by accident


def test_make_name_uses_the_pool_and_the_tail_of_the_gender():
    for species, by_gender in NAMES.items():
        for g in ("m", "f"):
            names = {E.make_name(species, set(), random.Random(i), g) for i in range(120)}
            assert all(any(n.startswith(b) for b in by_gender[g]) for n in names), (species, g)
    girls = {E.make_name("cat", set(), random.Random(i), "f") for i in range(300)}
    boys = {E.make_name("cat", set(), random.Random(i), "m") for i in range(300)}
    assert "Мурка Велика" in girls and "Мурчик Великий" in boys
    assert not any(n.endswith(("ий", "ій")) for n in girls) and not any(n.endswith(("а", "я")) for n in boys if " " in n and " з " not in n and " Із " not in n)


def test_the_tail_pairs_agree_with_the_gender_of_the_name():
    for m, f in NAME_SUFFIX:
        assert m.split(" ")[:2] == f.split(" ")[:2] or m != f
        if m != f:
            assert f.endswith(("а", "я")) and not m.endswith(("а", "я")), (m, f)
    assert decline("Мурка Велика", "f")["gen"] == "Мурки Великої"
    assert decline("Мурка Третя", "f")["ins"] == "Муркою Третьою"
    assert decline("Мурка Вічно Голодна", "f")["dat"] == "Мурці Вічно Голодній"


def test_a_pet_declines_its_name_by_its_own_gender():
    assert _girl("Любов").name_in("gen") == "Любов"  # a feminine name on a consonant does not decline
    boy = _pet()
    boy.name = "Любов"
    assert boy.name_in("gen") == "Любова"
    assert _girl().name_in("ins") == "Муркою"


# --- {він|вона} pairs -------------------------------------------------------------------------------

def test_pick_takes_the_first_for_a_boy_and_the_second_for_a_girl():
    assert pick("{Вилупився|Вилупилася}!", "m") == "Вилупився!"
    assert pick("{Вилупився|Вилупилася}!", "f") == "Вилупилася!"
    assert pick("{a|b} {c|d}", "f") == "b d"


def test_pick_reads_the_other_pet_for_other_pairs():
    t = "{name} {знайшов|знайшла}, {other:відмовив|відмовила}"
    assert pick(t, "f", "m") == "{name} знайшла, відмовив"
    assert pick(t, "m", "f") == "{name} знайшов, відмовила"
    assert pick(t, "f", None) == "{name} знайшла, відмовив"  # no other pet: the first alternative


def test_fmt_picks_by_gender_and_a_name_is_never_a_template():
    t = "{name} {вилупився|вилупилася} і {other:сказав|сказала} {other_dat}: {money:>4}₴"
    boy, girl = _pet(), _girl()
    boy.name = "{a|b}"
    assert boy.fmt(t, girl) == "{a|b} вилупився і сказала Мурці:  500₴"
    assert girl.fmt(t, boy) == "Мурка вилупилася і сказав {a|b}:  500₴"
    assert girl.fmt("{name_gen}", boy) == "Мурки"


def test_the_pair_syntax_is_checked():
    for bad in ("{a|b|c}", "{a|{name}}", "{money:5|6}", "{|}", "{a|b", "a|b", "{other:a|b|c}"):
        assert template_errors(bad), bad
    for good in ("{a|b}", "{other:a|b}", "{name} {a|} x", "{Він не здався. Він|Вона не здалася. Вона} лягла"):
        assert not template_errors(good), good
    assert GENDER_RX.fullmatch("{other:відмовив|відмовила}")


def test_no_content_text_has_a_malformed_pair_and_every_pair_resolves():
    for e in ALL:
        texts = [e.text] + [c.label for c in e.choices] + [o.text for c in e.choices for o in c.outs + c.fail]
        for s in texts:
            assert not template_errors(s), (e.id, s)
            assert not GENDER_RX.search(pick(s, "f", "f")) and "|" not in pick(s, "m", "m"), (e.id, s)


# --- display words ----------------------------------------------------------------------------------

def test_epitaphs_speak_of_a_girl_in_the_feminine():
    assert any(GENDER_RX.search(s) for s in EPITAPHS)
    for s in EPITAPHS:
        assert not template_errors(s), s
        boy, girl = pick(s, "m"), pick(s, "f")
        assert "{" not in boy and "{" not in girl and "|" not in boy + girl
    p = _girl()
    p.state, p.stage = "alive", 3
    seen = set()
    for i in range(80):
        q = E.Pet.from_dict(p.to_dict())
        q.die("захворів", random.Random(i), natural=True)
        seen.add(q.epitaph)
        assert "{" not in q.epitaph
    assert any("Жила" in s or "Померла" in s or "Пішла" in s for s in seen)
    assert not any("Жив," in s or "Помер " in s for s in seen)


def test_a_dead_girl_is_reported_in_the_feminine():
    p = _girl()
    p.state, p.stage = "alive", 3
    p.die("захворіла", random.Random(1), natural=True)
    assert "Прожила" in p.log[-1][2]


def test_status_role_and_species_words_have_a_feminine_form():
    assert E.status_name("friend", "m") == "🤝 друг" and E.status_name("friend", "f") == "🤝 подруга"
    assert E.status_name("bestie", "f") == "💛 найкраща подруга"
    assert E.status_name("rival", "f") == "😤 суперниця" and E.status_name("enemy", "f") == "⚔️ ворогиня"
    assert E.status_name("crush", "f") == "😳 закоханість" and E.status_name("nope", "f") == "nope"
    assert set(E.STATUS_NAMES_F) == set(E.STATUS_NAMES)
    assert E.role_name("vampire", "m") == "🧛 Вампір" and E.role_name("vampire", "f") == "🧛 Вампірка"
    assert E.role_name("angel", "f") == "😇 Ангел" and E.role_name("", "f") == ""
    assert "королева" in E.role_desc("vampire", "f") and "король" in E.role_desc("vampire", "m")
    assert E.role_desc("quantum", "f") == E.ROLES["quantum"]["desc"]
    assert E.species_name("cat", "f") == "Кішечка" and E.species_name("cat", "m") == "Котик"
    assert E.species_name("pig", "f") == "Свинка" and E.species_name("???", "f") == "???"


def test_the_pet_speaks_of_its_role_and_hatching_by_gender():
    girl, boy = _girl(), _pet()
    girl.role = boy.role = "vampire"
    assert girl.fmt("{role}") == "🧛 Вампірка" and boy.fmt("{role}") == "🧛 Вампір"
    girl.set_role("")
    assert "зцілилася" in girl.log[-1][2] and "Вампірка" in girl.log[-1][2]
    girl.hatch(E.now())
    assert "Вилупилася" in girl.log[-1][2] and "(Кішечка)" in girl.log[-1][2]
    boy.hatch(E.now())
    assert "Вилупився" in boy.log[-1][2]


def test_a_status_note_names_the_other_pet_by_its_gender():
    a, b = _pet(), _girl()
    notes = a.apply({"status": "friend", "rel": 5}, b, random.Random(1))
    assert "🤝 подруга" in notes
    b2 = _pet()
    assert "🤝 друг" in a.apply({"status": "friend"}, b2, random.Random(1))


# --- achievements -----------------------------------------------------------------------------------

def _achievement_keys() -> set[str]:
    keys = set()
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        for rx in (r'achievement="([^"]+)"', r'\.ach\("([^"]+)"\)', r'ach=\("([^"]+)"', r'achievements\.append\("([^"]+)"\)',
                   r'ach\(\{\d+: "([^"]+)", \d+: "([^"]+)", \d+: "([^"]+)"'):
            for m in re.finditer(rx, text):
                keys.update(g for g in m.groups() if g)
    keys.update(t[2][4] for t in E.LIFE.values())
    keys.add(E.MONEY_TIERS[4][1][2:])
    return keys


def test_every_feminine_achievement_is_a_real_achievement_with_a_different_title():
    real = _achievement_keys()
    assert len(real) > 100
    for key, fem in E.ACH_F.items():
        assert key in real, f"{key!r} is not an achievement (typo, or it was renamed)"
        assert fem != key and "{" not in fem


def test_the_stored_key_stays_masculine_and_the_display_is_gendered():
    girl, boy = _girl(), _pet()
    assert girl.ach("Підкорив Говерлу") == "🏆 Підкорила Говерлу"
    assert girl.achievements == ["Підкорив Говерлу"]  # old documents and the bot's keys stay valid
    assert "Підкорила Говерлу" in girl.log[-1][2]
    assert boy.ach("Підкорив Говерлу") == "🏆 Підкорив Говерлу"
    assert girl.ach("Династія") == "🏆 Династія"  # the same for both
    assert girl.ach("Підкорив Говерлу") is None  # still unique by key
    assert girl.ach_name("Мільйонер (майже)") == "Мільйонерка (майже)"
    assert boy.ach_name("Мільйонер (майже)") == "Мільйонер (майже)"
    assert girl.ach_name("Невідоме") == "Невідоме"


def test_the_life_summary_shows_the_feminine_titles():
    girl = _girl()
    girl.ach("Підкорив Говерлу")
    girl.die("захворіла", random.Random(1), natural=True)
    facts = "\n".join(E.life_summary(girl)["facts"])
    assert "Підкорила Говерлу" in facts and "Підкорив" not in facts


@pytest.mark.parametrize("gender", ["m", "f"])
def test_a_new_pet_of_each_gender_plays_a_few_events(gender):
    rng = random.Random(7)
    p = E.new_pet(1, 1, "Оля", "dog", [], rng, gender=gender)
    p.hatch(E.now())
    for e in list(E.EVENTS.values())[:60]:
        text = p.fmt(e.text, _pet() if e.social else None)
        assert "|" not in text, e.id


# --- the content is converted ----------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gender_scan  # noqa: E402


def test_no_masculine_word_about_a_pet_is_left_in_the_content():
    left = gender_scan.scan()
    assert not left, "\n".join(f"{f}:{line}: {h.word} — {h.sentence[:70]}" for f, line, h in left[:10])


def test_every_allowlist_entry_still_matches_a_sentence_and_has_a_reason():
    sentences = {gender_scan.key_of(h.sentence) for _, _, text in gender_scan.strings() for h in gender_scan.scan_text(text)}
    for key, why in gender_scan.allowed().items():
        assert why, key
        assert key in sentences, f"stale allowlist entry: {key!r}"


def test_the_scanner_knows_a_pet_from_somebody_else():
    def words(text, social=False):
        return [(h.word, h.subj) for h in gender_scan.scan_text(text, social)]
    assert words("{name} знайшов гаманець.") == [("знайшов", "pet")]
    assert words("Знайшов гаманець і вирішив залишити.") == [("Знайшов", "pet"), ("вирішив", "pet")]
    assert words("Кум забрав гроші.") == [("забрав", "who")]
    assert words("Приїхав патруль, знайшов соску.") == [("Приїхав", "who"), ("знайшов", "who")]
    assert words("Ніхто не помітив.") == [("помітив", "who")]
    assert words("{other} образився.") == [("образився", "other")]
    assert words("Шарик, якого {name} підібрав, став зіркою.") == [("підібрав", "pet"), ("став", "who")]
    assert words("{name} вирішив, що настав час.") == [("вирішив", "pet"), ("настав", "who")]
    assert words("Записав {name_acc} у «хороші».", social=True) == [("Записав", "other")]
    assert words("Записав {name_acc} у «хороші».") == [("Записав", "who")]
    assert words("{Знайшов|Знайшла} гаманець.") == []  # a pair is already written
    assert words("Щасливий.") == [("Щасливий", "pet")]
    assert words("Щасливий випадок.") == []  # an attribute, not a predicate
    assert words("Ти став мером.") == [("став", "pet")]


def test_feminine_past_tense_forms():
    table = {"знайшов": "знайшла", "прийшов": "прийшла", "вирішився": "вирішилася", "зрозумів": "зрозуміла",
             "виріс": "виросла", "втік": "втекла", "переміг": "перемогла", "помер": "померла", "з'їв": "з'їла",
             "підвівся": "підвелася", "приніс": "принесла", "був": "була", "став": "стала", "ВТІК": "ВТЕКЛА",
             "Запам'ятав": "Запам'ятала", "хотів": "хотіла", "об'ївся": "об'їлася", "зустрів": "зустріла"}
    for masculine, fem in table.items():
        assert gender_scan.feminine(masculine) == fem, masculine
    for not_a_verb in ("друзів", "років", "колектив", "будинок", "вона", "шов"):
        assert gender_scan.feminine(not_a_verb) is None, not_a_verb


def test_every_text_renders_for_both_genders_without_leftovers():
    boy, girl = _pet(), _girl()
    for e in ALL:
        texts = [e.text] + [c.label for c in e.choices] + [o.text for c in e.choices for o in c.outs + c.fail]
        for s in texts:
            for me, other in ((boy, girl), (girl, boy), (girl, girl)):
                out = me.fmt(s, other if e.social else None)
                assert "|" not in out and "{" not in out.replace("{x}", ""), (e.id, out)


def test_achievement_keys_in_content_are_plain_masculine_strings():
    for e in ALL:
        for c in e.choices:
            for o in c.outs + c.fail:
                a = o.fx.get("achievement", "")
                assert "{" not in a and "|" not in a, (e.id, a)


# --- the engine speaks about a girl in the feminine -----------------------------------------------------------

def test_tiers_temperament_stage_and_job_have_feminine_forms():
    girl, boy = _girl(), _pet()
    girl.persona["temper"] = boy.persona["temper"] = "хуліган"
    assert girl.temper_name() == "хуліганка" and boy.temper_name() == "хуліган"
    assert girl.fmt("{temper}") == "хуліганка"
    girl.persona["temper"] = "зануда"
    assert girl.temper_name() == "зануда"
    for key, tier, fem in (("money", 3, "🚗 Мажорка"), ("auth", 4, "🕶 Хрещена мати"), ("attr", 3, "✨ Красуня району")):
        assert girl.tier_name(key, tier).endswith(fem.split(" ", 1)[1])
        assert not boy.tier_name(key, tier).endswith(fem.split(" ", 1)[1])
    assert girl.tier_name("money", 0) == "🕳 У боргах" or "борг" in girl.tier_name("money", 0)
    assert E.stage_name(3, "f") == "🧑 Доросла" and E.stage_name(3, "m") == "🧑 Дорослий"
    assert E.job_name("atb", "f") == "🛒 Касирка АТБ" and E.job_name("atb", "m") == "🛒 Касир АТБ"
    assert E.job_name("witch", "f") == E.job_name("witch", "m") and E.job_name("nope", "f") == "nope"
    for k, v in E.TEMPER_F.items():
        assert k in E.PERKS and v != k


def test_world_event_claims_and_life_summaries_are_gendered():
    girl = _girl()
    seen = set()
    for i in range(60):
        text, _, _ = E.world_claim(girl, "meteor", random.Random(i))
        assert "{" not in text
        seen.add(text)
    assert any("знайшла" in s or "надихалася" in s for s in seen)
    assert not any(" знайшов " in s or "надихався" in s for s in seen)
    girl.state, girl.stage, girl.flags["dream_done"] = "dead", 3, 1
    s = E.life_summary(girl)
    assert s["title"] == "Та, що здійснила свою мрію"


def test_a_girl_fights_and_wins_in_the_feminine():
    from kit_the_cat import battle as B
    a, b = _girl("Мурка"), _pet()
    a.name, b.name = "Мурка", "Барсик"
    a.state = b.state = "alive"
    texts = []
    for i in range(30):
        res = B.fight(B.Fighter.of(a, "aggressive"), B.Fighter.of(b, "aggressive"), random.Random(i))
        texts.append(res.text if res.text else " ".join(map(str, res.log)))
        assert "{" not in texts[-1]
    assert B.Fighter.of(a).gender == "f" and B.Fighter.of(b).gender == "m"
    win, lose = _girl("Мурка"), _pet()
    lose.name = "Барсик"
    B.aftermath(win, lose, random.Random(1))
    assert "Мурка перемогла Барсика" in win.log[-1][2] and "Барсик програв Мурці" in lose.log[-1][2]
