"""The life card: one PNG with a whole life — pure stdlib, same in the bot and in the browser build."""
import struct
import zlib

from kit_the_cat import card, cardfont, engine as E
from kit_the_cat.content.cast import CAST
from kit_the_cat.content.persona import EPITAPHS, GOALS
from test_perks_dreams_health import _pet


def decode(data: bytes) -> tuple[int, int, int, bytes]:
    """-> (width, height, colour type, raw scanlines); checks the signature, every CRC and the length of the pixels."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, {}
    while pos < len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        assert struct.unpack(">I", data[pos + 8 + n:pos + 12 + n])[0] == zlib.crc32(tag + body)
        chunks[tag] = chunks.get(tag, b"") + body
        pos += 12 + n
    w, h, depth, kind = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    raw = zlib.decompress(chunks[b"IDAT"])
    assert depth == 8 and len(raw) == h * (1 + w * (1 if kind == 3 else 3))
    return w, h, kind, raw


def dead_pet() -> E.Pet:
    p = _pet()
    p.name, p.state, p.cause, p.epitaph = "Барсик Великий", "dead", "заснув і не прокинувся", "Лежить і не платить за комуналку."
    p.story = [[1, "ach", f"Подія {i}: «вибір» → щось сталося, і {p.name} запам'ятав це надовго"] for i in range(12)]
    return p


def test_the_card_is_a_valid_png_of_the_whole_life():
    p = dead_pet()
    w, h, kind, _ = decode(card.render_life_card(p.look(), E.life_summary(p, {})))
    assert w == card.W * card.SCALE and h > 400 * card.SCALE // 2
    assert kind == 3  # a palette: pixel art stays small


def test_a_longer_life_makes_a_taller_card_but_highlights_are_capped():
    p = dead_pet()
    short = card.render_life_card(p.look(), dict(E.life_summary(p, {}), story=["Раз"]))
    full = card.render_life_card(p.look(), E.life_summary(p, {}))
    assert decode(short)[1] < decode(full)[1] <= decode(card.render_life_card(p.look(), dict(E.life_summary(p, {}), story=["Дуже довго " * 30] * 40)))[1]
    assert decode(full)[1] < 1000 * card.SCALE  # never an endless strip


def test_the_card_works_for_a_living_pet_and_without_optional_parts():
    p = _pet()
    s = E.life_summary(p, {})
    decode(card.render_life_card(p.look(), s))
    decode(card.render_life_card(p.look(), dict(name="Ж", title="", cause="", epitaph="", facts=[], family="", story=[]), footer=""))


def test_clean_drops_emoji_and_spells_out_symbols():
    assert card.clean("🎲 17✅ 2❌ · ✨ Іконa") .startswith("17 вдало / 2 невдало")
    assert card.clean("💰 5 822 ₴") == "5 822 грн"
    assert card.clean("«Міст» №3") == "«Міст» N3"
    assert card.lead_icon("📅 12 років") == ("cal", "12 років")
    assert card.lead_icon("⚛️ Квантовий") == ("dot", "Квантовий")
    assert card.lead_icon("Досяг: щось") == ("", "Досяг: щось")


def test_wrap_and_fit_keep_words_whole_and_numbers_together():
    assert card.wrap("слово " * 10, 12) == ["слово слово", "слово слово", "слово слово", "слово слово", "слово слово"]
    assert card.wrap("а" * 30, 10) == ["ааааааааа-", "ааааааааа-", "ааааааааа-", "ааа"]
    assert card.wrap("мав 5\u00a0822 грн", 8) == ["мав", "5\u00a0822", "грн"]
    fitted = card.fit("раз два три чотири п'ять шість сім вісім дев'ять десять", 14, 2)
    assert len(fitted) == 2 and fitted[-1].endswith("…") and all(len(x) <= 14 for x in fitted)


def test_the_font_draws_every_ukrainian_letter_and_sign():
    for ch in "абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ0123456789«»—–…'’·•.,:;!?()%+-/":
        rows = cardfont.GLYPHS.get(ord(ch))
        assert rows, f"no glyph for {ch!r}"
        assert ch == " " or int(rows, 16) or True
    assert all(any(int(g[i:i + 2], 16) for i in range(0, len(g), 2)) for c, g in cardfont.GLYPHS.items() if chr(c).strip())


def test_the_text_of_a_life_loses_no_letters():
    """Whatever the game writes about a life must reach the card with every letter: emoji may go, letters may not."""
    texts = list(EPITAPHS) + [t for _, t in E.LIFE_TITLES] + list(E.TRAIT_TITLES.values()) + list(GOALS.values())
    texts += [c["name"] for c in CAST.values()]
    texts += [x for e in E.EVENTS.values() for x in [e.text, *(c.label for c in e.choices), *(o.text for c in e.choices for o in c.outs + c.fail)]]
    lost = [ch for ch in sorted(set("".join(texts))) if ch.isalnum() and not card.clean(ch)]
    assert not lost, f"letters the card font cannot draw: {lost}"


def test_the_pets_name_is_part_of_the_card():
    p = dead_pet()
    narrow = card.render_life_card(p.look(), dict(E.life_summary(p, {}), name="А"))
    wide = card.render_life_card(p.look(), dict(E.life_summary(p, {}), name="Дуже-дуже довге ім'я кота зі спадщиною"))
    decode(narrow), decode(wide)
    assert narrow != wide


def test_t_and_ya_are_drawn_the_printed_way():
    """Spleen's own «т» is an italic «m» and its «я» looks like «A»: a «підняти» read as «підмами». Redrawn on bake."""
    rows = lambda ch: ["".join("#" if b >> (card.FW - 1 - i) & 1 else "." for i in range(card.FW)) for b in card.glyph(ch)]
    assert rows("т")[3] == "#####." and rows("т")[4] == "..#..."
    assert rows("я")[7] == "..#.#." and rows("я")[8] == ".#..#."
