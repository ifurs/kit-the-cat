"""The Ukrainian lint catches what it promises and stays quiet on good text."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ua_lint  # noqa: E402


@pytest.mark.parametrize("text,needle", [
    ("Він пішов в магазин і купив хлеб, ы", "Russian letter"),
    ("Cабо з Lатинською «С»", "Latin look-alike"),
    ("Пам’ять", "typographic apostrophe"),
    ("{name} зустрів {nmae}", "unknown placeholder"),
    ("«Відкрита лапка без закриття", "unbalanced"),
])
def test_errors(text, needle):
    errors, _ = ua_lint.check(text)
    assert any(needle in e for e in errors), errors


@pytest.mark.parametrize("text,needle", [
    ("Пожалуйста, не рішай за мене", "будь ласка"),
    ("Слідуючий тиждень", "наступн"),
    ("Він получив премію", "отрима"),
    ("Свіже мясо на ринку", "м'яс"),
    ("Чекай... я зараз", "…"),
    ("Кіт - це сила", "—"),
    ('Він сказав "привіт"', "«»"),
    ("Щас буде весело", "зараз"),
])
def test_warnings(text, needle):
    _, warnings = ua_lint.check(text)
    assert any(needle in w for w in warnings), warnings


@pytest.mark.parametrize("text", [
    "Щасливий {name} з'їв усе до краплі й розповів усьому під'їзду.",
    "Екзаменаційний білет — найстрашніший папірець.",
    "«Вітаю», — сказав {other} до {other_owner}.",
])
def test_good_text_is_clean(text):
    assert ua_lint.check(text) == ([], [])


def test_whole_game_is_clean():
    errs = [(f, ln, e) for f, ln, t, frag in ua_lint.strings() for e in ua_lint.check(t, frag)[0]]
    assert not errs, errs[:5]
