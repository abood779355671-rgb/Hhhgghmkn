import os
import json
from sqlitedict import SqliteDict
from config import cfg

os.makedirs(os.path.dirname(cfg.KVSQLITE_PATH) or "data", exist_ok=True)

kvdb = SqliteDict(cfg.KVSQLITE_PATH, autocommit=True)


def kv_get(key: str, default=None):
    try:
        val = kvdb.get(key)
        if val is None:
            return default
        return val
    except Exception:
        return default


def kv_set(key: str, value) -> bool:
    try:
        kvdb[key] = value
        return True
    except Exception:
        return False


def kv_delete(key: str) -> bool:
    try:
        del kvdb[key]
        return True
    except Exception:
        return False


def kv_exists(key: str) -> bool:
    try:
        return key in kvdb
    except Exception:
        return False
