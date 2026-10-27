# 🐾 Kit the Cat

Тамагочі-симулятор життя з українського Telegram-бота «Кошеня» — тепер окремою грою. Чистий Python, без обов'язкових залежностей.

- **6 видів** (порося, кошеня, цуценя, лисеня, лоша, аксолотль), геном на ≈6·10⁶⁶ комбінацій, процедурний піксель-арт,
  у чаті немає двійників
- **313 пригод і 1134 рішення**: ланцюжки (кримінал, секта, політика, космос…), стосунки, весілля, діти-гібриди,
  8 надприродних ролей, сюжетні повороти, роботи, гроші, речі, що змінюють спрайт
- **Бої й турніри**: пасивки видів, спецприйоми рис, ульти ролей, рейтинг Elo
- **Пісочниця** без Telegram: у браузері (Pyodide) або локальний сервер

Детально: [docs/PET.md](docs/PET.md) · галерея: [docs/sprites/](docs/sprites/) · ідеї: [docs/ideas/PET_IDEAS.md](docs/ideas/PET_IDEAS.md)

## Як модуль

```bash
uv add "kit-the-cat[images] @ git+https://github.com/ifurs/kit-the-cat@v0.1.0"
```

```python
import random
from kit_the_cat import engine as E, sprites

rng = random.Random()
pet = E.new_pet(chat_id=-100, owner_id=42, owner_name="Оля", species="axolotl", others=[], rng=rng)
pet.tick()                                   # минає час: голод, вік, зарплата, смерть
e, other = pet.pick_event([pet], rng)        # пригода
res = pet.resolve(e, 0, other, rng)          # рішення власника → текст, ефекти, твісти
gif = sprites.render_gif(pet.look())         # потребує extra `images` (Pillow)
doc = pet.to_dict()                          # збереження — справа хоста (JSON-документ)
```

Контракт контенту: `kit_the_cat/content/dsl.py` (ефекти й вимоги, які рушій гарантовано підтримує).

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
```

Сторонні компоненти браузерної збірки: [Pyodide](https://github.com/pyodide/pyodide) (MPL-2.0), завантажується з npm при збірці.
