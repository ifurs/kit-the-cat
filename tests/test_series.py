"""Series (series=, ss=, recap=, finale=, then=[…]): scores and the recap live between episodes that are years apart,
the last decision of a season picks its ending by the scores, every path of every series ends and every ending can be
reached."""
import json
import random

from kit_the_cat import engine as E
from kit_the_cat.content import validate
from kit_the_cat.content.dsl import ch, ev, o
from kit_the_cat.content.events import ALL
from kit_the_cat.content.series import SERIES
from test_perks_dreams_health import _pet

ROOTS = {e.series: e for e in ALL if e.series and not e.followup}
STAGE = {"hut": (1, 7.0), "bottle": (2, 15.0), "cafe": (3, 30.0), "route": (3, 40.0)}


def _play(sid: str, seed: int, adult_coda: bool = True) -> tuple[E.Pet, list[E.Result]]:
    """Live a whole series with random choices; follow-ups come due one after another."""
    rng = random.Random(seed)
    stage, years = STAGE[sid]
    p = _pet(stage=stage)
    p.years = years
    p.skills = {s: {1: 11, 2: 20, 3: 30}[stage] for s in E.SKILLS}
    p.start(ROOTS[sid], None, "manual")
    out = []
    while p.pending and len(out) < 12:
        e = E.EVENTS[p.pending["id"]]
        idx = rng.choice([i for i, _ in p.options(e, None)])
        p.health = 100
        out.append(p.resolve(e, idx, None, rng))
        if not p.followups:
            break
        fid, due, *_ = p.followups.pop(0)
        p.years = max(p.years, due)
        if adult_coda:
            p.stage = max(p.stage, 3)
        assert p.eligible(E.EVENTS[fid], None, fresh=False), fid
        p.start(E.EVENTS[fid], None, "manual")
    return p, out


def test_there_are_several_series_with_enough_episodes_and_endings():
    assert len(SERIES) >= 3
    for sid, s in SERIES.items():
        eps = [e for e in ALL if e.series == sid]
        assert len(eps) >= 6, sid
        assert len(s["ends"]) >= 3, sid
        assert len(ROOTS[sid].choices) >= 3 and ROOTS[sid].once


def test_scores_recap_and_finale_are_kept_between_episodes():
    p = _pet()
    p.apply({"ss": {"hut.team": 2, "hut.craft": 1}, "recap": ("hut", "шалаш збудували з друзями")})
    p.apply({"ss": {"hut.team": 1}, "recap": ("hut", "{name} {вирішив|вирішила} лишитися")})
    assert p.series["hut"]["vars"] == {"team": 3, "craft": 1}
    assert p.series["hut"]["recap"][-1] == "Бублик вирішив лишитися"
    assert p.meets({"ss": {"hut.team": 3, "hut.craft": 1}}) and not p.meets({"ss": {"hut.team": 4}})
    assert p.meets({"ss": {"hut.team": (2, 3)}}) and not p.meets({"ss": {"hut.team": (0, 2)}})
    assert not p.meets({"ss": {"hut.law": 1}}) and not p.meets({"ss": {"unknown": 1}})
    assert not p.meets({"finale": {"hut": "any"}})
    p.apply({"finale": ("hut", "truce")})
    assert p.meets({"finale": {"hut": "truce"}}) and p.meets({"finale": {"hut": "any"}})
    assert not p.meets({"finale": {"hut": "legend"}}) and not p.meets({"finale": {"cafe": "any"}})
    assert any(k == "series" and "Шалаш за гаражами" in t for _, k, t in p.log)
    assert p.recap_text("hut") == "📺 Раніше: шалаш збудували з друзями; Бублик вирішив лишитися.\n\n"
    assert p.fmt("{recap_hut}Минуло п'ять років.").startswith("📺 Раніше: шалаш збудували")
    assert p.fmt("{recap_cafe}Привіт") == "Привіт"        # before the first episode there is nothing to recall


def test_the_recap_shows_the_last_four_lines():
    p = _pet()
    for i in range(10):
        p.apply({"recap": ("hut", f"крок {i}")})
    assert len(p.series["hut"]["recap"]) == E.RECAP_KEEP
    assert p.recap_text("hut").count(";") == E.RECAP_SHOWN - 1 and "крок 9" in p.recap_text("hut")
    assert "крок 2" not in p.recap_text("hut")


