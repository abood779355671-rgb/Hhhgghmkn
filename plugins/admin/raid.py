import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, ChatPermissions
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


RAID_THRESHOLD = 5
RAID_WINDOW = 10
RAID_LOCKDOWN = 60


def _raid_enabled(chat_id: int) -> bool:
    return get_chat_setting(chat_id, "raid_protection", False)


async def _lock_chat(client: Client, chat_id: int):
    try:
        await client.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
    except Exception:
        pass


async def _unlock_chat(client: Client, chat_id: int):
    try:
        await client.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
    except Exception:
        pass


# ─── تفعيل / تعطيل ────────────────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل حماية الريد"))
async def enable_raid(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "raid_protection", True)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم **تفعيل حماية Raid** ✓\n"
        f"🛡 سيتم قفل المجموعة تلقائياً إذا دخل أكثر من **{RAID_THRESHOLD}** أعضاء "
        f"خلال **{RAID_WINDOW}** ثواني."
    )


@Client.on_message(prefix_filter("تعطيل حماية الريد"))
async def disable_raid(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "raid_protection", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل حماية Raid** ✓")


# ─── handler الدخول ────────────────────────────────────────────────
@Client.on_chat_member_updated(filters.group, group=5)
async def raid_detector(client: Client, update: ChatMemberUpdated):
    if not update.new_chat_member:
        return

    old = update.old_chat_member
    new = update.new_chat_member

    is_join = (
        (old is None or old.status.name in ("LEFT", "BANNED", "RESTRICTED"))
        and new.status.name == "MEMBER"
    )
    if not is_join:
        return

    chat_id = update.chat.id
    if not is_chat_active(chat_id):
        return
    if not _raid_enabled(chat_id):
        return

    lock_key = chat_key(chat_id, "raid_locked")
    if rdb.get(lock_key):
        return

    counter_key = chat_key(chat_id, "raid_counter")
    count = rdb.incr(counter_key)
    if count == 1:
        rdb.expire(counter_key, RAID_WINDOW)

    if count >= RAID_THRESHOLD:
        rdb.set(lock_key, "1", ex=RAID_LOCKDOWN + 10)
        rdb.delete(counter_key)

        await _lock_chat(client, chat_id)
        await client.send_message(
            chat_id,
            f"🚨 **تحذير Raid!**\n\n"
            f"تم اكتشاف **{count}** أعضاء دخلوا خلال {RAID_WINDOW} ثواني.\n"
            f"تم **قفل المجموعة** تلقائياً 🔒\n"
            f"سيتم الفتح خلال **{RAID_LOCKDOWN}** ثانية.",
        )

        await asyncio.sleep(RAID_LOCKDOWN)

        rdb.delete(lock_key)
        await _unlock_chat(client, chat_id)
        await client.send_message(
            chat_id,
            f"{cfg.BOT_SYMBOL} انتهى وقت القفل — تم **فتح المجموعة** 🔓",
        )
