"""One command for every content check — the automatic half of the event pipeline (kit-event-writer skill).

    uv run python scripts/content_gate.py            # all gates, short summary, exit 1 if any fails
    uv run python scripts/content_gate.py --quick    # skip the balance simulation

Gates: DSL contract (validate), Ukrainian lint (errors fail; warnings are listed for a human/agent to judge),
a name in the wrong case (case_scan: a preposition right before {name}),
story dead ends and hard checks (content_stats), generated DSL reference fresh, content tests, balance targets.
"""
import subprocess
import sys
import time

GATES = [
    ("DSL contract", ["python", "-m", "kit_the_cat.content.validate"]),
    ("Ukrainian lint", ["python", "scripts/ua_lint.py", "--strict", "--warnings"]),
    ("Name cases", ["python", "scripts/case_scan.py", "--strict"]),
    ("Dead ends & hard checks", ["python", "scripts/content_stats.py", "--strict", "--gaps"]),
    ("DSL reference fresh", ["python", "scripts/gen_dsl_docs.py", "--check"]),
    ("Content tests", ["python", "-m", "pytest", "-q", "tests/test_dsl_contract.py", "tests/test_ua_lint.py",
                       "tests/test_consequences.py", "tests/test_tooling.py", "tests/test_grammar.py",
                       "tests/test_gender.py"]),
    ("Balance", ["python", "scripts/balance.py", "--pets", "24", "--days", "50"]),
]


def main() -> None:
    failed = []
    for name, cmd in GATES:
        if "--quick" in sys.argv and name == "Balance":
            continue
        t = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = r.returncode == 0
        print(f"{'✅' if ok else '❌'} {name} ({time.time() - t:.1f} s)")
        out = (r.stdout + r.stderr).strip()
        if not ok or name in ("Ukrainian lint", "Dead ends & hard checks"):
            tail = "\n".join(out.splitlines()[-25:])
            print("   " + tail.replace("\n", "\n   "))
        if not ok:
            failed.append(name)
    print(f"\n{'All gates passed' if not failed else 'FAILED: ' + ', '.join(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
