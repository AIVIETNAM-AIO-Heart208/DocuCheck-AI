"""Atomic job metadata and revisions; never infer success from an old JSON file."""

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
import threading
import time
import uuid


TERMINAL = {"succeeded", "partial", "failed", "cancelled"}


class Conflict(ValueError):
    pass


class Capacity(Conflict):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, "
                       "token TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, body TEXT NOT NULL, "
                       "UNIQUE(owner,token))")

    @contextmanager
    def connection(self):
        with self.lock, sqlite3.connect(self.root / "jobs.sqlite3", timeout=10) as db:
            db.row_factory = sqlite3.Row
            yield db

    def directory(self, key: str) -> Path:
        if str(uuid.UUID(key)) != key:
            raise ValueError("Invalid job ID")
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError("Unsafe job path")
        return path

    def find_token(self, owner: str, token: str):
        with self.connection() as db:
            row = db.execute("SELECT body FROM jobs WHERE owner=? AND token=?", (owner, token)).fetchone()
            return json.loads(row[0]) if row else None

    def get(self, key: str, owner: str | None = None):
        with self.connection() as db:
            row = db.execute("SELECT owner, body FROM jobs WHERE id=?", (key,)).fetchone()
            if row is None or (owner is not None and row["owner"] != owner):
                raise KeyError(key)
            return json.loads(row["body"])

    @staticmethod
    def _write(db, body):
        body["updated"] = time.time()
        db.execute("UPDATE jobs SET state=?, body=? WHERE id=?",
                   (body["state"], json.dumps(body, ensure_ascii=False, allow_nan=False), body["id"]))

    def create(self, owner, token, key, image, settings):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM jobs WHERE owner=? AND token=?", (owner, token)).fetchone()
            if existing:
                return json.loads(existing[0]), False
            rows = db.execute("SELECT owner,state FROM jobs WHERE state NOT IN ('succeeded','partial','failed','cancelled')").fetchall()
            if (len(rows) >= settings.queue_size + 1
                    or sum(r["state"] == "queued" for r in rows) >= settings.queue_size
                    or sum(r["owner"] == owner for r in rows) >= settings.per_session):
                raise Capacity("Hàng đợi đầy hoặc phiên của bạn đã có tác vụ đang chạy.")
            now = time.time()
            body = {"id":key, "state":"queued", "stage":"queued", "created":now,
                    "updated":now, "image":image, "result":None, "fields":{}, "error":None,
                    "review":None, "revision":0, "mode":settings.extraction_mode,
                    "gpu_policy":settings.gpu_policy, "timing":{}}
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?)",
                       (key, owner, token, "queued", now, json.dumps(body, ensure_ascii=False)))
            return body, True

    def update(self, key, **changes):
        with self.connection() as db:
            body = self.get(key)
            body.update(changes)
            self._write(db, body)
            return body

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            body = json.loads(row[0])
            body.update(state="loading", stage="loading", started=time.time())
            self._write(db, body)
            return body

    def cancel(self, key, owner):
        with self.connection() as db:
            body = self.get(key, owner)
            if body["state"] not in TERMINAL:
                body["state"] = "cancelled" if body["state"] == "queued" else "cancel_requested"
                body["stage"] = body["state"]
                self._write(db, body)
            return body

    def interrupted(self, message="Ứng dụng đã khởi động lại; hãy gửi lại ảnh."):
        with self.connection() as db:
            rows = db.execute("SELECT body FROM jobs WHERE state NOT IN ('succeeded','partial','failed','cancelled')").fetchall()
            for row in rows:
                body = json.loads(row[0])
                body.update(state="failed", stage="failed", error={"code":"interrupted", "message":message})
                self._write(db, body)

    def review(self, key, owner, values, revision, confirmed):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            body = self.get(key, owner)
            if body["state"] not in {"succeeded", "partial"}:
                raise Conflict("Chưa có kết quả để sửa.")
            if revision != body["revision"]:
                raise Conflict("Kết quả đã được sửa ở tab khác. Hãy tải lại.")
            previous = body["review"]
            # Confirmation of an existing draft is allowed; a changed confirmed
            # value must first be saved as a draft before a separate confirmation.
            changed_confirmed = previous and previous["confirmed"] and previous["values"] != values
            body["revision"] += 1
            body["review"] = {"values":values, "confirmed":bool(confirmed and not changed_confirmed),
                              "updated":time.time(), "revision":body["revision"]}
            db.execute("CREATE TABLE IF NOT EXISTS reviews (job_id TEXT, revision INTEGER, body TEXT, PRIMARY KEY(job_id,revision))")
            db.execute("INSERT INTO reviews VALUES(?,?,?)", (key, body["revision"], json.dumps(body["review"], ensure_ascii=False)))
            self._write(db, body)
            return body

    def queue_position(self, key):
        with self.connection() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created")]
            return ids.index(key) + 1 if key in ids else 0

    def prune(self, ttl):
        """Only expired terminal job UUID directories under this storage root."""
        with self.connection() as db:
            rows = db.execute("SELECT id FROM jobs WHERE state IN ('succeeded','partial','failed','cancelled') AND created<?",
                              (time.time()-ttl,)).fetchall()
            for row in rows:
                path = self.directory(row[0])
                if path.is_dir():
                    shutil.rmtree(path)
                db.execute("DELETE FROM jobs WHERE id=?", (row[0],))
                if db.execute("SELECT name FROM sqlite_master WHERE name='reviews'").fetchone():
                    db.execute("DELETE FROM reviews WHERE job_id=?", (row[0],))
            known = {r[0] for r in db.execute("SELECT id FROM jobs")}
            # Uploads interrupted before INSERT have no row. Only expire UUID
            # directories owned by this storage root; never follow symlinks.
            for path in self.root.iterdir():
                if path.name in known or path.is_symlink() or not path.is_dir():
                    continue
                try:
                    checked = self.directory(path.name)
                except ValueError:
                    continue
                if checked.stat().st_mtime < time.time()-ttl:
                    shutil.rmtree(checked)

    def disk_usage(self):
        return sum(p.stat().st_size for p in self.root.rglob("*") if not p.is_symlink() and p.is_file())
