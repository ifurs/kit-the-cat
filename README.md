# 🐾 Kit the Cat

Тамагочі-симулятор життя з українського Telegram-бота «Кошеня» — тепер окремою грою. Чистий Python, без обов'язкових залежностей.

- **7 видів** (порося, кошеня, цуценя, лисеня, лоша, аксолотль, пташка), геном на ≈10⁶⁷ комбінацій, процедурний піксель-арт,
  у чаті немає двійників
- **478 пригод і 1598 рішень**, ранні рішення повертаються наслідками через роки (арки); життєві стати з рівнями (популярність, авторитет, блат, фінграмотність, привабливість, статки), казино; ланцюжки (кримінал, секта, політика, космос…), стосунки, весілля, діти-гібриди,
  8 надприродних ролей, сюжетні повороти, роботи, гроші, речі, що змінюють спрайт
- **Бої й турніри**: пасивки видів, спецприйоми рис, ульти ролей, рейтинг Elo
- **Пісочниця** без Telegram: у браузері (Pyodide) або локальний сервер

Детально: [docs/PET.md](docs/PET.md) · галерея: [docs/sprites/](docs/sprites/) · ідеї: [docs/ideas/PET_IDEAS.md](docs/ideas/PET_IDEAS.md)

Пишеш пригоди? [Як писати](docs/CONTENT_GUIDE.md) · [довідник DSL](docs/DSL.md) · [внесок](CONTRIBUTING.md) · [зміни](CHANGELOG.md)

## Як модуль

```bash
uv add "kit-the-cat[images] @ git+https://github.com/ifurs/kit-the-cat@v0.4.0"
```

```python
import random
from kit_the_cat import engine as E, sprites

rng = random.Random()
pet = E.new_pet(chat_id=-100, owner_id=42, owner_name="Оля", species="axolotl", others=[], rng=rng)
pet.tick()                                   # минає час: вік у роках, побут, зарплата, смерть
e, other = pet.pick_event([pet], rng)        # пригода
res = pet.resolve(e, 0, other, rng)          # рішення власника → текст, ефекти, твісти
gif = sprites.render_gif(pet.look())         # потребує extra `images` (Pillow)
doc = pet.to_dict()                          # збереження — справа хоста (JSON-документ)
```

Контракт контенту: `kit_the_cat/content/dsl.py` (ефекти й вимоги, які рушій гарантовано підтримує). Інтеграція у свій застосунок: [docs/INTEGRATION.md](docs/INTEGRATION.md), будова: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Пісочниця

```bash
uv run kit-the-cat                         # http://127.0.0.1:8777, збереження в play.json (extra `sandbox`)
uv run python scripts/build_web.py            # build/web/: гра в браузері (Pyodide), статичний сайт
uv run python scripts/deploy_pages.py         # публікація на GitHub Pages
```

## Розробка

```bash
uv sync
uv run pytest -q
uv run python -m kit_the_cat.content.validate
uv run python scripts/gallery.py              # спрайт-галереї в docs/sprites/
uv run python scripts/uniqueness.py           # 200 петів в одному чаті: 0 двійників
uv run python scripts/content_stats.py --gaps # де контенту замало
uv run python scripts/content_gate.py         # усі перевірки контенту, зокрема українська мова (ua_lint)
uv run python scripts/balance.py              # симуляція району петів і цілі балансу
uv run python scripts/preview.py --items cap  # аркуш спрайтів для малювання
```

Сторонні компоненти браузерної збірки: [Pyodide](https://github.com/pyodide/pyodide) (MPL-2.0), завантажується з npm при збірці.
