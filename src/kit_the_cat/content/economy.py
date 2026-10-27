"""Jobs, education, shop prices, food and the daily cost of living. Owned by the engine side."""

# id: name, daily pay (₴), requirements (engine.meets), daily trait/skill drift, uniform items, workplace background.
# open=True → can be applied for at the 💼 job centre (others come only from storylines).
JOBS = {
    "atb": dict(name="🛒 Касир АТБ", pay=120, req={}, drift={"toxic": 0.5, "cha": 0.3}, items=["apron@1"], bg="kitchen",
                open=True),
    "courier": dict(name="🛵 Кур'єр на самокаті", pay=150, req={"skill": {"str": 15}}, drift={"str": 0.6, "party": 0.2},
                    items=["backpack@3"], bg="kyiv", open=True),
    "taxi": dict(name="🚕 Таксист «Шансон FM»", pay=170, req={}, drift={"toxic": 0.4, "cha": 0.4}, items=["cap"],
                 bg="kyiv", open=True),
    "cook": dict(name="🌯 Кухар у шаурмичній", pay=150, req={}, drift={"glutton": 0.6, "str": 0.2}, items=["chef", "apron"],
                 bg="kitchen", open=True),
    "farmer": dict(name="🚜 Фермер", pay=170, req={"skill": {"str": 25}}, drift={"patriot": 0.4, "str": 0.5},
                   items=["cowboy@3"], bg="farm", open=True),
    "it": dict(name="💻 Айтішник", pay=380, req={"skill": {"int": 45}}, drift={"int": 0.6, "party": -0.2, "mood": -1},
               items=["hoodie", "laptop", "nerd"], bg="office", open=True),
    "blogger": dict(name="📸 Блогер", pay=0, req={"skill": {"cha": 35}}, drift={"cha": 0.6, "toxic": 0.3},
                    items=["phone", "sunglasses@8"], bg="club", pay_range=(-50, 700), open=True),
    "dj": dict(name="🎧 Діджей", pay=240, req={"trait": {"party": 15}}, drift={"party": 0.8, "health": -1},
               items=["headphones", "sunglasses"], bg="club", open=True),
    "witch": dict(name="🔮 Потомствена ворожка", pay=200, req={"trait": {"mystic": 15}}, drift={"mystic": 0.8, "cha": 0.2},
                  items=["wizard@7", "cards"], bg="mystic", pay_range=(50, 450), open=True),
    "doctor": dict(name="🩺 Лікар", pay=340, req={"edu": "med"}, drift={"int": 0.3, "love": 0.3, "mood": -1},
                   items=["coat", "mask"], bg="hospital", open=True),
    "volunteer": dict(name="🇺🇦 Волонтер", pay=60, req={"trait": {"patriot": 15}}, drift={"patriot": 1, "cha": 0.5, "love": 0.3},
                      items=["vyshyvanka", "scarf"], bg="field", open=True),
    "deputy": dict(name="🏛 Депутат", pay=350, req={"flag": "politics"}, drift={"toxic": 0.6, "gambler": 0.3},
                   items=["suit", "tie@6"], bg="palace", pay_range=(200, 1200)),
    "bandit": dict(name="🕶 Бандит", pay=400, req={"flag": "crime"}, drift={"toxic": 0.6, "dark": 0.5, "str": 0.3},
                   items=["tracksuit", "chain"], bg="kyiv", risk=("jail", 0.08)),
    "poker": dict(name="🃏 Професійний покерист", pay=0, req={"skill": {"luck": 40}}, drift={"gambler": 1},
                  items=["cards", "monocle"], bg="casino", pay_range=(-400, 900), open=True),
    "prophet": dict(name="🕯 Пророк секти", pay=450, req={"flag": "cult"}, drift={"mystic": 0.8, "dark": 0.4},
                    items=["robe", "wand"], bg="mystic"),
    "astronaut": dict(name="👨‍🚀 Космонавт", pay=600, req={"flag": "space"}, drift={"int": 0.4, "luck": 0.2},
                      items=["spacesuit", "jetpack"], bg="space"),
    "military": dict(name="🪖 Захисник", pay=300, req={"flag": "army"}, drift={"patriot": 1, "str": 0.6, "dark": 0.2},
                     items=["helmet", "bronik"], bg="bunker"),
    # role jobs
    "night_guard": dict(name="🌙 Нічний сторож на кладовищі", pay=260, req={"role": "any"}, drift={"dark": 0.8},
                        items=["cape@10"], bg="cemetery", open=True),
    "exorcist": dict(name="✝️ Екзорцист за викликом", pay=320, req={"trait": {"mystic": 30}}, drift={"mystic": 0.6, "str": 0.2},
                     items=["book", "robe@1"], bg="mystic", pay_range=(100, 600), open=True),
}

