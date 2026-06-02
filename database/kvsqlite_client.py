import os
import json
import sqlite3
import threading
from config import cfg

os.makedirs(os.path.dirname(cfg.KVSQLITE_PATH) or "data", exist_ok=True)

_lock = threading.Lock()

def _conn(path):
    c = sqlite3.connect(path, check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
    c.commit()
    return c

_db = _conn(cfg.KVSQLITE_PATH)

def kv_get(key: str, default=None):
    try:
        with _lock:
            row = _db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except Exception:
            return row[0]
    except Exception:
        return default

def kv_set(key: str, value) -> bool:
    try:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        with _lock:
            _db.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)", (key, value))
            _db.commit()
        return True
    except Exception:
        return False

def kv_delete(key: str) -> bool:
    try:
        with _lock:
            _db.execute("DELETE FROM kv WHERE key=?", (key,))
            _db.commit()
        return True
    except Exception:
        return False

def kv_exists(key: str) -> bool:
    try:
        with _lock:
            row = _db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone()
        return row is not None
    except Exception:
        return False
