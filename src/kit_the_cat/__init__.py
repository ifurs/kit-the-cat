"""Kit the Cat: the pet life-sim from the Кошеня bot. Pure Python, no required dependencies.

    from kit_the_cat import engine, sprites, battle
    pet = engine.new_pet(chat_id, owner_id, "Ім'я", "cat", others=[], rng=random.Random())
    pet.tick()                                  # time passes
    e, other = pet.pick_event(others, rng)      # a life event (313 of them, content/)
    res = pet.resolve(e, idx, other, rng)       # the owner's choice
    frames = sprites.frame_canvases(pet.look()) # pixel art; render_gif() needs the `images` extra (Pillow)

Storage is the host's job: pets are plain dicts (Pet.to_dict / Pet.from_dict). `storage.MemoryStore` is a ready
in-memory store; the Telegram bot keeps the same documents in SQLite.
"""
__version__ = "0.6.0"
