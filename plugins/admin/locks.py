import re
import time
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting, safe_delete, build_mention
from database.redis_client import rdb, chat_key, user_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ─── كلمات السب ──────────────────────────────────────────────────
CURSE_WORDS = [
    "كلب", "حمار", "غبي", "أحمق", "تافه", "زبالة",
    "لعين", "ملعون", "خنزير", "قرد",
]

# ─── كلمات إباحية ─────────────────────────────────────────────────
ADULT_WORDS = [
    "سكس", "بورن", "xxx", "بزاز", "طيز", "كس", "زب",
    "نيك", "شرموطة", "عاهرة", "خول", "متناك",
    "porn", "sex", "nude", "naked", "fuck",
]

# ─── نطاق الحروف الفارسية / الأردية ──────────────────────────────
PERSIAN_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
ARABIC_RANGE = re.compile(r"[\u0621-\u064A\u0660-\u0669]")


def _has_persian(text: str) -> bool:
    """يكتشف حروف فارسية/أردية (ليست عربية أصيلة)"""
    persian_chars = re.compile(r"[\u0686\u0698\u067E\u06AF\u06A9\u0679\u0688\u0691\u06BA\u06BE\u06C1\u06D2\u06CC\u0622\u0623\u0624\u0626]")
    return bool(persian_chars.search(text))


def is_locked(chat_id: int, lock_type: str) -> bool:
    return get_chat_setting(chat_id, f"lock_{lock_type}", False) is True


def build_lock_status(chat_id: int) -> str:
    lines = [f"{cfg.BOT_SYMBOL} **حالة الأقفال:**\n"]
    for lock_type, name in cfg.LOCK_NAMES.items():
        status = "🔒 مقفل" if is_locked(chat_id, lock_type) else "🔓 مفتوح"
        lines.append(f"• {name}: {status}")
    return "\n".join(lines)


