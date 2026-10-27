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
            for k in c.req:
                if k not in dsl.KNOWN_REQ:
                    errors.append(f"{e.id}/{c.label}: unknown req {k}")
            for out in c.outs + c.fail:
                for k, v in out.fx.items():
                    if k not in dsl.KNOWN_FX:
                        errors.append(f"{e.id}/{c.label}: unknown effect {k}")
                    if k == "role" and v and v not in dsl.ROLES:
                        errors.append(f"{e.id}: unknown role {v}")
                    if k == "other":
                        errors += [f"{e.id}: unknown other-effect {x}" for x in v if x not in dsl.KNOWN_FX]
            if not c.outs:
                errors.append(f"{e.id}/{c.label}: no outcomes")
        if len(e.text) > 450:
            errors.append(f"{e.id}: text too long for a caption")
    print(f"{len(ALL)} events, {sum(len(e.choices) for e in ALL)} choices")
    print("\n".join(errors) or "OK")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
