import random
import asyncio
from datetime import datetime
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import cfg
from helpers.permissions import is_chat_active
from database.redis_client import rdb, chat_key, global_key


SESSION_TTL = 300
LINK_TTL = 86400

TZ = pytz.timezone("Asia/Riyadh")


def get_now_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def get_or_create_sarhni_id(user_id: int) -> str:
    existing = rdb.get(chat_key(user_id, "sarhni_id"))
    if existing:
        return existing
    rand_id = str(random.randint(100000, 999999))
    rdb.set(chat_key(user_id, "sarhni_id"), rand_id, ex=LINK_TTL)
    rdb.set(f"sarhni:id:{rand_id}", user_id, ex=LINK_TTL)
    return rand_id


@Client.on_message(filters.regex(r"^صارحني$") & filters.group)
async def sarhni_trigger(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not user:
        return

    rand_id = get_or_create_sarhni_id(user.id)
    bot_info = await client.get_me()
    bot_username = bot_info.username
    link = f"https://t.me/{bot_username}?start=sarhni_{rand_id}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 صارحني بشيء", url=link)]
    ])

    await message.reply(
        f"{cfg.BOT_SYMBOL} **صارحني!**\n"
        f"اضغط على الزر أدناه وصارح [{user.first_name}](tg://user?id={user.id}) بشيء بشكل **مجهول** تماماً 🤫\n"
        f"⏳ الجلسة تنتهي بعد **5 دقائق** من بدايتها.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@Client.on_message(filters.command("start") & filters.private)
async def sarhni_start(client: Client, message: Message):
    if not message.command or len(message.command) < 2:
        return
    arg = message.command[1]
    if not arg.startswith("sarhni_"):
        return

    rand_id = arg[len("sarhni_"):]
    sender_id = message.from_user.id

    target_raw = rdb.get(f"sarhni:id:{rand_id}")
    if not target_raw:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} **انتهت صلاحية هذا الرابط أو غير صالح.**"
        )

    target_user_id = int(target_raw)

    if sender_id == target_user_id:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} **ما تقدر تصارح نفسك! 😄**"
        )

    rdb.set(f"sarhni:session:{sender_id}", target_user_id, ex=SESSION_TTL)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء الجلسة", callback_data="sarhni_cancel")]
    ])

    try:
        target_user = await client.get_users(target_user_id)
        target_name = target_user.first_name
    except Exception:
        target_name = "الشخص"

    await message.reply(
        f"{cfg.BOT_SYMBOL} **جلسة صارحني بدأت!**\n"
        f"أنت الآن في جلسة مجهولة مع **{target_name}**.\n"
        f"أرسل أي رسالة (نص، صورة، فيديو، صوت، ملصق) وستصله بشكل **مجهول تماماً** 🤫\n"
        f"⏳ لديك **5 دقائق** قبل انتهاء الجلسة.",
        reply_markup=keyboard,
    )

    asyncio.create_task(_session_expire_notify(client, sender_id, target_user_id))


async def _session_expire_notify(client: Client, sender_id: int, target_user_id: int):
    await asyncio.sleep(SESSION_TTL + 2)
    still_active = rdb.get(f"sarhni:session:{sender_id}")
    if still_active and int(still_active) == target_user_id:
        rdb.delete(f"sarhni:session:{sender_id}")
        try:
            await client.send_message(sender_id, f"{cfg.BOT_SYMBOL} **انتهت جلسة صارحني تلقائياً.**")
        except Exception:
            pass


@Client.on_message(filters.private & ~filters.command([]))
async def sarhni_relay(client: Client, message: Message):
    if not message.from_user:
        return

    sender_id = message.from_user.id
    target_raw = rdb.get(f"sarhni:session:{sender_id}")
    if not target_raw:
        return

    target_user_id = int(target_raw)
    now_str = get_now_str()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ رد", callback_data=f"sarhni_reply_{sender_id}")]
    ])

    anon_header = f"📩 **رسالة مجهولة**\n🕐 `{now_str}`\n\n"

    try:
        if message.text:
            await client.send_message(
                target_user_id,
                anon_header + message.text,
                reply_markup=keyboard,
            )
        elif message.photo:
            await client.send_photo(
                target_user_id,
                message.photo.file_id,
                caption=anon_header + (message.caption or ""),
                reply_markup=keyboard,
            )
        elif message.video:
            await client.send_video(
                target_user_id,
                message.video.file_id,
                caption=anon_header + (message.caption or ""),
                reply_markup=keyboard,
            )
        elif message.audio:
            await client.send_audio(
                target_user_id,
                message.audio.file_id,
                caption=anon_header + (message.caption or ""),
                reply_markup=keyboard,
            )
        elif message.voice:
            await client.send_voice(
                target_user_id,
                message.voice.file_id,
                caption=anon_header + (message.caption or ""),
                reply_markup=keyboard,
            )
        elif message.sticker:
            await client.send_sticker(target_user_id, message.sticker.file_id)
            await client.send_message(
                target_user_id,
                anon_header + "🖼 أرسل لك ملصق",
                reply_markup=keyboard,
            )
        elif message.document:
            await client.send_document(
                target_user_id,
                message.document.file_id,
                caption=anon_header + (message.caption or ""),
                reply_markup=keyboard,
            )
        else:
            await message.reply(f"{cfg.BOT_SYMBOL} **نوع الرسالة غير مدعوم.**")
            return

        await message.reply(f"{cfg.BOT_SYMBOL} **تم إرسال رسالتك بشكل مجهول ✓**")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل إرسال الرسالة:** `{e}`")


@Client.on_callback_query(filters.regex(r"^sarhni_cancel$"))
async def sarhni_cancel_cb(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    rdb.delete(f"sarhni:session:{user_id}")
    await callback.message.edit_text(f"{cfg.BOT_SYMBOL} **تم إلغاء جلسة صارحني.**")
    await callback.answer("تم الإلغاء")


@Client.on_callback_query(filters.regex(r"^sarhni_reply_(\d+)$"))
async def sarhni_reply_cb(client: Client, callback: CallbackQuery):
    import re
    m = re.match(r"^sarhni_reply_(\d+)$", callback.data)
    if not m:
        return
    original_sender_id = int(m.group(1))
    replier_id = callback.from_user.id

    rdb.set(f"sarhni:session:{replier_id}", original_sender_id, ex=SESSION_TTL)

    cancel_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء الرد", callback_data="sarhni_cancel")]
    ])

    await callback.message.reply(
        f"{cfg.BOT_SYMBOL} **وضع الرد المجهول مفعّل.**\n"
        f"أرسل ردك الآن وسيصل بشكل مجهول.\n"
        f"⏳ لديك **5 دقائق**.",
        reply_markup=cancel_kb,
    )
    await callback.answer("أرسل ردك الآن")

    asyncio.create_task(_session_expire_notify(client, replier_id, original_sender_id))
