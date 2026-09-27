"""Origit record: schema, canonical JSON serialisation and SHA-256 hashing.

One record is attached to every commit (as a git note under refs/notes/origit).
It describes how the commit was produced: which agent session, what the agent
read, wrote, added and ran, who approved it, and what the tests said.

Canonical form (this is what gets hashed and stored):
  * JSON, UTF-8, keys sorted recursively, separators (",", ":"), no whitespace,
    ``ensure_ascii=False`` so non-ASCII (including Unicode-tag smuggling
    characters in a ``ref``) survives byte-for-byte.
  * ``read``, ``wrote`` and ``added_deps`` are treated as sets: de-duplicated
    and sorted, so trace order does not change the hash.
  * ``commands`` keeps its order (order is evidence).
  * ``record_sha256`` is the SHA-256 hex digest of the canonical bytes of the
    record *without* the ``record_sha256`` key itself.

A record is immutable evidence: change one byte and ``verify()`` fails.
Verified live on Bob IDE 2026-09-26.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

SCHEMA = "origit/record/v1"

ACTOR_HUMAN = "human"
ACTOR_BOB_IDE = "bob-ide"

READ_KINDS = ("file", "pkg", "url", "mcp")

_SET_KEYS = ("read", "wrote", "added_deps")

REQUIRED_KEYS = (
    "schema", "session", "actor", "read", "wrote", "added_deps", "commands",
    "author", "approver", "approved_at", "tests",
)


@dataclass
class Session:
    """The agent task/session that produced the commit."""

    id: str  # Bob session_id from the hook payload, e.g. "ses_01abc123"
    started_at: str | None = None  # ISO-8601 UTC
    ended_at: str | None = None


@dataclass
class Actor:
    """Who/what did the work."""

    kind: str = ACTOR_HUMAN  # "bob-ide" | "human" | future: "cursor", "codex", ...
    model: str | None = None
    mode: str | None = None  # Bob custom mode slug, e.g. "origit-build"
    config_sha256: str | None = None  # hash of the rules/mode files in effect


@dataclass
class Read:
    """One input the agent consumed."""

    kind: str  # file | pkg | url | mcp
    ref: str
    sha256: str | None = None


@dataclass
class Dep:
    """One dependency the agent added."""

    name: str
    version: str
    registry: str = "npm"
    lockfile_sha256: str | None = None


@dataclass
class Tests:
    """Result of the project's own test suite at commit time (plain git hook, no AI)."""

    run: bool = False
    passed: int = 0
    failed: int = 0


@dataclass
class Record:
    """The full Origit record. Build it, then call ``finalize()`` to hash it."""

    session: Session
    actor: Actor
    read: list[Read] = field(default_factory=list)
    wrote: list[str] = field(default_factory=list)
    added_deps: list[Dep] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    author: str = ""
    approver: str | None = None
    approved_at: str | None = None
    tests: Tests = field(default_factory=Tests)
    schema: str = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def finalize(self) -> dict[str, Any]:
        """Return the canonical dict including ``record_sha256``."""
        return finalize(self.to_dict())


def _sort_key(item: Any) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _dedupe_sorted(items: Iterable[Any]) -> list[Any]:
    seen: dict[str, Any] = {}
    for it in items:
        seen.setdefault(_sort_key(it), it)
    return [seen[k] for k in sorted(seen)]


def canonicalize(record: dict[str, Any]) -> dict[str, Any]:
    """Return a normalised copy: set-like lists de-duplicated and sorted, hash key removed."""
    out: dict[str, Any] = {}
    for k, v in record.items():
        if k == "record_sha256":
            continue
        out[k] = _dedupe_sorted(v) if (k in _SET_KEYS and isinstance(v, list)) else v
    return out


def canonical_bytes(record: dict[str, Any]) -> bytes:
    """Canonical JSON bytes of a record (without ``record_sha256``)."""
    return json.dumps(canonicalize(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_hash(record: dict[str, Any]) -> str:
    """SHA-256 hex of the canonical bytes."""
    return sha256_hex(canonical_bytes(record))


def finalize(record: dict[str, Any]) -> dict[str, Any]:
    """Validate, canonicalise and stamp ``record_sha256``. Returns a new dict."""
    validate(record)
    out = canonicalize(record)
    out["record_sha256"] = record_hash(out)
    return out


def verify(record: dict[str, Any]) -> bool:
    """True iff ``record_sha256`` matches the record content."""
    stored = record.get("record_sha256")
    return bool(stored) and stored == record_hash(record)


def dumps(record: dict[str, Any]) -> str:
    """Serialise a finalized record for storage (canonical, includes the hash)."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def loads(text: str) -> dict[str, Any]:
    return json.loads(text)


class RecordError(ValueError):
    pass


def validate(record: dict[str, Any]) -> None:
    """Minimal structural validation. Raises RecordError."""
    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        raise RecordError(f"record missing keys: {', '.join(missing)}")
    if record["schema"] != SCHEMA:
        raise RecordError(f"unknown schema {record['schema']!r}, expected {SCHEMA!r}")
    if not isinstance(record["session"], dict) or not record["session"].get("id"):
        raise RecordError("session.id is required")
    if not isinstance(record["actor"], dict) or not record["actor"].get("kind"):
        raise RecordError("actor.kind is required")
    for r in record["read"]:
        if not isinstance(r, dict) or r.get("kind") not in READ_KINDS or not r.get("ref"):
            raise RecordError(f"bad read entry: {r!r}")
    for d in record["added_deps"]:
        if not isinstance(d, dict) or not d.get("name"):
            raise RecordError(f"bad added_deps entry: {d!r}")
    for w in record["wrote"]:
        if not isinstance(w, str) or not w:
            raise RecordError(f"bad wrote entry: {w!r}")
    t = record["tests"]
    if not isinstance(t, dict) or not {"run", "passed", "failed"} <= set(t):
        raise RecordError("tests must have run/passed/failed")


def file_sha256(path: str) -> str | None:
    """SHA-256 of a file's bytes, or None if unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None
