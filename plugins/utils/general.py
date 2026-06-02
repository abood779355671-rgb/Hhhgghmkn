import re
import json
import random
import asyncio
from datetime import datetime
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active, activate_chat, deactivate_chat
from helpers.utils import build_mention, safe_delete, get_chat_setting, set_chat_setting
from database.redis_client import rdb, chat_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ─── تفعيل / تعطيل البوت ─────────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل"))
async def activate(client: Client, message: Message):
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    activate_chat(message.chat.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم **تفعيل {cfg.BOT_NAME}** في هذه المجموعة ✓\n"
        f"استخدم `{cfg.BOT_PREFIX} الاوامر` لقائمة الأوامر الكاملة."
    )


@Client.on_message(prefix_filter("تعطيل"))
async def deactivate(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    deactivate_chat(message.chat.id)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل {cfg.BOT_NAME}**.")


# ─── الوقت والتاريخ ───────────────────────────────────────────────
@Client.on_message(prefix_filter("الساعة|الوقت"))
async def current_time(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    tz = pytz.timezone("Asia/Riyadh")
    now = datetime.now(tz)
    await message.reply(
        f"{cfg.BOT_SYMBOL} **الوقت الحالي (الرياض):**\n"
        f"🕐 `{now.strftime('%I:%M:%S %p')}`"
    )


@Client.on_message(prefix_filter("التاريخ"))
async def current_date(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    from hijri_converter import convert
    today = datetime.now()
    hijri = convert.Gregorian(today.year, today.month, today.day).to_hijri()
    await message.reply(
        f"{cfg.BOT_SYMBOL} **التاريخ الحالي:**\n"
        f"📅 ميلادي: `{today.strftime('%Y-%m-%d')}`\n"
        f"🌙 هجري: `{hijri.year}/{hijri.month:02}/{hijri.day:02}`"
    )


# ─── معلومات المجموعة ─────────────────────────────────────────────
@Client.on_message(prefix_filter("المالك"))
async def chat_owner(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    try:
        async for member in client.get_chat_members(message.chat.id, filter="owners"):
            return await message.reply(
                f"{cfg.BOT_SYMBOL} **مالك المجموعة:**\n👑 {build_mention(member.user)}"
            )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **تعذر الحصول على المعلومات:** `{e}`")


@Client.on_message(prefix_filter("الرابط|انشاء رابط"))
async def get_invite_link(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    try:
        link = await client.export_chat_invite_link(message.chat.id)
        await message.reply(f"{cfg.BOT_SYMBOL} **رابط الدعوة:**\n{link}")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل:** `{e}`")


# ─── منشن الكل ────────────────────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل المنشن"))
async def enable_mention_all(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "mention_all_enabled", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل منشن الكل** ✓")


@Client.on_message(prefix_filter("تعطيل المنشن"))
async def disable_mention_all(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "mention_all_enabled", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل منشن الكل** ✓")


@Client.on_message(
    filters.group &
    filters.regex(r"^(@all|منشن الكل)$", flags=8)
)
async def mention_all(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.** يحتاج إداري أو أعلى.")
    if not get_chat_setting(message.chat.id, "mention_all_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} منشن الكل **معطّل** في هذه المجموعة.")

    member_ids = rdb.smembers(chat_key(message.chat.id, "members"))
    if not member_ids:
        async for member in client.get_chat_members(message.chat.id):
            if not member.user.is_bot and not member.user.is_deleted:
                member_ids.add(str(member.user.id))

    batch: list[str] = []
    count = 0
    for uid_bytes in member_ids:
        uid = int(uid_bytes) if isinstance(uid_bytes, (bytes, str)) else uid_bytes
        try:
            u = await client.get_users(uid)
            if not u.is_bot and not u.is_deleted:
                batch.append(f"[‌]({f'tg://user?id={uid}'})")
                count += 1
        except Exception:
            batch.append(f"[‌](tg://user?id={uid})")
            count += 1

        if len(batch) >= 30:
            await message.reply(" ".join(batch))
            batch = []
            await asyncio.sleep(1.5)

    if batch:
        await message.reply(" ".join(batch))

    await message.reply(f"{cfg.BOT_SYMBOL} تم منشنة **{count}** عضو ✓")


# ─── ترجمة بالرد (بدون prefix) ────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل الترجمة"))
async def enable_translate(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "translate_enabled", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل الترجمة بالرد** ✓")


@Client.on_message(prefix_filter("تعطيل الترجمة"))
async def disable_translate(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "translate_enabled", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل الترجمة بالرد** ✓")


@Client.on_message(
    filters.group &
    filters.regex(r"^(ترجمه|ترجم)$", flags=8),
    group=6,
)
async def translate_reply(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "translate_enabled", True):
        return
    if not message.reply_to_message:
        return

    reply = message.reply_to_message
    text = (
        reply.text or
        reply.caption or
        (reply.poll.question if reply.poll else None)
    )
    if not text:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا يوجد نص في الرسالة المردود عليها.**")

    try:
        from helpers.utils import run_in_thread
        from deep_translator import GoogleTranslator

        def _do():
            return GoogleTranslator(source="auto", target="ar").translate(text)

        translated = await run_in_thread(_do)
        await message.reply(
            f"{cfg.BOT_SYMBOL} **الترجمة:**\n{translated}",
            reply_to_message_id=reply.id,
        )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الترجمة:** `{e}`")


# ─── ترجمة بالنص القديمة ─────────────────────────────────────────
@Client.on_message(prefix_filter(r"ترجمة\s+(.+)"))
async def translate_text(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(r"ترجمة\s+(.+)", message.text, re.DOTALL)
    if not m:
        return
    text_to_translate = m.group(1).strip()
    if message.reply_to_message and message.reply_to_message.text:
        text_to_translate = message.reply_to_message.text

    try:
        from helpers.utils import run_in_thread
        from deep_translator import GoogleTranslator

        def _do():
            return GoogleTranslator(source="auto", target="ar").translate(text_to_translate)

        translated = await run_in_thread(_do)
        await message.reply(f"{cfg.BOT_SYMBOL} **الترجمة:**\n{translated}")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الترجمة:** `{e}`")


@Client.on_message(filters.command(["ar", "en"]) & filters.group)
async def quick_translate(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    target_lang = "ar" if message.command[0] == "ar" else "en"
    text = None
    if message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text
    elif len(message.command) > 1:
        text = " ".join(message.command[1:])
    if not text:
        return await message.reply(f"{cfg.BOT_SYMBOL} ردّ على رسالة أو اكتب النص بعد الأمر.")
    try:
        from helpers.utils import run_in_thread
        from deep_translator import GoogleTranslator

        def _do():
            return GoogleTranslator(source="auto", target=target_lang).translate(text)

        translated = await run_in_thread(_do)
        await message.reply(f"{cfg.BOT_SYMBOL} **الترجمة:**\n{translated}")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الترجمة:** `{e}`")


# ─── قائمة التثبيت ────────────────────────────────────────────────
def _get_pin_list(chat_id: int) -> list[dict]:
    raw = rdb.get(chat_key(chat_id, "pin_list"))
    return json.loads(raw) if raw else []


def _save_pin_list(chat_id: int, data: list[dict]):
    rdb.set(chat_key(chat_id, "pin_list"), json.dumps(data, ensure_ascii=False))


@Client.on_message(prefix_filter("تثبيت"))
async def pin_message(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    if not message.reply_to_message:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على الرسالة التي تريد تثبيتها.**")
    try:
        target = message.reply_to_message
        await target.pin()

        pin_list = _get_pin_list(message.chat.id)
        chat_username = message.chat.username
        if chat_username:
            link = f"https://t.me/{chat_username}/{target.id}"
        else:
            cid_str = str(message.chat.id).replace("-100", "")
            link = f"https://t.me/c/{cid_str}/{target.id}"

        preview = (target.text or target.caption or "رسالة وسائط")[:50]
        pin_list.append({"msg_id": target.id, "link": link, "preview": preview})
        _save_pin_list(message.chat.id, pin_list)

        await message.reply(f"{cfg.BOT_SYMBOL} تم **تثبيت الرسالة** وإضافتها لقائمة التثبيت ✓")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل التثبيت:** `{e}`")


@Client.on_message(prefix_filter("الغاء التثبيت"))
async def unpin_message(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    try:
        await client.unpin_chat_message(message.chat.id)
        await message.reply(f"{cfg.BOT_SYMBOL} تم **إلغاء التثبيت** ✓")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل:** `{e}`")


@Client.on_message(prefix_filter("قائمة التثبيت"))
async def show_pin_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    pin_list = _get_pin_list(message.chat.id)
    if not pin_list:
        return await message.reply(f"{cfg.BOT_SYMBOL} **قائمة التثبيت فارغة.**")

    lines = [f"{cfg.BOT_SYMBOL} **الرسائل المثبتة سابقاً ({len(pin_list)}):**\n"]
    for i, item in enumerate(pin_list, 1):
        preview = item.get("preview", "رسالة")
        link = item.get("link", "#")
        lines.append(f"{i}. [{preview}...]({link})")
    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("مسح قائمة التثبيت"))
async def clear_pin_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    _save_pin_list(message.chat.id, [])
    await message.reply(f"{cfg.BOT_SYMBOL} تم **مسح قائمة التثبيت** ✓")


# ─── حذف رسالة ────────────────────────────────────────────────────
@Client.on_message(prefix_filter("مسح"))
async def delete_message(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    if not message.reply_to_message:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على الرسالة التي تريد حذفها.**")
    try:
        await message.reply_to_message.delete()
        await safe_delete(message)
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الحذف:** `{e}`")


# ─── البوتات ──────────────────────────────────────────────────────
@Client.on_message(prefix_filter("طرد البوتات"))
async def kick_bots(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    me = await client.get_me()
    kicked = 0
    async for member in client.get_chat_members(message.chat.id):
        if member.user.is_bot and member.user.id != me.id:
            try:
                await client.ban_chat_member(message.chat.id, member.user.id)
                await client.unban_chat_member(message.chat.id, member.user.id)
                kicked += 1
            except Exception:
                pass

    await message.reply(f"{cfg.BOT_SYMBOL} تم طرد **{kicked}** بوت ✓")


@Client.on_message(prefix_filter("كشف البوتات"))
async def detect_bots(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    bots = []
    async for member in client.get_chat_members(message.chat.id):
        if member.user.is_bot:
            bots.append(f"• [{member.user.first_name}](tg://user?id={member.user.id})")

    if not bots:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا يوجد بوتات في المجموعة.**")
    await message.reply(
        f"{cfg.BOT_SYMBOL} **البوتات في المجموعة ({len(bots)}):**\n" + "\n".join(bots)
    )


# ─── البايو العشوائي ──────────────────────────────────────────────
RANDOM_BIOS = [
    "مجموعة مميزة بأعضاء رائعين ☆",
    "هنا يجتمع الأحبة 🤍",
    "مكان الضحكة والنقاش الهادف 💬",
    "مجموعتنا — قوانيننا 📌",
    "لا نقبل إلا المحترمين ✅",
    "الكل هنا أسرة واحدة 💙",
    "أجمل المجموعات وأحلى الأعضاء ⭐",
    "منطقة خالية من السلبية 🌱",
]


@Client.on_message(prefix_filter("بايو عشوائي"))
async def random_bio(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    bio = random.choice(RANDOM_BIOS)
    try:
        await client.set_chat_description(message.chat.id, bio)
        await message.reply(f"{cfg.BOT_SYMBOL} تم تغيير وصف المجموعة إلى:\n**{bio}**")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل تغيير الوصف:** `{e}`")


# ─── تتبع من أضاف / طرد البوت ────────────────────────────────────
@Client.on_chat_member_updated()
async def track_bot_membership(client: Client, update):
    try:
        me = await client.get_me()
        if not update.new_chat_member or update.new_chat_member.user.id != me.id:
            return
        chat_id = update.chat.id
        user = update.from_user
        if not user:
            return
        if update.new_chat_member.status.name == "MEMBER":
            rdb.set(global_key(f"added_by:{chat_id}"), str(user.id))
            rdb.set(global_key(f"added_by_name:{chat_id}"), user.first_name or "مجهول")
        elif update.new_chat_member.status.name in ("LEFT", "BANNED"):
            rdb.set(global_key(f"kicked_by:{chat_id}"), str(user.id))
            rdb.set(global_key(f"kicked_by_name:{chat_id}"), user.first_name or "مجهول")
    except Exception:
        pass


@Client.on_message(prefix_filter("مين ضافني"))
async def who_added_me(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    uid = rdb.get(global_key(f"added_by:{chat_id}"))
    name = rdb.get(global_key(f"added_by_name:{chat_id}")) or "مجهول"

    if not uid:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندي معلومات عن من أضافني.**")

    await message.reply(
        f"{cfg.BOT_SYMBOL} **من أضاف البوت للمجموعة:**\n"
        f"👤 [{name}](tg://user?id={uid}) — `{uid}`"
    )


@Client.on_message(prefix_filter("مين طردني"))
async def who_kicked_me(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    uid = rdb.get(global_key(f"kicked_by:{chat_id}"))
    name = rdb.get(global_key(f"kicked_by_name:{chat_id}")) or "مجهول"

    if not uid:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لم يُطرد البوت من هذه المجموعة.**")

    await message.reply(
        f"{cfg.BOT_SYMBOL} **من طرد البوت:**\n"
        f"👤 [{name}](tg://user?id={uid}) — `{uid}`"
    )


# ─── المحظورين والمقيدين ──────────────────────────────────────────
@Client.on_message(prefix_filter("المقيدين"))
async def list_restricted(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    restricted = rdb.smembers(chat_key(message.chat.id, "restricted"))
    if not restricted:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا يوجد مقيدون.**")
    lines = [f"{cfg.BOT_SYMBOL} **قائمة المقيدين:**\n"]
    for uid in restricted:
        try:
            u = await client.get_users(int(uid))
            lines.append(f"• [{u.first_name}](tg://user?id={uid}) — `{uid}`")
        except Exception:
            lines.append(f"• `{uid}`")
    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("مسح المحظورين"))
async def clear_banned(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    rdb.delete(chat_key(message.chat.id, "banned"))
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح سجل المحظورين المحلي ✓")


# ─── الإعدادات ────────────────────────────────────────────────────
@Client.on_message(prefix_filter("الاعدادات"))
async def show_settings(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id

    from plugins.utils.welcome import get_welcome_data
    welcome_data = get_welcome_data(chat_id)
    from plugins.admin.locks import is_locked
    lock_lines = []
    for lt, name in cfg.LOCK_NAMES.items():
        icon = "🔒" if is_locked(chat_id, lt) else "🔓"
        lock_lines.append(f"{icon} {name}")

    captcha_on = get_chat_setting(chat_id, "captcha_enabled", False)
    cleanup_on = get_chat_setting(chat_id, "auto_cleanup", False)
    sub_on = get_chat_setting(chat_id, "sub_required", False)
    raid_on = get_chat_setting(chat_id, "raid_protection", False)
    translate_on = get_chat_setting(chat_id, "translate_enabled", True)
    smart_on = get_chat_setting(chat_id, "smart_replies", True)
    mention_on = get_chat_setting(chat_id, "mention_all_enabled", True)

    lines = [
        f"「 إعدادات {message.chat.title} 」\n",
        f"**الترحيب:** {'✅' if welcome_data.get('enabled') else '❌'}",
        f"**التحقق عند الدخول:** {'✅' if captcha_on else '❌'}",
        f"**الاشتراك الإجباري:** {'✅' if sub_on else '❌'}",
        f"**التنظيف التلقائي:** {'✅' if cleanup_on else '❌'}",
        f"**حماية Raid:** {'✅' if raid_on else '❌'}",
        f"**الترجمة بالرد:** {'✅' if translate_on else '❌'}",
        f"**الردود الذكية:** {'✅' if smart_on else '❌'}",
        f"**منشن الكل:** {'✅' if mention_on else '❌'}",
        f"\n**الأقفال:**",
    ] + lock_lines

    await message.reply("\n".join(lines))


# ─── قائمة الأوامر ────────────────────────────────────────────────
COMMANDS_PAGES = {
    "admin": (
        "🛡 **أوامر الإدارة**",
        [
            ("رفع مشرف", "رفع عضو لمشرف"),
            ("تنزيل مشرف", "تنزيل مشرف"),
            ("رفع مطور", "رفع لنائب مطور"),
            ("تنزيل مطور", "تنزيل رتبة المطور"),
            ("كتم", "كتم عضو (رد أو @يوزر)"),
            ("الغاء الكتم", "رفع الكتم"),
            ("كتم عام", "كتم عام في كل المجموعات"),
            ("الغاء الكتم العام", "رفع الكتم العام"),
            ("حظر", "حظر محلي"),
            ("رفع الحظر", "رفع الحظر"),
            ("حظر عام", "حظر عام (gban)"),
            ("الغاء الحظر العام", "رفع الحظر العام"),
            ("طرد", "طرد من المجموعة"),
            ("تقييد", "منع الإرسال"),
            ("الغاء تقييد", "رفع التقييد"),
            ("المكتومين", "قائمة المكتومين"),
            ("المحظورين", "قائمة المحظورين"),
            ("المقيدين", "قائمة المقيدين"),
        ]
    ),
    "locks": (
        "🔒 **أوامر الأقفال**",
        [
            ("قفل الروابط / فتح الروابط", "قفل/فتح الروابط"),
            ("قفل الصور / فتح الصور", "قفل/فتح الصور"),
            ("قفل الفيديو / فتح الفيديو", "قفل/فتح الفيديو"),
            ("قفل الملفات / فتح الملفات", "قفل/فتح الملفات"),
            ("قفل الملصقات / فتح الملصقات", "قفل/فتح الملصقات"),
            ("قفل الفويسات / فتح الفويسات", "قفل/فتح الصوتيات"),
            ("قفل الهشتاق / فتح الهشتاق", "قفل/فتح الهاشتاق"),
            ("قفل التوجيه / فتح التوجيه", "قفل/فتح الفورورد"),
            ("قفل التكرار / فتح التكرار", "منع تكرار الرسالة من نفس الشخص"),
            ("قفل السب / فتح السب", "قفل/فتح الكلام السيئ"),
            ("قفل المنشن / فتح المنشن", "قفل/فتح المنشن"),
            ("قفل البوتات / فتح البوتات", "قفل/فتح رسائل البوتات"),
            ("قفل الفارسية / فتح الفارسية", "حذف الرسائل التي تحتوي حروف فارسية"),
            ("قفل الإيراني / فتح الإيراني", "نفس قفل الفارسية"),
            ("قفل الكلايش / فتح الكلايش", "حذف الرسائل الطويلة +200 حرف"),
            ("قفل الاباحي / فتح الاباحي", "حذف الكلام الإباحي"),
            ("قفل الانلاين / فتح الانلاين", "حذف رسائل الأعضاء العاديين"),
            ("قفل الكل / فتح الكل", "قفل/فتح كل الأنواع"),
            ("قفل الدردشة / فتح الدردشة", "قفل الكلام للكل"),
            ("الاقفال", "عرض حالة الأقفال"),
        ]
    ),
    "welcome": (
        "👋 **أوامر الترحيب والقوانين**",
        [
            ("تفعيل الترحيب", "تفعيل رسالة الترحيب"),
            ("تعطيل الترحيب", "تعطيل الترحيب"),
            ("رسالة الترحيب [نص]", "تعيين نص الترحيب"),
            ("ترحيب بالصورة", "تفعيل/إيقاف صورة العضو"),
            ("القوانين [نص]", "حفظ أو عرض القوانين"),
            ("تفعيل التحقق", "كابتشا عند الدخول"),
            ("تعطيل التحقق", "إيقاف الكابتشا"),
            ("تفعيل الاشتراك", "اشتراك إجباري"),
            ("قناة الاشتراك @قناة", "تعيين القناة"),
            ("تعطيل الاشتراك", "إلغاء الاشتراك الإجباري"),
        ]
    ),
    "filters": (
        "🤖 **الردود والأوامر المخصصة**",
        [
            ("اضف رد [كلمة]", "ردّ على رسالة لإضافة رد تلقائي"),
            ("اضف رد عام [كلمة]", "رد عام لكل المجموعات"),
            ("مسح رد [كلمة]", "حذف رد تلقائي"),
            ("الردود", "عرض كل الردود التلقائية"),
            ("اضف امر [اسم]", "إضافة أمر مخصص"),
            ("مسح امر [اسم]", "حذف أمر مخصص"),
            ("الاوامر المضافة", "عرض الأوامر المضافة"),
            ("اضف ميزة", "إضافة ميزة مخصصة بخطوات"),
            ("حذف ميزة [كلمة]", "حذف ميزة مضافة"),
            ("قائمة الميزات", "عرض كل الميزات"),
        ]
    ),
    "economy": (
        "💰 **نظام الاقتصاد**",
        [
            ("انشاء حساب بنكي", "فتح حساب"),
            ("فلوسي", "عرض الرصيد"),
            ("راتب", "راتب يومي"),
            ("بخشيش", "مكافأة عشوائية كل ساعة"),
            ("كنز", "بحث عن كنز كل ساعتين"),
            ("عجلة [مبلغ]", "رهان العجلة"),
            ("استثمار فلوسي [مبلغ]", "استثمار"),
            ("تحويل [مبلغ]", "تحويل فلوس لشخص"),
            ("زرف", "سرقة فلوس (ردّ على شخص)"),
            ("توب الفلوس", "أثرياء البوت"),
            ("توب الحراميه", "أكثر السارقين"),
        ]
    ),
    "games": (
        "🎮 **الألعاب الجماعية**",
        [
            ("تخمين", "تخمين كلمة عربية"),
            ("عواصم", "تخمين عواصم الدول"),
            ("أعلام", "تخمين الأعلام"),
            ("إيموجي", "تخمين الإيموجي"),
            ("أنمي", "تخمين اسم الأنمي"),
            ("سيارات", "تخمين السيارة"),
            ("كرة قدم", "تخمين لاعب"),
            ("أكمل الجملة", "إكمال الجملة الناقصة"),
            ("حساب", "مسألة حسابية"),
            ("نرد", "رمي النرد (ردّ للمنافسة)"),
            ("روليت / تدوير", "لعبة الروليت الجماعية"),
            ("حجر ورقة مقص [حجر/ورقة/مقص]", "اللعبة الكلاسيكية"),
            ("الأحكام", "حكم عشوائي (ردّ على شخص)"),
            ("الديمون", "لعبة الديمون"),
            ("توب الألعاب", "متصدرو الألعاب"),
            ("انهاء اللعبة", "إنهاء اللعبة الحالية"),
        ]
    ),
    "lists": (
        "🎉 **القوائم**",
        [
            ("رفع [اسم القائمة]", "إضافة عضو للقائمة"),
            ("تنزيل [اسم القائمة]", "إزالة عضو من القائمة"),
            ("قائمة [اسم]", "عرض القائمة"),
            ("مسح قائمة [اسم]", "مسح القائمة"),
            ("القوائم", "عرض كل القوائم المتاحة"),
        ]
    ),
    "fun": (
        "🎭 **الهمس والفضفضة**",
        [
            ("اهمس [رسالة]", "إرسال همسة سرية (ردّ على شخص)"),
            ("سارحني [كلامك]", "فضفضة مجهولة الهوية"),
            ("سارح", "عرض فضفضة عشوائية"),
            ("مسح الفضفضات", "مسح الفضفضات المحفوظة"),
        ]
    ),
    "utils": (
        "🛠 **أوامر عامة**",
        [
            ("الساعة / الوقت", "الوقت الحالي"),
            ("التاريخ", "التاريخ هجري وميلادي"),
            ("المالك", "مالك المجموعة"),
            ("الرابط / انشاء رابط", "رابط الدعوة"),
            ("@all أو منشن الكل", "منشنة الكل (إداري فأعلى)"),
            ("تفعيل المنشن / تعطيل المنشن", "تحكم بمنشن الكل"),
            ("ترجمه / ترجم", "ترجمة الرسالة المردود عليها للعربية"),
            ("تفعيل الترجمة / تعطيل الترجمة", "تحكم بالترجمة بالرد"),
            ("ترجمة [نص]", "ترجمة نص محدد"),
            ("تثبيت", "تثبيت رسالة + إضافتها للقائمة"),
            ("قائمة التثبيت", "عرض الرسائل المثبتة سابقاً"),
            ("مسح قائمة التثبيت", "مسح قائمة التثبيت"),
            ("الغاء التثبيت", "إلغاء تثبيت"),
            ("مسح", "حذف رسالة"),
            ("طرد البوتات", "طرد البوتات"),
            ("كشف البوتات", "عرض البوتات"),
            ("بايو عشوائي", "تغيير وصف المجموعة"),
            ("مين ضافني", "من أضاف البوت"),
            ("مين طردني", "من طرد البوت"),
            ("الاعدادات", "إعدادات المجموعة"),
            ("احبك", "البوت يرد بكلام محبة"),
            ("اكرهك", "البوت يرد بشكل لطيف"),
            ("بوت", "تنبيه البوت"),
            ("المطور", "معلومات المطور"),
        ]
    ),
    "profile": (
        "🪪 **البطاقة الشخصية**",
        [
            ("آيدي", "عرض بطاقتك الشخصية"),
            ("id", "نفس أمر آيدي"),
            ("آيدي (رد على شخص)", "عرض بطاقة شخص آخر"),
        ]
    ),
    "stats": (
        "📊 **الإحصائيات والنشاط**",
        [
            ("حسابي", "عدد رسائلي وترتيبي"),
            ("ترتيب", "ترتيب الأعضاء"),
            ("توب", "توب 5 الأكثر نشاطاً"),
            ("مسح الاحصائيات", "مسح إحصائيات المجموعة"),
        ]
    ),
    "raid": (
        "🛡 **حماية Raid**",
        [
            ("تفعيل حماية الريد", "تفعيل حماية الريد التلقائية"),
            ("تعطيل حماية الريد", "تعطيل الحماية"),
        ]
    ),
    "download": (
        "⬇️ **التحميل والتعرف**",
        [
            ("بحث [كلمة] / يوت [كلمة]", "بحث وتحميل مباشر من يوتيوب"),
            ("يوتيوب [كلمة]", "4 نتائج بأزرار للاختيار"),
            ("يوتيوب [رابط]", "تحميل صوت من رابط مباشر"),
            ("فيديو [رابط]", "تحميل فيديو من رابط"),
            ("تيك [رابط]", "تحميل من تيك توك"),
            ("ساوند [كلمة أو رابط]", "بحث أو تحميل من SoundCloud"),
            ("شازام", "التعرف على أغنية (ردّ على صوت)"),
            ("شازام [اسم أغنية]", "الحصول على كلمات الأغنية"),
            ("تفعيل/تعطيل يوتيوب", "تحكم بتحميل يوتيوب"),
            ("تفعيل/تعطيل تيك توك", "تحكم بتحميل تيك توك"),
            ("تفعيل/تعطيل ساوند كلاود", "تحكم بتحميل SoundCloud"),
        ]
    ),
    "tts": (
        "🔊 **تحويل النص لصوت**",
        [
            ("انطقي [نص]", "يحول النص لصوت ويرسله كفويس"),
            ("انطق [نص]", "نفس أمر انطقي"),
            ("انطقي (رد على رسالة)", "ينطق نص الرسالة المردود عليها"),
            ("تفعيل انطقي", "تفعيل ميزة انطقي في المجموعة"),
            ("تعطيل انطقي", "تعطيل ميزة انطقي"),
        ]
    ),
    "smart": (
        "🧠 **الردود الذكية**",
        [
            ("تفعيل الردود", "تفعيل الردود التلقائية الذكية"),
            ("تعطيل الردود", "تعطيل الردود التلقائية"),
            ("(صباح الخير، شكراً، كيف حالك...)", "ردود تلقائية عشوائية"),
            ("(كلام فاحش)", "تحذير تلقائي للعضو"),
            ("(آية، دعاء، حديث)", "ردود دينية عشوائية"),
        ]
    ),
    "extra_lists": (
        "📋 **قوائم إضافية**",
        [
            ("رفع كيك @شخص", "إضافة لقائمة الكيك"),
            ("تنزيل كيك @شخص", "إزالة من قائمة الكيك"),
            ("قائمة الكيك", "عرض قائمة الكيك"),
            ("مسح قائمة الكيك", "مسح القائمة"),
            ("رفع عسل / تنزيل عسل", "قائمة العسل"),
            ("قائمة العسل / مسح قائمة العسل", "عرض ومسح قائمة العسل"),
            ("رفع نصاب / تنزيل نصاب", "قائمة النصابين"),
            ("قائمة النصابين / مسح قائمة النصابين", "عرض ومسح قائمة النصابين"),
        ]
    ),
    "cleanup": (
        "🧹 **التنظيف التلقائي**",
        [
            ("تفعيل التنظيف", "تفعيل حذف الرسائل القديمة"),
            ("تعطيل التنظيف", "تعطيل التنظيف"),
            ("وقت التنظيف [مدة]", "تحديد مدة الاحتفاظ"),
        ]
    ),
}


def build_commands_keyboard():
    pages = list(COMMANDS_PAGES.keys())
    buttons = []
    row = []
    LABELS = {
        "admin":       "🛡 الإدارة",
        "locks":       "🔒 الأقفال",
        "welcome":     "👋 الترحيب",
        "filters":     "🤖 الردود",
        "economy":     "💰 الاقتصاد",
        "games":       "🎮 الألعاب",
        "lists":       "🎉 القوائم",
        "fun":         "🎭 الهمس",
        "utils":       "🛠 عام",
        "profile":     "🪪 آيدي",
        "stats":       "📊 الإحصائيات",
        "raid":        "🛡 حماية Raid",
        "download":    "⬇️ التحميل",
        "tts":         "🔊 انطقي",
        "smart":       "🧠 ردود ذكية",
        "extra_lists": "📋 قوائم إضافية",
        "cleanup":     "🧹 التنظيف",
    }
    for i, page in enumerate(pages):
        row.append(InlineKeyboardButton(LABELS.get(page, page), callback_data=f"cmds:{page}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_page_text(page_key: str) -> str:
    title, cmds = COMMANDS_PAGES[page_key]
    p = cfg.BOT_PREFIX
    lines = [f"「 {title} 」\n"]
    for cmd, desc in cmds:
        lines.append(f"{cfg.BOT_SYMBOL} `{p} {cmd}`\n   ↳ _{desc}_\n")
    return "\n".join(lines)


@Client.on_message(prefix_filter("الاوامر"))
async def show_commands(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    await message.reply(
        f"「 أوامر {cfg.BOT_NAME} ༄ 」\n\n"
        f"اختر القسم الذي تريد عرض أوامره:",
        reply_markup=build_commands_keyboard(),
    )


@Client.on_callback_query(filters.regex(r"^cmds:"))
async def commands_callback(client: Client, callback: CallbackQuery):
    page_key = callback.data.split(":")[1]
    if page_key not in COMMANDS_PAGES:
        return await callback.answer("قسم غير موجود.", show_alert=True)

    text = build_page_text(page_key)
    back_button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ رجوع للقائمة", callback_data="cmds:_back")]]
    )
    await callback.message.edit(text, reply_markup=back_button)
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^cmds:_back"))
async def commands_back(client: Client, callback: CallbackQuery):
    await callback.message.edit(
        f"「 أوامر {cfg.BOT_NAME} ༄ 」\n\nاختر القسم:",
        reply_markup=build_commands_keyboard(),
    )
    await callback.answer()


# ─── ردود عاطفية واجتماعية ────────────────────────────────────────
LOVE_REPLIES = [
    "وأنا أحبك أكثر! 🥰",
    "يا هلا فيك، أنت النور 💛",
    "والله حبك يحيّيني ❤️",
    "أنا دايم هنا معك 🤍",
    "حبك يجعلني أشتغل بروح 💙",
]

HATE_REPLIES = [
    "بصراحة؟ أنا أحبك حتى لو أكرهتني 😌",
    "أوكي، بس أنا ما أقدر أكرهك 😅",
    "تمام، بس أنا ما خذيت بالي 😤",
    "ههه، مو مشكلة — أنا بخير 😇",
    "حسناً، سأتجاهل ذلك 🙃",
]


@Client.on_message(prefix_filter("احبك"))
async def bot_love_reply(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    await message.reply(random.choice(LOVE_REPLIES))


@Client.on_message(prefix_filter("اكرهك"))
async def bot_hate_reply(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    await message.reply(random.choice(HATE_REPLIES))


@Client.on_message(prefix_filter("بوت"))
async def bot_attention(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    await message.reply("نعم؟ 👀")


@Client.on_message(prefix_filter("المطور"))
async def show_developer(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    owner_id = cfg.OWNER_ID
    try:
        owner = await client.get_users(owner_id)
        name = owner.first_name or "المطور"
        username = f"@{owner.username}" if owner.username else "—"
        await message.reply(
            f"{cfg.BOT_SYMBOL} **معلومات المطور:**\n"
            f"👑 الاسم: [{name}](tg://user?id={owner_id})\n"
            f"🔗 يوزر: {username}\n"
            f"🆔 الـ ID: `{owner_id}`"
        )
    except Exception:
        await message.reply(
            f"{cfg.BOT_SYMBOL} **المطور:**\n"
            f"🆔 ID: `{owner_id}`"
        )
