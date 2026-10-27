"""The developer scripts stay in sync with the engine and the content stays free of dead ends."""
import sys
from pathlib import Path

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content.dsl import ch, o

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import content_stats  # noqa: E402
import gen_dsl_docs  # noqa: E402


@pytest.mark.parametrize("stage", [1, 2, 3, 4])
@pytest.mark.parametrize("skill,diff", [("cha", 10), ("int", 40), ("luck", 25), ("str", 60)])
def test_typical_chance_mirrors_pet_chance(stage, skill, diff):
    sk, luck, level = content_stats.TYPICAL[stage]
    p = E.Pet(chat_id=1, owner_id=1)
    p.stage, p.mood, p.health = stage, 50, 100
    p.skills = {s: sk for s in E.SKILLS}
    p.skills["luck"] = luck if skill != "luck" else sk
    p.xp = 20 * (level - 1) ** 2
    assert p.level == level
    assert p.chance(ch("x", o("y"), check=(skill, diff))) == pytest.approx(content_stats.typical_chance(skill, diff, stage))


def test_content_has_no_dead_ends():
    events, where = content_stats.load()
    assert {e.id for e in events} == {i for i in E.EVENTS if not i.startswith("_")}  # _date etc. are engine built-ins
    assert content_stats.analyse(events, where)["errors"] == []


def test_dsl_reference_is_complete_and_fresh():
    assert gen_dsl_docs.undocumented() == []
    assert gen_dsl_docs.OUT.read_text() == gen_dsl_docs.render()
