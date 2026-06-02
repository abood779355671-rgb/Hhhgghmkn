import os
import uuid
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting, run_in_thread


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


def _tts_to_file(text: str) -> str:
    from gtts import gTTS
    os.makedirs("downloads", exist_ok=True)
    path = f"downloads/tts_{uuid.uuid4().hex}.mp3"
    tts = gTTS(text=text, lang="ar", slow=False)
    tts.save(path)
    return path


# ─── تفعيل / تعطيل ────────────────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل انطقي"))
async def enable_tts(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "tts_enabled", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل ميزة انطقي** ✓")


@Client.on_message(prefix_filter("تعطيل انطقي"))
async def disable_tts(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "tts_enabled", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل ميزة انطقي** ✓")


# ─── أمر انطقي / انطق ─────────────────────────────────────────────
@Client.on_message(
    filters.group &
    filters.regex(rf"^(انطقي|انطق)\s*(.*)", flags=8)
)
async def tts_command(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "tts_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} ميزة **انطقي** معطّلة في هذه المجموعة.")

    import re
    m = re.match(r"^(انطقي|انطق)\s*(.*)", message.text, re.DOTALL | re.IGNORECASE)
    text = (m.group(2) or "").strip() if m else ""

    if not text and message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text.strip()

    if not text:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} **اكتب النص بعد الأمر** أو ردّ على رسالة:\n"
            f"`انطقي [النص]`"
        )

    if len(text) > 500:
        return await message.reply(f"{cfg.BOT_SYMBOL} **النص طويل جداً** (الحد الأقصى 500 حرف).")

    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري تحويل النص لصوت... 🔊")
    file_path = None
    try:
        file_path = await run_in_thread(_tts_to_file, text)
        await client.send_voice(
            message.chat.id,
            file_path,
            reply_to_message_id=message.id,
        )
        await msg.delete()
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **فشل التحويل:** `{e}`")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