# ─── أوامر القفل / الفتح ─────────────────────────────────────────
@Client.on_message(prefix_filter(r"قفل\s+(\S+)"))
async def lock_content(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    m = re.search(r"قفل\s+(\S+)", message.text)
    if not m:
        return
    target = m.group(1).strip()

    if target == "الكل":
        for lt in cfg.LOCK_TYPES:
            set_chat_setting(message.chat.id, f"lock_{lt}", True)
        return await message.reply(f"{cfg.BOT_SYMBOL} تم **قفل الكل** 🔒")

    matched = next(
        (lt for lt, name in cfg.LOCK_NAMES.items() if target in (name, lt)), None
    )
    if not matched:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} نوع غير معروف.\nالمتاح: {', '.join(cfg.LOCK_NAMES.values())}"
        )
    set_chat_setting(message.chat.id, f"lock_{matched}", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم قفل **{cfg.LOCK_NAMES[matched]}** 🔒")


@Client.on_message(prefix_filter(r"فتح\s+(\S+)"))
async def unlock_content(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    m = re.search(r"فتح\s+(\S+)", message.text)
    if not m:
        return
    target = m.group(1).strip()

    if target == "الكل":
        for lt in cfg.LOCK_TYPES:
            set_chat_setting(message.chat.id, f"lock_{lt}", False)
        return await message.reply(f"{cfg.BOT_SYMBOL} تم **فتح الكل** 🔓")

    matched = next(
        (lt for lt, name in cfg.LOCK_NAMES.items() if target in (name, lt)), None
    )
    if not matched:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} نوع غير معروف.\nالمتاح: {', '.join(cfg.LOCK_NAMES.values())}"
        )
    set_chat_setting(message.chat.id, f"lock_{matched}", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم فتح **{cfg.LOCK_NAMES[matched]}** 🔓")


@Client.on_message(prefix_filter("الاقفال"))
async def show_locks(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    await message.reply(build_lock_status(message.chat.id))


@Client.on_message(prefix_filter("قفل الدردشة"))
async def lock_chat(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    from pyrogram.types import ChatPermissions
    await client.set_chat_permissions(message.chat.id, ChatPermissions(can_send_messages=False))
    set_chat_setting(message.chat.id, "chat_locked", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **قفل الدردشة** — الإدارة فقط 🔒")


@Client.on_message(prefix_filter("فتح الدردشة"))
async def unlock_chat(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    from pyrogram.types import ChatPermissions
    await client.set_chat_permissions(
        message.chat.id,
        ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True,
        ),
    )
    set_chat_setting(message.chat.id, "chat_locked", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **فتح الدردشة** 🔓")


# ─── قفل الدخول (joins) — يطرد البوتات الجديدة ──────────────────
@Client.on_chat_member_updated(filters.group)
async def enforce_joins_lock(client: Client, update: ChatMemberUpdated):
    if not update.new_chat_member:
        return
    if not is_chat_active(update.chat.id):
        return
    if not is_locked(update.chat.id, "joins"):
        return

    user = update.new_chat_member.user
    if user.is_bot:
        bot_me = await client.get_me()
        if user.id == bot_me.id:
            return
        try:
            await client.ban_chat_member(update.chat.id, user.id)
            await client.unban_chat_member(update.chat.id, user.id)
            await client.send_message(
                update.chat.id,
                f"{cfg.BOT_SYMBOL} تم طرد البوت **{user.first_name}** تلقائياً — قفل الدخول مفعّل 🔒"
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
#  تطبيق الأقفال على الرسائل — group=1
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(filters.group, group=1)
async def enforce_locks(client: Client, message: Message):
    if not message.from_user:
        return
    if not is_chat_active(message.chat.id):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    actor_rank = get_user_rank(user_id, chat_id)

    if actor_rank <= cfg.RANK_ADMIN:
        return

    # ─── الروابط ──────────────────────────────────────────────────
    if is_locked(chat_id, "links") and message.entities:
        for ent in message.entities:
            if ent.type.name in ("URL", "TEXT_LINK"):
                await safe_delete(message)
                return

    # ─── الصور ────────────────────────────────────────────────────
    if is_locked(chat_id, "photos") and message.photo:
        await safe_delete(message)
        return

    # ─── الفيديو ──────────────────────────────────────────────────
    if is_locked(chat_id, "videos") and message.video:
        await safe_delete(message)
        return

    # ─── الملفات ──────────────────────────────────────────────────
    if is_locked(chat_id, "documents") and message.document:
        await safe_delete(message)
        return

    # ─── الملصقات ─────────────────────────────────────────────────
    if is_locked(chat_id, "stickers") and message.sticker:
        await safe_delete(message)
        return

    # ─── الفويسات ─────────────────────────────────────────────────
    if is_locked(chat_id, "voices") and (message.voice or message.audio):
        await safe_delete(message)
        return

    # ─── الهاشتاق ─────────────────────────────────────────────────
    if is_locked(chat_id, "hashtags") and message.text and "#" in message.text:
        await safe_delete(message)
        return

    # ─── التوجيه ──────────────────────────────────────────────────
    if is_locked(chat_id, "forwards") and message.forward_date:
        await safe_delete(message)
        return

    # ─── المنشن ───────────────────────────────────────────────────
    if is_locked(chat_id, "mentions") and message.entities:
        for ent in message.entities:
            if ent.type.name == "MENTION":
                await safe_delete(message)
                return

    # ─── السب ─────────────────────────────────────────────────────
    if is_locked(chat_id, "curses") and message.text:
        for word in CURSE_WORDS:
            if word in message.text:
                await safe_delete(message)
                return

    # ─── البوتات ──────────────────────────────────────────────────
    if is_locked(chat_id, "bots") and message.from_user and message.from_user.is_bot:
        await safe_delete(message)
        return

    # ─── القنوات ──────────────────────────────────────────────────
    if is_locked(chat_id, "channels") and message.sender_chat:
        await safe_delete(message)
        return

    # ─── التكرار (لكل مستخدم على حدة) ───────────────────────────
    if is_locked(chat_id, "duplicates") and message.text:
        dup_key = chat_key(chat_id, "dup", user_id)
        last = rdb.get(dup_key)
        if last == message.text:
            await safe_delete(message)
            return
        rdb.set(dup_key, message.text, ex=60)

    # ─── الفارسية / الإيراني ─────────────────────────────────────
    if is_locked(chat_id, "persian") and message.text:
        if _has_persian(message.text):
            await safe_delete(message)
            return

    if is_locked(chat_id, "irani") and message.text:
        if _has_persian(message.text):
            await safe_delete(message)
            return

    # ─── الكلايش (رسائل طويلة > 200 حرف) ────────────────────────
    if is_locked(chat_id, "klish") and message.text:
        if len(message.text) > 200:
            await safe_delete(message)
            return

    # ─── الإباحي ──────────────────────────────────────────────────
    if is_locked(chat_id, "adult") and message.text:
        text_low = message.text.lower()
        for word in ADULT_WORDS:
            if word in text_low:
                await safe_delete(message)
                return

    # ─── الانلاين (يحذف رسائل الأعضاء العاديين فقط) ─────────────
    if is_locked(chat_id, "online"):
        if actor_rank >= cfg.RANK_MEMBER:
            await safe_delete(message)
            return
