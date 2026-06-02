import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active, get_active_chats
from helpers.utils import get_chat_setting, set_chat_setting
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


DURATION_MAP = {
    "ساعة": 3600, "ساعتين": 7200, "3ساعات": 10800, "6ساعات": 21600,
    "12ساعة": 43200, "يوم": 86400, "يومين": 172800, "اسبوع": 604800,
}


@Client.on_message(prefix_filter("تفعيل التنظيف"))
async def enable_cleanup(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    set_chat_setting(message.chat.id, "auto_cleanup", True)
    duration = int(get_chat_setting(message.chat.id, "cleanup_duration", 86400))
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم تفعيل **التنظيف التلقائي** ✓\n"
        f"سيتم حذف الرسائل بعد **{duration // 3600} ساعة**"
    )


@Client.on_message(prefix_filter("تعطيل التنظيف"))
async def disable_cleanup(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    set_chat_setting(message.chat.id, "auto_cleanup", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم تعطيل **التنظيف التلقائي** ✓")


@Client.on_message(prefix_filter(r"وقت التنظيف\s+(.+)"))
async def set_cleanup_duration(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    import re
    m = re.search(r"وقت التنظيف\s+(.+)", message.text)
    if not m:
        return

    duration_text = m.group(1).strip().replace(" ", "")
    duration_secs = DURATION_MAP.get(duration_text)

    if not duration_secs:
        available = " / ".join(DURATION_MAP.keys())
        return await message.reply(f"{cfg.BOT_SYMBOL} المتاح: {available}")

    set_chat_setting(message.chat.id, "cleanup_duration", duration_secs)
    await message.reply(f"{cfg.BOT_SYMBOL} وقت التنظيف: **{m.group(1).strip()}** ✓")


@Client.on_message(filters.group, group=10)
async def track_message_for_cleanup(client: Client, message: Message):
    """يتتبع الرسائل للتنظيف اللاحق"""
    if not message.id or not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "auto_cleanup", False):
        return
    rdb.zadd(
        chat_key(message.chat.id, "cleanup_msgs"),
        {str(message.id): int(time.time())}
    )


async def auto_cleanup_task(client: Client):
    """
    مهمة التنظيف تعمل كل ساعة — تمر على المجموعات ذات التنظيف المفعّل
    وتحذف الرسائل التي تجاوزت مدتها دفعة واحدة.
    """
    while True:
        await asyncio.sleep(3600)  # كل ساعة فقط — لا يثقّل السيرفر
        active = get_active_chats()
        for chat_id in active:
            if not get_chat_setting(chat_id, "auto_cleanup", False):
                continue

            duration = int(get_chat_setting(chat_id, "cleanup_duration", 86400))
            cutoff = int(time.time()) - duration
            msg_ids_key = chat_key(chat_id, "cleanup_msgs")

            # اجلب دفعات من 100 رسالة لتجنب الحمل الزائد
            while True:
                old_entries = rdb.zrangebyscore(msg_ids_key, "-inf", cutoff, start=0, num=100)
                if not old_entries:
                    break
                try:
                    msg_ids = [int(mid) for mid in old_entries]
                    await client.delete_messages(chat_id, msg_ids)
                except Exception:
                    pass
                rdb.zremrangebyscore(msg_ids_key, "-inf", cutoff)
                await asyncio.sleep(0.5)
