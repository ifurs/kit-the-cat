"""Validate content against the DSL contract:  uv run python -m kit_the_cat.content.validate"""
from collections import Counter

from . import dsl
from .events import ALL


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
            if len(c.label) > 40:
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
        if len(e.text) > 450:
            errors.append(f"{e.id}: text too long for a caption")
    by_id = {e.id: e for e in ALL}
    targets = set()
    for e in ALL:
        for c in e.choices:
            for out in c.outs + c.fail:
                if "then" in out.fx:
                    v = out.fx["then"]
                    ok = isinstance(v, tuple) and len(v) == 2 and v[0] in by_id and by_id[v[0]].followup
                    try:
                        ok = ok and dsl.years(v[1]) > 0
                    except ValueError:
                        ok = False
                    if not ok:
                        errors.append(f"{e.id}/{c.label}: then={v!r} must be (followup event id, duration)")
                    else:
                        targets.add(v[0])
    errors += [f"{e.id}: follow-up that nothing schedules (then=)" for e in ALL if e.followup and e.id not in targets]
    print(f"{len(ALL)} events, {sum(len(e.choices) for e in ALL)} choices")
    print("\n".join(errors) or "OK")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