def test_then_with_a_list_picks_the_first_ending_whose_scores_hold():
    end = ["sr_hut_end_legend", "sr_hut_end_truce", "sr_hut_end_grown"]
    p = _pet()
    p.apply({"ss": {"hut.team": 4, "hut.craft": 2}, "then": (end, "1y")})
    assert [f[0] for f in p.followups] == ["sr_hut_end_legend"]
    q = _pet()
    q.apply({"ss": {"hut.peace": 2}, "then": (end, "1y")})
    assert [f[0] for f in q.followups] == ["sr_hut_end_truce"]
    r = _pet()
    r.apply({"then": (end, "1y")})
    assert [f[0] for f in r.followups] == ["sr_hut_end_grown"]


def test_an_episode_counts_and_the_result_tells_which_one():
    p, out = _play("hut", 1)
    assert [r.series["ep"] for r in out] == list(range(1, len(out) + 1))
    assert out[0].series["title"] == "Шалаш за гаражами" and not out[0].series["finale"]
    assert out[-2].series["finale"] and out[-2].series["ending"]    # the last episode of the season (a coda follows)
    assert p.series["hut"]["ep"] == len(out)


def test_series_survive_saving_and_old_documents_load_without_them():
    p, _ = _play("cafe", 2)
    q = E.Pet.from_dict(json.loads(json.dumps(p.to_dict())))
    assert q.series == p.series and q.series["cafe"]["end"] == "coda"
    old = p.to_dict()
    old.pop("series")
    assert E.Pet.from_dict(old).series == {}


def test_every_path_of_every_series_goes_through_to_an_ending_and_a_coda():
    for sid in SERIES:
        lengths = set()
        for seed in range(60):
            p, out = _play(sid, seed)
            ends = [r.series["finale"] for r in out if r.series["finale"]]
            lengths.add(len(out))
            assert ends and ends[0] in SERIES[sid]["ends"], (sid, seed)
            assert not p.pending and not [f for f in p.followups if f[0] in E.EVENTS and E.EVENTS[f[0]].series == sid]
            assert 5 <= len(out) <= 7, (sid, seed, len(out))
        assert lengths


def test_episodes_show_what_happened_before_and_leave_no_placeholders():
    for sid in SERIES:
        for seed in range(15):
            rng = random.Random(seed)
            texts = []
            stage, years = STAGE[sid]
            q = _pet(stage=stage)
            q.years = years
            q.start(ROOTS[sid], None, "manual")
            while q.pending:
                e = E.EVENTS[q.pending["id"]]
                texts.append((e, q.fmt(e.text)))
                q.health = 100
                q.resolve(e, rng.choice([i for i, _ in q.options(e, None)]), None, rng)
                if not q.followups:
                    break
                fid, due, *_ = q.followups.pop(0)
                q.years, q.stage = max(q.years, due), max(q.stage, 3)
                q.start(E.EVENTS[fid], None, "manual")
            assert texts[0][1].find("Раніше") == -1
            for e, t in texts[1:]:
                assert t.startswith("📺 Раніше: "), (e.id, t[:60])
            assert all("{" not in t and "}" not in t for _, t in texts)


def test_every_ending_of_every_series_can_be_reached():
    for sid, s in SERIES.items():
        seen = set()
        for seed in range(500):
            _, out = _play(sid, seed)
            seen |= {r.series["finale"] for r in out if r.series["finale"]}
            if seen == set(s["ends"]):
                break
        assert seen == set(s["ends"]), (sid, set(s["ends"]) - seen)


def test_a_season_may_not_be_picked_without_its_scores_and_codas_wait_for_the_finale():
    coda = E.EVENTS["sr_hut_s2"]
    p = _pet()
    assert not p.eligible(coda, None, fresh=False)
    p.apply({"finale": ("hut", "grown")})
    assert p.eligible(coda, None, fresh=False)
    assert not _pet().eligible(E.EVENTS["sr_hut_end_legend"], None, fresh=False)


def test_the_validator_catches_broken_series():
    def errs(*events):
        return validate.series_errors({e.id: e for e in events})
    ok = ev("t_ok", "x", ch("a", o("b", ss={"hut.team": 1}, recap=("hut", "ok"), then=("t_ok", "1y"))), series="hut")
    assert not errs(ok)
    bad = ev("t_bad", "{recap_nope}x", ch("a", o("b", ss={"nope.x": 1}, recap=("hut", "z" * 91), finale=("hut", "zzz")),
                                         o("c")), series="nope")
    text = " ".join(errs(bad))
    for part in ("unknown series 'nope'", "{recap_nope}", "unknown series score 'nope.x'", "longer than",
                 "finale=('hut', 'zzz')", "needs then= or finale="):
        assert part in text, part
