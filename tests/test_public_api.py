"""Public API snapshot: the names hosts can import from the modules documented in docs/INTEGRATION.md.

The snapshot is tests/fixtures/public_api.json. After an intended API change, update it and bump the version:

    uv run python tests/test_public_api.py --update

A removed or renamed name breaks hosts (major bump per CONTRIBUTING.md); an added one is new API (minor bump).
"""
import importlib
import inspect
import json
import sys
import types
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "fixtures" / "public_api.json"
# docs/INTEGRATION.md: «Public API» plus the helpers it tells hosts to call (grammar, persona, storage contract)
MODULES = ["engine", "sprites", "card", "content.economy", "battle", "grammar", "content.persona", "storage"]
SKIP = {"TYPE_CHECKING", "annotations"}
KEEP = {"clock"}  # documented patchable hooks: listed whatever they are bound to (time.time, a test's fake clock)


def _public(names_values, owner: str | None = None) -> list[str]:
    out = []
    for n, v in names_values:
        if n.startswith("_") or n in SKIP or isinstance(v, types.ModuleType):
            continue
        if n not in KEEP and (inspect.isclass(v) or inspect.isfunction(v) or inspect.isbuiltin(v)):
            if owner and not (getattr(v, "__module__", "") or "").startswith("kit_the_cat"):
                continue  # stdlib helpers imported into the module (random, field, Callable, …)
        out.append(n)
    return sorted(out)


def current() -> dict[str, list[str]]:
    api = {}
    for m in MODULES:
        mod = importlib.import_module(f"kit_the_cat.{m}")
        api[m] = _public(vars(mod).items(), owner=mod.__name__)
        for n in api[m]:
            cls = getattr(mod, n)
            if inspect.isclass(cls) and cls.__module__ == mod.__name__:  # methods, properties and dataclass fields
                members = {k: None for c in reversed(cls.__mro__) if c.__module__.startswith("kit_the_cat") for k in vars(c)}
                members.update(dict.fromkeys(getattr(cls, "__dataclass_fields__", {})))
                api[f"{m}.{n}"] = _public(members.items())
    return api


def test_public_api_matches_snapshot():
    want = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    have = current()
    removed = {k: sorted(set(v) - set(have.get(k, []))) for k, v in want.items()}
    removed = {k: v for k, v in removed.items() if v} | {k: ["(whole namespace)"] for k in want if k not in have}
    added = {k: sorted(set(v) - set(want.get(k, []))) for k, v in have.items()}
    added = {k: v for k, v in added.items() if v}
    msg = []
    if removed:
        msg.append("REMOVED/RENAMED public API — a BREAKING change for hosts (major bump, see CONTRIBUTING.md "
                   "«Versioning»; or keep an alias):\n" + "\n".join(f"  {k}: {', '.join(v)}" for k, v in removed.items()))
    if added:
        msg.append("NEW public API — a minor bump, and document it in docs/INTEGRATION.md if hosts should use it "
                   "(prefix with _ if it is internal):\n" + "\n".join(f"  {k}: {', '.join(v)}" for k, v in added.items()))
    if msg:
        msg.append("If intended: uv run python tests/test_public_api.py --update, bump pyproject.toml, note it in CHANGELOG.md.")
    assert not msg, "\n\n".join(msg)


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        sys.exit(__doc__)
    SNAPSHOT.write_text(json.dumps(current(), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT}")