EDUCATION = {
    "school": "🏫 Атестат (з трійками)",
    "ptu": "🔧 Диплом ПТУ",
    "kpi": "🎓 Диплом КПІ",
    "mohyla": "📜 Диплом Могилянки",
    "med": "⚕️ Медичний",
    "courses": "💾 Курси «Айті за 2 тижні»",
    "hogwarts": "🧙 Заочна школа магії",
}

# shop prices; items not listed here can only be found in events
PRICES = {
    "cap": 150, "beanie": 120, "partyhat": 80, "flower": 60, "bow": 90, "cowboy": 300, "chef": 200, "headphones": 450,
    "helmet": 700, "foil": 40, "oseledets": 250, "vinok": 280, "wizard": 600,
    "sunglasses": 200, "nerd": 180, "monocle": 900, "mustache": 220, "clown": 100, "mask": 30, "vr": 1500,
    "chain": 1200, "bib": 50, "bowtie": 250, "tie": 300, "scarf": 220, "bell": 90, "korali": 500,
    "vyshyvanka": 800, "suit": 1500, "hoodie": 400, "tracksuit": 350, "apron": 120, "coat": 600,
    "cape": 700, "backpack": 300,
    "coffee": 60, "mic": 500, "phone": 900, "bottle": 80, "book": 120, "flowers": 150, "guitar": 1100, "balloon": 40,
    "cane": 150, "laptop": 2500, "sausage": 90, "cards": 70, "sabre": 1800,
    "notes": 300, "sparkles": 2000, "hearts": 600,
}
BACKGROUND_PRICES = {
    "khrushchovka": 0, "meadow": 0, "kitchen": 400, "farm": 800, "office": 1500, "club": 1200, "sea": 3000,
    "mountains": 2500, "kyiv": 2000, "mystic": 1800, "love": 900, "field": 700, "space": 15000, "palace": 25000,
    "casino": 5000, "bunker": 1500, "toxic": 300, "ruins": 100, "cemetery": 666,
}
# daily upkeep of a home ("комуналка"), ₴; homes not listed cost 1% of the price
HOME_UPKEEP = {"khrushchovka": 15, "meadow": 0, "ruins": 0, "palace": 400, "space": 250}

FOOD = {
    # id: name, price, effects
    "crust": ("🍞 Хліб з водою", 0, dict(hunger=20, mood=-4)),
    "mivina": ("🍜 Мівіна", 10, dict(hunger=25, health=-3, mood=3)),
    "salo": ("🥓 Сало", 30, dict(hunger=35, mood=5, glutton=1, patriot=0.5)),
    "varenyky": ("🥟 Вареники", 35, dict(hunger=35, mood=10, love=0.5, glutton=0.5)),
    "borsch": ("🍲 Борщ", 40, dict(hunger=40, health=5, patriot=1)),
    "beer": ("🍺 Пиво", 45, dict(hunger=10, mood=20, health=-6, party=1.5)),
    "salad": ("🥗 Салатик", 50, dict(hunger=25, health=8, mood=-5)),
    "shrooms": ("🍄 Дивні гриби", 60, dict(hunger=5, mood=15, health=-8, mystic=2)),
    "shawarma": ("🌯 Шаурма", 70, dict(hunger=50, mood=8, health=-2, glutton=1)),
    "cake": ("🎂 Київський торт", 120, dict(hunger=45, mood=25, health=-4, glutton=2, love=0.5)),
    "blood": ("🩸 Донорська кров", 90, dict(hunger=60, mood=10, dark=1)),     # vampires only
    "brains": ("🧠 Мізки з ринку", 80, dict(hunger=60, int=1, dark=1)),       # zombies only
}
ROLE_FOOD = {"blood": "vampire", "brains": "zombie"}

POCKET = 60          # ₴/day for babies and teens ("бабуся передала")
PENSION = 90         # ₴/day for unemployed elders
WELFARE = 25         # ₴/day for unemployed adults
WEALTH_TAX = (3000, 0.02)   # above 3000 ₴ — 2%/day goes to «податкова»
MYSTERY_BOX = 300
POTION = 3500
