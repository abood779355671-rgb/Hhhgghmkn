import re
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


@Client.on_message(prefix_filter("تفعيل الاشتراك"))
async def enable_subscription(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    channel = get_chat_setting(message.chat.id, "sub_channel")
    if not channel:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} حدّد القناة أولاً:\n`{cfg.BOT_PREFIX} قناة الاشتراك @القناة`"
        )

    set_chat_setting(message.chat.id, "sub_required", True)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم تفعيل **الاشتراك الإجباري** ✓\nالقناة: {channel}"
    )


@Client.on_message(prefix_filter("تعطيل الاشتراك"))
async def disable_subscription(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "sub_required", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم تعطيل الاشتراك الإجباري ✓")


@Client.on_message(prefix_filter(r"قناة الاشتراك\s+(\S+)"))
async def set_sub_channel(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    m = re.search(r"قناة الاشتراك\s+(\S+)", message.text)
    if not m:
        return
    channel = m.group(1).strip()
    try:
        chat = await client.get_chat(channel)
        set_chat_setting(message.chat.id, "sub_channel", channel)
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم تعيين قناة الاشتراك:\n📢 **{chat.title}** ✓\n"
            f"الآن فعّل بـ `{cfg.BOT_PREFIX} تفعيل الاشتراك`"
        )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **تعذر الوصول:** `{e}`\nتأكد أن البوت مشرف في القناة.")


# ─── التحقق الفعلي من الاشتراك عند كل رسالة ─────────────────────
# group=2 — يعمل بعد أوامر البوت (0) وقبل العدّادات (5,10)
@Client.on_message(filters.group, group=2)
async def check_subscription(client: Client, message: Message):
    if not message.from_user:
        return
    if not is_chat_active(message.chat.id):
        return

    if not get_chat_setting(message.chat.id, "sub_required", False):
        return

    channel = get_chat_setting(message.chat.id, "sub_channel")
    if not channel:
        return

    user_id = message.from_user.id
    if get_user_rank(user_id, message.chat.id) <= cfg.RANK_ADMIN:
        return

    try:
        member = await client.get_chat_member(channel, user_id)
        if member.status.name in ("BANNED", "LEFT"):
            raise Exception("not subscribed")
    except Exception:
        try:
            await message.delete()
            chat = await client.get_chat(channel)
            await client.send_message(
                message.chat.id,
                f"{cfg.BOT_SYMBOL} {message.from_user.mention}، اشترك في القناة أولاً:\n"
                f"📢 [{chat.title}](https://t.me/{channel.lstrip('@')})\n"
                f"بعد الاشتراك تقدر تتكلم ✓",
                disable_web_page_preview=True,
            )
        except Exception:
            pass
