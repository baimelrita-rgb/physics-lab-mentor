"""Ownership model (MVP package 4): tenant -> lab -> station, in the same SQLite file as the store.

- A tenant is a school or a school network. Every teacher, lesson, session and content edit
  belongs to exactly one tenant, and nothing crosses between tenants.
- A lab is a physics lab room in a tenant. A station (one physical bench) is in one lab.
- A teacher sees the stations of their tenant; when the teacher account lists labs, only those.
- Stations that were never assigned belong to the default tenant (demo and single-school setups).

Teachers and their roles stay in teachers.json (lab/auth.py) with a `tenant` and `labs` field.
Managed with:  python3 tools/org.py ...
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time

from .content import DEFAULT_TENANT, valid_tenant

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS labs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants (id),
    name TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS station_labs (
    station_id TEXT PRIMARY KEY,
    lab_id TEXT NOT NULL REFERENCES labs (id),
    name TEXT NOT NULL DEFAULT ''
);
"""
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


class OrgError(Exception):
    pass


class Org:
    def __init__(self, db: sqlite3.Connection, lock: threading.Lock):
        self.db, self.lock = db, lock
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO tenants VALUES (?, ?, ?)", (DEFAULT_TENANT, "ברירת מחדל", time.time()))

    # ---------- writes ----------
    def add_tenant(self, tid: str, name: str):
        if not valid_tenant(tid):
            raise OrgError("tenant id: lowercase letters, digits, '-' or '_'")
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO tenants VALUES (?, ?, COALESCE((SELECT created FROM tenants WHERE id = ?), ?))",
                            (tid, name.strip() or tid, tid, time.time()))

    def add_lab(self, lab_id: str, tenant_id: str, name: str):
        if not _ID.match(lab_id):
            raise OrgError("lab id: letters, digits, '-' or '_'")
        if not self.tenant_exists(tenant_id):
            raise OrgError("unknown tenant")
        owner = self.lab_tenant(lab_id)
        if owner and owner != tenant_id:
            raise OrgError("this lab id belongs to another tenant")
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO labs VALUES (?, ?, ?, COALESCE((SELECT created FROM labs WHERE id = ?), ?))",
                            (lab_id, tenant_id, name.strip() or lab_id, lab_id, time.time()))

    def assign_station(self, station_id: str, lab_id: str, name: str = ""):
        if not _ID.match(station_id):
            raise OrgError("station id: letters, digits, '-' or '_'")
        if not self.lab_tenant(lab_id):
            raise OrgError("unknown lab")
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO station_labs VALUES (?, ?, ?)", (station_id, lab_id, name.strip()))

    # ---------- reads ----------
    def tenant_exists(self, tid: str) -> bool:
        return self.db.execute("SELECT 1 FROM tenants WHERE id = ?", (tid,)).fetchone() is not None

    def tenants(self) -> list[dict]:
        return [{"id": i, "name": n} for i, n in self.db.execute("SELECT id, name FROM tenants ORDER BY id")]

    def labs(self, tenant_id: str) -> list[dict]:
        return [{"id": i, "name": n} for i, n in
                self.db.execute("SELECT id, name FROM labs WHERE tenant_id = ? ORDER BY id", (tenant_id,))]

    def lab_tenant(self, lab_id: str) -> str | None:
        row = self.db.execute("SELECT tenant_id FROM labs WHERE id = ?", (lab_id,)).fetchone()
        return row[0] if row else None

    def station(self, station_id: str) -> dict:
        """{"lab": lab id or None, "tenant": tenant id, "name": display name}."""
        row = self.db.execute("SELECT s.lab_id, l.tenant_id, s.name FROM station_labs s JOIN labs l ON l.id = s.lab_id "
                              "WHERE s.station_id = ?", (station_id,)).fetchone()
        if not row:
            return {"lab": None, "tenant": DEFAULT_TENANT, "name": ""}
        return {"lab": row[0], "tenant": row[1], "name": row[2]}

    def visible(self, station_id: str, tenant_id: str, labs: list[str] | None) -> bool:
        st = self.station(station_id)
        if st["tenant"] != tenant_id:
            return False
        return not labs or st["lab"] in labs
