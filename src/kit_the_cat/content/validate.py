"""Validate content against the DSL contract:  uv run python -m kit_the_cat.content.validate"""
import re
from collections import Counter

from . import dsl
from .events import ALL
from .persona import EPITAPHS
from ..grammar import pick, template_errors


def main() -> None:
    errors = []
    ids = Counter(e.id for e in ALL)
    errors += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    for e in ALL:
        for k in e.req:
            if k not in dsl.KNOWN_REQ:
                errors.append(f"{e.id}: unknown req {k}")
        if not e.choices:
            errors.append(f"{e.id}: no choices")
        for c in e.choices:
            if max(len(pick(c.label, g, g)) for g in "mf") > 40:  # as the player reads it
                errors.append(f"{e.id}: label too long ({c.label})")
            for r in (e.req, c.req):
                for k in ("life", "tier", "tier_max"):
                    bad = [x for x in r.get(k, {}) if x not in dsl.LIFE | ({"money"} if k != "life" else set())]
                    errors += [f"{e.id}: unknown {k} key {x}" for x in bad]
            for k in c.req:
                if k not in dsl.KNOWN_REQ:
                    errors.append(f"{e.id}/{c.label}: unknown req {k}")
            for out in c.outs + c.fail:
                for k, v in out.fx.items():
                    if k not in dsl.KNOWN_FX:
                        errors.append(f"{e.id}/{c.label}: unknown effect {k}")
                    if k == "time":
                        try:
                            dsl.years(v)
                        except ValueError:
                            errors.append(f"{e.id}/{c.label}: bad time {v!r}")
                    if k == "role" and v and v not in dsl.ROLES:
                        errors.append(f"{e.id}: unknown role {v}")
                    if k == "other":
                        errors += [f"{e.id}: unknown other-effect {x}" for x in v if x not in dsl.KNOWN_FX]
            if not c.outs:
                errors.append(f"{e.id}/{c.label}: no outcomes")
        if max(len(pick(e.text, g, g)) for g in "mf") > 450:
            errors.append(f"{e.id}: text too long for a caption")
    texts = [(e.id, e.text) for e in ALL] + [(f"{e.id}/{c.label}", c.label) for e in ALL for c in e.choices]
    texts += [(f"{e.id}/{c.label}", o.text) for e in ALL for c in e.choices for o in c.outs + c.fail]
    texts += [(f"epitaph {s[:20]}", s) for s in EPITAPHS]
    errors += [f"{where}: {err}" for where, s in texts for err in template_errors(s)]
    from .persona import GOALS
    for e in ALL:
        for r in [e.req] + [c.req for c in e.choices]:
            ph = r.get("phase")
            if ph is not None and not set([ph] if isinstance(ph, str) else ph) <= dsl.PHASES:
                errors.append(f"{e.id}: unknown phase {ph!r}")
            if "season" in r:
                bad = [x for x in ([r["season"]] if isinstance(r["season"], (str, int)) else r["season"])
                       if isinstance(x, str) and x not in dsl.SEASONS]
                errors += [f"{e.id}: unknown season {x!r}" for x in bad]
            if "goal" in r and r["goal"] not in GOALS:
                errors.append(f"{e.id}: unknown goal {r['goal']!r}")
    by_id = {e.id: e for e in ALL}
    targets = set()
    for e in ALL:
        for c in e.choices:
            for out in c.outs + c.fail:
                if "then" in out.fx:
                    v = out.fx["then"]
                    ids = [v[0]] if isinstance(v, tuple) and isinstance(v[0], str) else list(v[0]) if isinstance(v, tuple) else []
                    ok = isinstance(v, tuple) and len(v) == 2 and bool(ids) and all(i in by_id and by_id[i].followup for i in ids)
                    try:
                        ok = ok and dsl.years(v[1]) > 0
                    except ValueError:
                        ok = False
                    if not ok:
                        errors.append(f"{e.id}/{c.label}: then={v!r} must be (followup event id | [ids], duration)")
                    else:
                        targets.update(ids)
                        if len(ids) > 1 and "ss" in by_id[ids[-1]].req:
                            errors.append(f"{e.id}/{c.label}: the last of then=([…]) is the fallback and must have no ss=")
                        if len(ids) > 1 and "ss" in out.fx and list(out.fx).index("ss") > list(out.fx).index("then"):
                            errors.append(f"{e.id}/{c.label}: write ss= before then=([…]): the ending reads the scores")
    errors += story_errors(by_id, targets)
    errors += series_errors(by_id)
    errors += [f"{e.id}: follow-up that nothing schedules (then= / step=)" for e in ALL if e.followup and e.id not in targets]
    print(f"{len(ALL)} events, {sum(len(e.choices) for e in ALL)} choices")
    print("\n".join(errors) or "OK")
    raise SystemExit(1 if errors else 0)


