import re
import asyncio
from pyrogram import Client
from pyrogram.types import Message, User
from config import cfg
from database.redis_client import rdb, chat_key


def extract_user_and_reason(message: Message) -> tuple[int | None, str]:
    """استخراج المستخدم والسبب من الرسالة"""
    user_id = None
    reason = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
        parts = message.text.split(None, 2)
        reason = parts[2] if len(parts) > 2 else ""
    elif message.entities:
        for ent in message.entities:
            if ent.type.name in ("MENTION", "TEXT_MENTION"):
                if ent.type.name == "TEXT_MENTION":
                    user_id = ent.user.id
                else:
                    username = message.text[ent.offset:ent.offset + ent.length]
                    user_id = username
                parts = message.text.split(None, 2)
                reason = parts[2] if len(parts) > 2 else ""
                break

    return user_id, reason


async def resolve_user(client: Client, user_id) -> User | None:
    try:
        if isinstance(user_id, str) and user_id.startswith("@"):
            return await client.get_users(user_id)
        return await client.get_users(int(user_id))
    except Exception:
        return None


def format_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} ثانية"
    elif seconds < 3600:
        return f"{seconds // 60} دقيقة"
    elif seconds < 86400:
        return f"{seconds // 3600} ساعة"
    else:
        return f"{seconds // 86400} يوم"


def build_mention(user: User) -> str:
    name = user.first_name or "مجهول"
    return f"[{name}](tg://user?id={user.id})"


async def safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


def get_chat_setting(chat_id: int, setting: str, default=None):
    val = rdb.get(chat_key(chat_id, "settings", setting))
    if val is None:
        return default
    if val in ("true", "1"):
        return True
    if val in ("false", "0"):
        return False
    return val


def set_chat_setting(chat_id: int, setting: str, value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    rdb.set(chat_key(chat_id, "settings", setting), str(value))


def is_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


async def run_in_thread(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)
