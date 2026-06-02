import redis
from config import cfg


_pool = redis.ConnectionPool(
    host=cfg.REDIS_HOST,
    port=cfg.REDIS_PORT,
    password=cfg.REDIS_PASSWORD or None,
    db=cfg.REDIS_DB,
    decode_responses=True,
    max_connections=50,
)

rdb: redis.Redis = redis.Redis(connection_pool=_pool)


def key(*parts) -> str:
    """بناء مفتاح Redis مع معرّف البوت لتجنب التعارض"""
    return f"raad:{cfg.BOT_ID}:" + ":".join(str(p) for p in parts)


def chat_key(chat_id: int, *parts) -> str:
    return key("chat", chat_id, *parts)


def user_key(user_id: int, *parts) -> str:
    return key("user", user_id, *parts)


def global_key(*parts) -> str:
    return key("global", *parts)


def ping() -> bool:
    try:
        return rdb.ping()
    except Exception:
        return False