SERIES_RECAP = 90  # chars of a «Раніше в серіалі» line


def series_errors(by_id: dict) -> list[str]:
    """Series (ss=, recap=, finale=, series=): ids and endings exist, every outcome of an episode goes on (then=) or
    ends (finale=), recap lines are short, {recap_x} names a series, episodes are solo."""
    from .series import SERIES
    errors = []

    def key_ok(k: str) -> bool:
        sid, _, var = k.partition(".")
        return sid in SERIES and bool(var)
    for e in by_id.values():
        if e.series and e.series not in SERIES:
            errors.append(f"{e.id}: unknown series {e.series!r}")
        if e.series and e.social:
            errors.append(f"{e.id}: series episodes are solo (social=False)")
        for ph in re.findall(r"\{recap_([a-z_0-9]+)\}", e.text):
            if ph not in SERIES:
                errors.append(f"{e.id}: {{recap_{ph}}} is not a series")
        for r in [e.req] + [c.req for c in e.choices]:
            errors += [f"{e.id}: unknown series score {k!r} in req ss=" for k in r.get("ss", {}) if not key_ok(k)]
            errors += [f"{e.id}: unknown ending {sid}/{tag} in req finale="
                       for sid, tag in r.get("finale", {}).items()
                       if sid not in SERIES or (tag != "any" and tag not in SERIES[sid]["ends"])]
        for c in e.choices:
            for out in c.outs + c.fail:
                fx = out.fx
                where = f"{e.id}/{c.label}"
                errors += [f"{where}: unknown series score {k!r} in ss=" for k in fx.get("ss", {}) if not key_ok(k)]
                if "recap" in fx:
                    v = fx["recap"]
                    if not (isinstance(v, tuple) and len(v) == 2 and v[0] in SERIES):
                        errors.append(f"{where}: recap={v!r} must be (series id, line)")
                    elif max(len(pick(v[1], g, g)) for g in "mf") > SERIES_RECAP:
                        errors.append(f"{where}: recap line is longer than {SERIES_RECAP} characters")
                    elif e.series and v[0] != e.series:
                        errors.append(f"{where}: recap of another series")
                if "finale" in fx:
                    v = fx["finale"]
                    if not (isinstance(v, tuple) and len(v) == 2 and v[0] in SERIES and v[1] in SERIES[v[0]]["ends"]):
                        errors.append(f"{where}: finale={v!r} must be (series id, a key of its ends)")
                if e.series and "then" not in fx and "finale" not in fx:
                    errors.append(f"{where}: an outcome of a series episode needs then= or finale=")
    return errors


STORY_STEPS = 6  # a story is 1–6 decisions long


def story_errors(by_id: dict, targets: set) -> list[str]:
    """Stories (step=): steps exist, belong to the same story, are follow-ups; no loops; ≤ STORY_STEPS deep;
    a list of next steps ends with an unconditional fallback; sv= is used only inside stories."""
    errors, nxt = [], {}
    for e in by_id.values():
        if "sv" in e.req and not e.story:
            errors.append(f"{e.id}: sv= outside a story")
        if e.story and e.social:
            errors.append(f"{e.id}: stories are solo (social=False)")
        for c in e.choices:
            for out in c.outs + c.fail:
                if "sv" in out.fx and not e.story:
                    errors.append(f"{e.id}/{c.label}: sv= outside a story")
                if "step" not in out.fx:
                    continue
                v = out.fx["step"]
                ids = [v] if isinstance(v, str) else list(v) if isinstance(v, (list, tuple)) else []
                if not ids or not e.story:
                    errors.append(f"{e.id}/{c.label}: step={v!r} needs a story event and step ids")
                    continue
                for i in ids:
                    t = by_id.get(i)
                    if not t or not t.followup or t.story != e.story:
                        errors.append(f"{e.id}/{c.label}: step {i!r} must be a follow-up of the story «{e.story}»")
                    else:
                        targets.add(i)
                        nxt.setdefault(e.id, set()).add(i)
                last = by_id.get(ids[-1])
                if len(ids) > 1 and last and last.req:
                    errors.append(f"{e.id}/{c.label}: the last of step=[…] is the fallback and must have no req")

    def depth(i: str, seen: tuple) -> int:
        if i in seen:
            errors.append(f"{i}: story loops back ({' → '.join(seen + (i,))})")
            return 0
        return 1 + max((depth(j, seen + (i,)) for j in nxt.get(i, ())), default=0)
    for e in by_id.values():
        if e.story and not e.followup:
            d = depth(e.id, ())
            if d > STORY_STEPS:
                errors.append(f"{e.id}: story «{e.story}» is {d} steps deep (max {STORY_STEPS})")
    return errors


if __name__ == "__main__":
    main()
