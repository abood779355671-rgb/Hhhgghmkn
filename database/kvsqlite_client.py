import os
import json
from kvsqlite.sync import Client
from config import cfg

os.makedirs(os.path.dirname(cfg.KVSQLITE_PATH) or "data", exist_ok=True)

kvdb = Client(cfg.KVSQLITE_PATH)


def kv_get(key: str, default=None):
    try:
        val = kvdb.get(key)
        if val is None:
            return default
        if isinstance(val, (bytes, bytearray)):
            val = val.decode()
        try:
            return json.loads(val)
        except Exception:
            return val
    except Exception:
        return default


def kv_set(key: str, value) -> bool:
    try:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        kvdb.set(key, value)
        return True
    except Exception:
        return False


def kv_delete(key: str) -> bool:
    try:
        kvdb.delete(key)
        return True
    except Exception:
        return False


def kv_exists(key: str) -> bool:
    try:
        return kvdb.get(key) is not None
    except Exception:
        return False
