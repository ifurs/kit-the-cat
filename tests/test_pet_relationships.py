"""Partnership must be mutual: no bigamy (found in simulation: a pet paired with a second partner without a breakup)."""
from kit_the_cat import engine as E


def _pet(owner: int, name: str) -> E.Pet:
    p = E.Pet(chat_id=1, owner_id=owner, name=name)
    p.state, p.stage = "alive", 3
    return p


def test_new_partner_breaks_old_partnership():
    a, b, c = _pet(1, "Підкова"), _pet(2, "Гарбузик"), _pet(3, "Гривастик")
    a.set_status(b, "partner")
    assert a.partner == b.pid and b.partner == a.pid
    c.set_status(b, "partner")  # Гривастик proposes to an already married Гарбузик
    assert b.partner == c.pid and c.partner == b.pid
    assert b.status[a.pid] == "ex"
    E.fix_partners([a, b, c])
    assert a.partner == ""
    assert a.status[b.pid] == "ex" and a.status[c.pid] == "enemy"
    assert any("💔" in entry[2] for entry in a.log)
    partners = [p.partner for p in (a, b, c) if p.partner]
    assert sorted(partners) == sorted([b.pid, c.pid])  # exactly one mutual couple


def test_vanished_partner_is_cleared():
    a, b = _pet(1, "А"), _pet(2, "Б")
    a.set_status(b, "partner")
    E.fix_partners([a])  # b's owner used /forget
    assert a.partner == "" and a.status[b.pid] == "ex"


def test_proposal_requires_both_single():
    e = E.EVENTS["soc_proposal"]
    assert e.req.get("partner") is False and e.req.get("other_partner") is False


def test_no_romance_for_babies():
    a, b = _pet(1, "Малюк"), _pet(2, "Дорослий")
    a.stage = 1
    a.apply({"status": "crush", "rel": 20, "baby": True}, b)
    assert a.status.get(b.pid) != "crush" and b.status.get(a.pid) != "crush"
    assert not a.heir and not b.heir
    assert a.rel[b.pid] == 20  # friendship still counts
    assert E.EVENTS["_date"].req.get("stage") == (2, 4) and E.EVENTS["_date"].req.get("other_stage") == 2


def test_teens_can_crush_but_not_marry():
    a, b = _pet(1, "А"), _pet(2, "Б")
    a.stage = b.stage = 2
    a.apply({"status": "crush"}, b)
    assert a.status[b.pid] == "crush"
    a.apply({"status": "partner"}, b)
    assert not a.partner
