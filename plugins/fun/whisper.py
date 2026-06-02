import random
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import is_chat_active
from helpers.utils import build_mention
from database.redis_client import rdb, chat_key, user_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ─── تسجيل مستخدمي الخاص ───────────────────────────────────────────
@Client.on_message(filters.command("start") & filters.private)
async def register_private(client: Client, message: Message):
    """يحفظ المستخدم ليتمكن البوت من مراسلته في الخاص"""
    user = message.from_user
    rdb.sadd(user_key(user.id, "private_enabled"), "1")
    await message.reply(
        f"{cfg.BOT_SYMBOL} أهلاً {user.first_name}!\n"
        f"تم تفعيل استقبال الهمسات من المجموعات. 🤫"
    )


def has_private(user_id: int) -> bool:
    return rdb.exists(user_key(user_id, "private_enabled")) > 0


# ─── الهمس ────────────────────────────────────────────────────────
@Client.on_message(prefix_filter("اهمس"))
async def whisper(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص لترسل له همسة.**")

    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} الاستخدام: ردّ على شخص واكتب\n"
            f"`{cfg.BOT_PREFIX} اهمس [الرسالة]`"
        )

    whisper_text = parts[2]
    target = message.reply_to_message.from_user
    sender = message.from_user

    if not has_private(target.id):
        return await message.reply(
            f"{cfg.BOT_SYMBOL} {build_mention(target)} لم يفعّل البوت بالخاص بعد.\n"
            f"أخبره يضغط /start للبوت في الخاص أولاً."
        )

    try:
        await client.send_message(
            target.id,
            f"「 همسة سرية 🤫 」\n\n"
            f"من: {build_mention(sender)}\n\n"
            f"{whisper_text}"
        )
        await message.reply(
            f"{cfg.BOT_SYMBOL} وصلت همستك لـ {build_mention(target)} بشكل سري ✓"
        )
        await message.delete()
    except Exception:
        await message.reply(
            f"{cfg.BOT_SYMBOL} فشل الإرسال — تأكد أن الشخص شغّل البوت بالخاص."
        )


# ─── الفضفضة المجهولة ─────────────────────────────────────────────
@Client.on_message(prefix_filter("سارحني"))
async def confess(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return

    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} الاستخدام: `{cfg.BOT_PREFIX} سارحني [كلامك]`\n"
            f"رسالتك ستُرسل مجهولة الهوية للمجموعة ويُحفظ منها نسخة 🎭"
        )

    confession_text = parts[2]

    # احفظ في Redis للأمر سارح
    key = chat_key(message.chat.id, "confessions")
    rdb.lpush(key, confession_text)
    rdb.ltrim(key, 0, 99)   # احتفظ بآخر 100 فضفضة فقط

    # احذف رسالة الشخص حتى يبقى مجهولاً
    try:
        await message.delete()
    except Exception:
        pass

    await client.send_message(
        message.chat.id,
        f"「 فضفضة مجهولة الهوية 🎭 」\n\n{confession_text}"
    )


@Client.on_message(prefix_filter("سارح"))
async def confess_listen(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return

    key = chat_key(message.chat.id, "confessions")
    count = rdb.llen(key)

    if count == 0:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} لا توجد فضفضات محفوظة.\n"
            f"استخدم `{cfg.BOT_PREFIX} سارحني [كلامك]` لإضافة فضفضة."
        )

    confession = random.choice(rdb.lrange(key, 0, -1))
    await message.reply(
        f"「 فضفضة عشوائية 🎭 」\n\n{confession}\n\n"
        f"_({count} فضفضة محفوظة)_"
    )


@Client.on_message(prefix_filter("مسح الفضفضات"))
async def clear_confessions(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    from helpers.permissions import get_user_rank
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    rdb.delete(chat_key(message.chat.id, "confessions"))
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح جميع الفضفضات المحفوظة ✓")
