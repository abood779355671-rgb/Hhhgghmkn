import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting, build_mention
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


NO_PERMS = ChatPermissions(can_send_messages=False)
ALL_PERMS = ChatPermissions(
    can_send_messages=True, can_send_media_messages=True,
    can_send_other_messages=True, can_add_web_page_previews=True,
    can_invite_users=True,
)

MATH_QUESTIONS = [
    (f"{a} + {b}", str(a + b)) for a in range(2, 10) for b in range(2, 10)
] + [
    (f"{a} × {b}", str(a * b)) for a in range(2, 6) for b in range(2, 6)
]


def is_captcha_enabled(chat_id: int) -> bool:
    return get_chat_setting(chat_id, "captcha_enabled", False) is True


def pending_key(chat_id: int, user_id: int) -> str:
    return chat_key(chat_id, f"captcha_pending:{user_id}")


# ─── تفعيل / تعطيل الكابتشا ─────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل التحقق"))
async def enable_captcha(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "captcha_enabled", True)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم تفعيل **التحقق عند الدخول** ✓\n"
        f"سيُطلب من كل عضو جديد حل مسألة قبل الكلام."
    )


@Client.on_message(prefix_filter("تعطيل التحقق"))
async def disable_captcha(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "captcha_enabled", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم تعطيل **التحقق عند الدخول** ✓")


# ─── إرسال الكابتشا عند الدخول ───────────────────────────────────
@Client.on_chat_member_updated(filters.group)
async def send_captcha_on_join(client: Client, update: ChatMemberUpdated):
    if not update.new_chat_member:
        return
    if not is_chat_active(update.chat.id):
        return
    if not is_captcha_enabled(update.chat.id):
        return

    old = update.old_chat_member
    if old and old.status.name not in ("LEFT", "BANNED"):
        return

    user = update.new_chat_member.user
    if user.is_bot:
        return

    chat_id = update.chat.id

    # قيّد المستخدم مؤقتاً
    try:
        await client.restrict_chat_member(chat_id, user.id, NO_PERMS)
    except Exception:
        return

    # اختر سؤالاً عشوائياً
    question, correct = random.choice(MATH_QUESTIONS)

    # أجوبة خاطئة عشوائية مختلفة
    wrong_answers = set()
    while len(wrong_answers) < 3:
        fake = str(int(correct) + random.randint(-5, 5))
        if fake != correct and fake not in wrong_answers:
            wrong_answers.add(fake)

    options = list(wrong_answers) + [correct]
    random.shuffle(options)

    buttons = [
        [InlineKeyboardButton(opt, callback_data=f"captcha:{chat_id}:{user.id}:{correct}:{opt}")]
        for opt in options
    ]

    pending_data = {"question": question, "answer": correct}
    import json
    rdb.set(pending_key(chat_id, user.id), json.dumps(pending_data), ex=120)

    try:
        sent = await client.send_message(
            chat_id,
            f"「 تحقق من الدخول 」\n\n"
            f"أهلاً {build_mention(user)}!\n"
            f"حل هذه المسألة خلال **دقيقتين** للكلام في المجموعة:\n\n"
            f"🧮 **{question} = ?**",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

        # انتظر دقيقتين ثم اطرد إذا لم يجب
        await asyncio.sleep(120)
        if rdb.exists(pending_key(chat_id, user.id)):
            rdb.delete(pending_key(chat_id, user.id))
            try:
                await client.ban_chat_member(chat_id, user.id)
                await client.unban_chat_member(chat_id, user.id)
                await sent.edit(
                    f"{cfg.BOT_SYMBOL} لم يجب {build_mention(user)} على التحقق — تم طرده. 🚪"
                )
            except Exception:
                pass
    except Exception:
        pass


# ─── معالجة إجابة الكابتشا ───────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^captcha:"))
async def handle_captcha_answer(client: Client, callback: CallbackQuery):
    import json
    data = callback.data.split(":")
    if len(data) < 5:
        return await callback.answer("بيانات غير صالحة.", show_alert=True)

    _, chat_id_str, uid_str, correct, chosen = data
    chat_id = int(chat_id_str)
    uid = int(uid_str)

    # فقط صاحب التحقق يقدر يضغط
    if callback.from_user.id != uid:
        return await callback.answer("هذا التحقق مو لك! 🙂", show_alert=True)

    key = pending_key(chat_id, uid)
    if not rdb.exists(key):
        return await callback.answer("انتهت مدة التحقق.", show_alert=True)

    if chosen == correct:
        rdb.delete(key)
        try:
            await client.restrict_chat_member(chat_id, uid, ALL_PERMS)
        except Exception:
            pass
        await callback.answer("✅ إجابة صحيحة! أهلاً بك.", show_alert=True)
        try:
            user = callback.from_user
            await callback.message.edit(
                f"{cfg.BOT_SYMBOL} {build_mention(user)} اجتاز التحقق بنجاح ✓ أهلاً وسهلاً!"
            )
        except Exception:
            pass
    else:
        await callback.answer("❌ إجابة خاطئة! حاول مرة أخرى.", show_alert=True)
