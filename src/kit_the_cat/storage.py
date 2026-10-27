"""Storage for the sandbox: pets, journal, graves and per-chat state, kept in memory.

`dump()` / `load()` turn it into one JSON string, so the browser can keep a save in localStorage and the local
server can keep it in a file. The Telegram bot uses its own SQLite storage with the same method names.
"""
import json
import time

_LOG_CAP = 4000


def _copy(d):
    return json.loads(json.dumps(d, ensure_ascii=False))


class MemoryStore:
    def __init__(self):
        self.pets: dict[str, dict] = {}
        self.logs: list[dict] = []
        self.graves: list[dict] = []
        self.chats: dict[str, dict] = {}
        self.next_id = 1

    async def init(self) -> None:
        pass

    async def close(self) -> None:
        pass

    # --- pets ------------------------------------------------------------------------------------
    async def get_pet(self, chat_id: int, owner_id: int) -> dict | None:
        d = self.pets.get(f"{chat_id}:{owner_id}")
        return _copy(d) if d else None

    async def chat_pets(self, chat_id: int) -> list[dict]:
        return [_copy(d) for d in self.pets.values() if d["chat_id"] == chat_id]

    async def save_pets(self, docs: list[dict]) -> None:
        ts = int(time.time())
        for d in docs:
            log, d["log"] = d.get("log") or [], []
            for t, k, x in log:
                self.logs.append(dict(id=self.next_id, chat_id=d["chat_id"], owner_id=d["owner_id"],
                                      gen=d.get("gen", 1), ts=int(t), kind=k, text=x))
                self.next_id += 1
            if d.get("state") == "dead" and not d.get("flags", {}).get("_buried"):
                d.setdefault("flags", {})["_buried"] = 1
                self.graves.append(dict(chat_id=d["chat_id"], owner_id=d["owner_id"], gen=d.get("gen", 1),
                                        name=d.get("name"), cause=d.get("cause"), died=int(d.get("died") or ts)))
            self.pets[f"{d['chat_id']}:{d['owner_id']}"] = _copy(d)
        if len(self.logs) > _LOG_CAP:
            self.logs = self.logs[-_LOG_CAP:]

    async def pet_log(self, chat_id: int, owner_id: int, gen: int | None = None, limit: int = 30,
                      kinds: tuple = ()) -> list[dict]:
        rows = [r for r in self.logs if r["chat_id"] == chat_id and r["owner_id"] == owner_id
                and (gen is None or r["gen"] == gen) and (not kinds or r["kind"] in kinds)]
        return sorted(rows[-limit:], key=lambda r: r["ts"])

    async def pet_chat(self, chat_id: int) -> dict:
        return _copy(self.chats.get(str(chat_id), {}))

    async def set_pet_chat(self, chat_id: int, data: dict) -> None:
        self.chats[str(chat_id)] = _copy(data)

    async def delete_chat(self, chat_id: int) -> None:
        self.pets = {k: v for k, v in self.pets.items() if v["chat_id"] != chat_id}
        self.logs = [r for r in self.logs if r["chat_id"] != chat_id]
        self.graves = [r for r in self.graves if r["chat_id"] != chat_id]
        self.chats.pop(str(chat_id), None)

    # --- saves -----------------------------------------------------------------------------------
    def dump(self) -> str:
        return json.dumps(dict(v=1, pets=self.pets, logs=self.logs, graves=self.graves, chats=self.chats,
                               next_id=self.next_id), ensure_ascii=False, separators=(",", ":"))

    def load(self, s: str) -> bool:
        try:
            d = json.loads(s)
            if d.get("v") != 1:
                return False
            self.pets, self.logs, self.graves = d["pets"], d["logs"], d["graves"]
            self.chats, self.next_id = d["chats"], d["next_id"]
            return True
        except (ValueError, KeyError, TypeError):
            return False
