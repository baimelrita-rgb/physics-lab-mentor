"""Class rosters: the students of each class, per teacher.

Privacy: only a display name is kept (the teacher decides how much of it, e.g. first name and
an initial). No ID numbers, no contact details. The file is readable by the server user only.
A student who leaves is marked inactive, not deleted, so their past lessons stay readable.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

MAX_NAME = 40


class RosterError(Exception):
    pass


class Roster:
    def __init__(self, state_dir: Path):
        self.file = Path(state_dir) / "rosters.json"

    def _load(self) -> dict:
        return json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {}

    def _save(self, data: dict):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.file)

    @staticmethod
    def key(owner: str, class_name: str) -> str:
        return f"{owner}|{class_name}"

    def classes(self, owner: str) -> list[str]:
        return [k.split("|", 1)[1] for k in self._load() if k.split("|", 1)[0] == owner]

    def remove_class(self, owner: str, class_name: str):
        data = self._load()
        if data.pop(self.key(owner, class_name), None) is not None:
            self._save(data)

    def students(self, owner: str, class_name: str, active_only: bool = False) -> list[dict]:
        items = self._load().get(self.key(owner, class_name), [])
        return [s for s in items if s["active"] or not active_only]

    def find(self, owner: str, class_name: str, sid: str) -> dict | None:
        return next((s for s in self.students(owner, class_name) if s["id"] == sid), None)

    def add(self, owner: str, class_name: str, names: list[str]) -> list[dict]:
        if not class_name.strip():
            raise RosterError("class name required")
        data = self._load()
        items = data.setdefault(self.key(owner, class_name), [])
        existing = {s["name"] for s in items if s["active"]}
        for raw in names:
            name = " ".join(raw.split())[:MAX_NAME]
            if name and name not in existing:
                items.append({"id": "st_" + secrets.token_hex(4), "name": name, "active": True})
                existing.add(name)
        self._save(data)
        return items

    def update(self, owner: str, class_name: str, sid: str, name: str | None = None, active: bool | None = None) -> dict:
        data = self._load()
        for s in data.get(self.key(owner, class_name), []):
            if s["id"] == sid:
                if name is not None:
                    name = " ".join(name.split())[:MAX_NAME]
                    if not name:
                        raise RosterError("empty name")
                    s["name"] = name
                if active is not None:
                    s["active"] = active
                self._save(data)
                return s
        raise RosterError("student not found")
