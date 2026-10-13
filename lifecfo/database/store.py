"""SQLite store for the sandbox.

This module only reads and writes rows. All rules about when a write is
allowed live in `lifecfo.services.sandbox`, which is the only caller that
changes anything.

The audit log is append-only and hash-chained: each entry stores the hash of
the previous one, so editing or removing an entry breaks `verify_audit_chain`.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lifecfo.domain.models import FinancialState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY, strategy TEXT NOT NULL, label TEXT NOT NULL,
    plan_json TEXT NOT NULL, plan_hash TEXT NOT NULL, state_hash TEXT NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plans(id),
    plan_hash TEXT NOT NULL, state_hash TEXT NOT NULL, decision TEXT NOT NULL,
    decided_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL, ref TEXT NOT NULL, from_envelope TEXT, to_envelope TEXT,
    amount INTEGER NOT NULL, effective_on TEXT NOT NULL, plan_id TEXT,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL,
    action TEXT NOT NULL, payload TEXT NOT NULL, prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL);
"""

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    ts: str
    actor: str
    action: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


def _audit_hash(prev_hash: str, ts: str, actor: str, action: str, payload_json: str) -> str:
    material = "\n".join((prev_hash, ts, actor, action, payload_json))
    return hashlib.sha256(material.encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    @contextmanager
    def transaction(self):
        """All-or-nothing group of writes."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    # --- state -------------------------------------------------------------------------

    def load_state(self) -> FinancialState | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = 'state'").fetchone()
        return FinancialState.model_validate_json(row["value"]) if row else None

    def save_state(self, state: FinancialState) -> None:
        self.db.execute(
            "INSERT INTO meta (key, value) VALUES ('state', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (state.model_dump_json(),),
        )

    # --- plans and approvals -----------------------------------------------------------

    def insert_plan(self, row: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO plans (id, strategy, label, plan_json, plan_hash, state_hash, status, "
            "created_at) VALUES (:id, :strategy, :label, :plan_json, :plan_hash, :state_hash, "
            ":status, :created_at)", row)

    def get_plan(self, plan_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()

    def list_plans(self, status: str | None = None) -> list[sqlite3.Row]:
        if status is None:
            return self.db.execute("SELECT * FROM plans ORDER BY created_at, id").fetchall()
        return self.db.execute(
            "SELECT * FROM plans WHERE status = ? ORDER BY created_at, id", (status,)).fetchall()

    def set_plan_status(self, plan_id: str, status: str) -> None:
        self.db.execute("UPDATE plans SET status = ? WHERE id = ?", (status, plan_id))

    def insert_approval(self, row: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO approvals (id, plan_id, plan_hash, state_hash, decision, decided_at) "
            "VALUES (:id, :plan_id, :plan_hash, :state_hash, :decision, :decided_at)", row)

    def get_approval(self, approval_id: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()

    def latest_usable_approval(self) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM approvals WHERE decision = 'APPROVED' AND used_at IS NULL "
            "ORDER BY decided_at DESC, id DESC LIMIT 1").fetchone()

    def list_approvals(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM approvals ORDER BY decided_at, id").fetchall()

    def mark_approval_used(self, approval_id: str, used_at: str) -> None:
        self.db.execute("UPDATE approvals SET used_at = ? WHERE id = ?", (used_at, approval_id))

    # --- transactions ------------------------------------------------------------------

    def insert_transaction(self, row: dict[str, Any]) -> None:
        """Raises sqlite3.IntegrityError when the idempotency key was already used."""
        self.db.execute(
            "INSERT INTO transactions (idempotency_key, kind, ref, from_envelope, to_envelope, "
            "amount, effective_on, plan_id, created_at) VALUES (:idempotency_key, :kind, :ref, "
            ":from_envelope, :to_envelope, :amount, :effective_on, :plan_id, :created_at)", row)

    def list_transactions(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM transactions ORDER BY id").fetchall()

    # --- audit -------------------------------------------------------------------------

    def append_audit(self, ts: str, actor: str, action: str, payload: dict[str, Any]) -> None:
        last = self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = last["hash"] if last else GENESIS_HASH
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        self.db.execute(
            "INSERT INTO audit (ts, actor, action, payload, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, actor, action, payload_json, prev_hash,
             _audit_hash(prev_hash, ts, actor, action, payload_json)))

    def list_audit(self, limit: int | None = None) -> list[AuditEntry]:
        """Entries oldest first; with `limit`, the most recent ones."""
        rows = self.db.execute("SELECT * FROM audit ORDER BY seq").fetchall()
        if limit is not None:
            rows = rows[-limit:]
        return [AuditEntry(r["seq"], r["ts"], r["actor"], r["action"], json.loads(r["payload"]),
                           r["prev_hash"], r["hash"]) for r in rows]

    def verify_audit_chain(self) -> bool:
        prev_hash = GENESIS_HASH
        for row in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            expected = _audit_hash(prev_hash, row["ts"], row["actor"], row["action"],
                                   row["payload"])
            if row["prev_hash"] != prev_hash or row["hash"] != expected:
                return False
            prev_hash = row["hash"]
        return True

    def clear(self) -> None:
        for table in ("transactions", "approvals", "plans", "audit", "meta"):
            self.db.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names
