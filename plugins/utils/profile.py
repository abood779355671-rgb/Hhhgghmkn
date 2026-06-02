import random
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import resolve_user
from database.redis_client import rdb, chat_key, user_key


# ═══════════════════════════════════════════════════════════════════
#  عداد الرسائل — group=-1 ليكون أول ما يُنفَّذ
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.text, group=-1)
async def count_messages(client: Client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id
    cid = message.chat.id
    rdb.incr(user_key(uid, "msgs"))
    rdb.incr(chat_key(cid, "user", uid, "msgs"))
    rdb.sadd(chat_key(cid, "members"), uid)


# ═══════════════════════════════════════════════════════════════════
#  بطاقة الهوية — تصاميم متعددة
# ═══════════════════════════════════════════════════════════════════

RANK_ICONS = {
    cfg.RANK_OWNER:  "👑",
    cfg.RANK_DEV:    "💻",
    cfg.RANK_DEV2:   "🔰",
    cfg.RANK_MOD:    "🛡",
    cfg.RANK_ADMIN:  "⚡",
    cfg.RANK_MEMBER: "👤",
}


def _rank_name(rank: int) -> str:
    return cfg.RANK_NAMES.get(rank, "👤 عضو")


def _rank_icon(rank: int) -> str:
    return RANK_ICONS.get(rank, "👤")


def _msg_count(user_id: int, chat_id: int) -> int:
    v = rdb.get(chat_key(chat_id, "user", user_id, "msgs"))
    return int(v) if v else 0


def _build_card(user, rank: int, msgs: int, bio: str | None, design: int, chat_title: str) -> str:
    name = user.first_name or ""
    uname = f"@{user.username}" if user.username else "لا يوجد"
    uid = user.id
    rank_name = _rank_name(rank)
    rank_icon = _rank_icon(rank)
    bio_text = bio or "لا يوجد"

    if design == 0:
        return (
            f"┌─────────────────────┐\n"
            f"│    🪪 **بطاقة شخصية**\n"
            f"├─────────────────────┤\n"
            f"│ 👤 **الاسم:** {name}\n"
            f"│ 🔖 **اليوزر:** {uname}\n"
            f"│ 🆔 **الآيدي:** `{uid}`\n"
            f"│ {rank_icon} **الرتبة:** {rank_name}\n"
            f"│ 💬 **رسائله:** {msgs:,}\n"
            f"│ 📝 **البايو:** {bio_text}\n"
            f"└─────────────────────┘"
        )

    elif design == 1:
        return (
            f"╔══ 🪪 البطاقة الشخصية ══╗\n\n"
            f"  ✦ الاسم ➤ **{name}**\n"
            f"  ✦ اليوزر ➤ **{uname}**\n"
            f"  ✦ الآيدي ➤ `{uid}`\n"
            f"  ✦ الرتبة ➤ {rank_icon} **{rank_name}**\n"
            f"  ✦ الرسائل ➤ 💬 **{msgs:,}**\n"
            f"  ✦ البايو ➤ _{bio_text}_\n\n"
            f"╚══════════════════════╝"
        )

    elif design == 2:
        return (
            f"「 **بطاقتك في {chat_title}** 」\n\n"
            f"🔹 الاسم: **{name}**\n"
            f"🔹 اليوزر: {uname}\n"
            f"🔹 الآيدي: `{uid}`\n"
            f"🔹 الرتبة: {rank_icon} {rank_name}\n"
            f"🔹 إجمالي رسائلك: **{msgs:,}** رسالة\n"
            f"🔹 نبذة: _{bio_text}_"
        )

    elif design == 3:
        stars = "⭐" * min(5, max(1, msgs // 50))
        return (
            f"🃏 **≡ بطاقة الهوية ≡**\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📛 **{name}** | {uname}\n"
            f"🆔 ID: `{uid}`\n"
            f"🏅 الرتبة: {rank_name}\n"
            f"💬 نشاطه: {stars}\n"
            f"📊 رسائله: **{msgs:,}**\n"
            f"📖 البايو: _{bio_text}_\n"
            f"━━━━━━━━━━━━━━━━━"
        )

    elif design == 4:
        level = (
            "🥇 أسطوري" if msgs >= 1000 else
            "🥈 متقدم" if msgs >= 500 else
            "🥉 نشيط" if msgs >= 100 else
            "🔰 مبتدئ"
        )
        return (
            f"⚡ **{cfg.BOT_NAME} — بطاقة شخصية**\n\n"
            f"❱ الاسم: **{name}**\n"
            f"❱ اليوزر: {uname}\n"
            f"❱ الآيدي: `{uid}`\n"
            f"❱ الصلاحية: {rank_icon} {rank_name}\n"
            f"❱ مستوى النشاط: {level}\n"
            f"❱ عدد الرسائل: **{msgs:,}**\n"
            f"❱ نبذة: _{bio_text}_"
        )

    else:
        return (
            f"✧ **بطاقة {name}** ✧\n"
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"• اليوزر: {uname}\n"
            f"• الآيدي: `{uid}`\n"
            f"• الرتبة: {rank_icon} {rank_name}\n"
            f"• رسائله: {msgs:,}\n"
            f"• البايو: {bio_text}\n"
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
        )


# ─── أمر آيدي ─────────────────────────────────────────────────────
@Client.on_message(
    filters.group & filters.regex(r"^(آيدي|id|ايدي|ID)$", flags=8),
    group=5,
)
async def show_profile(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return

    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    else:
        target_user = message.from_user

    if not target_user:
        return

    uid = target_user.id
    cid = message.chat.id

    rank = get_user_rank(uid, cid)
    msgs = _msg_count(uid, cid)

    bio = None
    try:
        full = await client.get_users(uid)
        bio = getattr(full, "bio", None) or getattr(full, "status", None)
        if bio and not isinstance(bio, str):
            bio = None
    except Exception:
        pass

    design = random.randint(0, 5)
    card = _build_card(
        target_user, rank, msgs, bio, design,
        message.chat.title or "المجموعة",
    )

    if target_user.photo:
        try:
            photo = await client.download_media(target_user.photo.small_file_id)
            await client.send_photo(cid, photo, caption=card, reply_to_message_id=message.id)
            import os
            os.remove(photo)
            return
        except Exception:
            pass

    await message.reply(card)
