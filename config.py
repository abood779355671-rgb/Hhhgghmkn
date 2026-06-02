import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
    API_ID: int = int(os.environ.get("API_ID", 0))
    API_HASH: str = os.environ.get("API_HASH", "")

    OWNER_ID: int = int(os.environ.get("OWNER_ID", 0))
    DEV_IDS: list[int] = [
        int(x.strip())
        for x in os.environ.get("DEV_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.environ.get("REDIS_PORT", 6379))
    REDIS_PASSWORD: str = os.environ.get("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.environ.get("REDIS_DB", 0))

    BOT_NAME: str = os.environ.get("BOT_NAME", "رعد")
    BOT_PREFIX: str = os.environ.get("BOT_PREFIX", "رعد")
    BOT_SYMBOL: str = os.environ.get("BOT_SYMBOL", "༄")

    BOT_CHANNEL: str = os.environ.get("BOT_CHANNEL", "")

    KVSQLITE_PATH: str = os.environ.get("KVSQLITE_PATH", "data/bot.db")
    YOUTUBE_DB_PATH: str = "data/ytdb.sqlite"
    SOUND_DB_PATH: str = "data/sounddb.sqlite"

    BOT_ID: str = ""

    RANK_OWNER = 1
    RANK_DEV = 2
    RANK_DEV2 = 3
    RANK_MOD = 4
    RANK_ADMIN = 5
    RANK_MEMBER = 6

    RANK_NAMES = {
        1: "👑 المالك",
        2: "💻 المطور",
        3: "🔰 نائب المطور",
        4: "🛡 المدير",
        5: "⚡ الإداري",
        6: "👤 عضو",
    }

    LOCK_TYPES = [
        "links", "photos", "videos", "documents", "stickers",
        "voices", "hashtags", "forwards", "duplicates", "curses",
        "mentions", "bots", "channels", "joins",
        "persian", "irani", "klish", "adult", "online",
    ]

    LOCK_NAMES = {
        "links":      "الروابط",
        "photos":     "الصور",
        "videos":     "الفيديو",
        "documents":  "الملفات",
        "stickers":   "الملصقات",
        "voices":     "الفويسات",
        "hashtags":   "الهشتاق",
        "forwards":   "التوجيه",
        "duplicates": "التكرار",
        "curses":     "السب",
        "mentions":   "المنشن",
        "bots":       "البوتات",
        "channels":   "القنوات",
        "joins":      "الدخول",
        "persian":    "الفارسية",
        "irani":      "الإيراني",
        "klish":      "الكلايش",
        "adult":      "الاباحي",
        "online":     "الانلاين",
    }


cfg = Config()

import os as _os
_os.makedirs("data", exist_ok=True)
_os.makedirs("downloads", exist_ok=True)

from sqlitedict import SqliteDict
ytdb = SqliteDict(cfg.YOUTUBE_DB_PATH, autocommit=True)
sounddb = SqliteDict(cfg.SOUND_DB_PATH, autocommit=True)
