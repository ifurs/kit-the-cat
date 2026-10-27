"""DSL contract between pet content and the engine (see CLAUDE.md "DSL contract")."""
import inspect
from collections import Counter

import pytest

from kit_the_cat.content import dsl, validate
from kit_the_cat.content.events import ALL


def _fx_items():
    for e in ALL:
        for c in e.choices:
            for out in c.outs + c.fail:
                yield e, c, out.fx


def test_validator_runs_and_reports(capsys):
    with pytest.raises(SystemExit) as exc:
        validate.main()
    assert exc.value.code in (0, 1)
    out = capsys.readouterr().out
    assert "events" in out.splitlines()[0]
    assert (exc.value.code == 0) == out.rstrip().endswith("OK")


def test_event_ids_unique():
    dup = [i for i, n in Counter(e.id for e in ALL).items() if n > 1]
    assert not dup, f"duplicate event ids: {dup}"


def test_content_uses_only_known_effects():
    bad = [(e.id, k) for e, _, fx in _fx_items() for k in fx if k not in dsl.KNOWN_FX]
    bad += [(e.id, f"other.{k}") for e, _, fx in _fx_items() for k in fx.get("other", {}) if k not in dsl.KNOWN_FX]
    assert not bad, f"unknown effects: {bad[:20]}"


def test_content_uses_only_known_requirements():
    bad = [(e.id, k) for e in ALL for k in e.req if k not in dsl.KNOWN_REQ]
    bad += [(e.id, k) for e in ALL for c in e.choices for k in c.req if k not in dsl.KNOWN_REQ]
    assert not bad, f"unknown requirements: {bad[:20]}"


def test_roles_are_known():
    bad = [(e.id, fx["role"]) for e, _, fx in _fx_items() if fx.get("role") and fx["role"] not in dsl.ROLES]
    assert not bad


def test_every_event_has_choices_with_outcomes():
    assert all(e.choices for e in ALL)
    assert all(c.outs for e in ALL for c in e.choices)


def _source_handles(src: str, key: str) -> bool:
    return f'"{key}"' in src or f"'{key}'" in src


def test_engine_implements_every_known_effect():
    from kit_the_cat import engine
    src = inspect.getsource(engine.Pet.apply)
    implicit = dsl.STATS | dsl.SKILLS | dsl.TRAITS
    missing = sorted(k for k in dsl.KNOWN_FX - implicit if not _source_handles(src, k))
    assert not missing, f"engine.Pet.apply ignores: {missing}"


def test_engine_implements_every_known_requirement():
    from kit_the_cat import engine
    src = inspect.getsource(engine.Pet.meets)
    missing = sorted(k for k in dsl.KNOWN_REQ if not _source_handles(src, k))
    assert not missing, f"engine.Pet.meets ignores: {missing}"
