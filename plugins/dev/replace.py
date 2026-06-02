import os
import sys
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


BOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPLACE_STEPS: dict[str, dict] = {}


def _is_dev(user_id: int) -> bool:
    return get_user_rank(user_id) <= cfg.RANK_DEV


def _safe_path(filename: str) -> str | None:
    target = os.path.normpath(os.path.join(BOT_DIR, filename))
    if not target.startswith(BOT_DIR):
        return None
    if not target.endswith(".py"):
        return None
    if not os.path.isfile(target):
        return None
    return target


def _do_replace(filepath: str, old: str, new: str) -> tuple[int, str]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old)
    if count == 0:
        return 0, content

    updated = content.replace(old, new)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(updated)

    return count, updated


@Client.on_message(prefix_filter("استبدال كلمة"))
async def replace_word_start(client: Client, message: Message):
    if not message.from_user:
        return
    if not _is_dev(message.from_user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية. يحتاج رتبة مطور.**")

    uid = message.from_user.id
    REPLACE_STEPS[uid] = {"step": "old_word", "chat_id": message.chat.id}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **أداة استبدال الكلمات** 🔧\n\n"
        f"**الخطوة 1/3:** أرسل **الكلمة القديمة** التي تريد استبدالها:"
    )


@Client.on_message(filters.group & filters.text, group=2)
async def replace_word_steps(client: Client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id

    if uid not in REPLACE_STEPS:
        return
    if REPLACE_STEPS[uid].get("chat_id") != message.chat.id:
        return

    state = REPLACE_STEPS[uid]
    text = message.text.strip()

    if state["step"] == "old_word":
        state["old_word"] = text
        state["step"] = "new_word"
        await message.reply(
            f"{cfg.BOT_SYMBOL} **الخطوة 2/3:** أرسل **الكلمة الجديدة** (البديل):"
        )

    elif state["step"] == "new_word":
        state["new_word"] = text
        state["step"] = "filename"
        await message.reply(
            f"{cfg.BOT_SYMBOL} **الخطوة 3/3:** أرسل **مسار الملف** نسبةً لمجلد البوت:\n"
            f"مثال: `plugins/utils/general.py` أو `config.py`"
        )

    elif state["step"] == "filename":
        filepath = _safe_path(text)
        if not filepath:
            del REPLACE_STEPS[uid]
            return await message.reply(
                f"{cfg.BOT_SYMBOL} **خطأ:** الملف غير موجود أو غير مسموح به.\n"
                f"تأكد أن المسار صحيح وأن الملف `.py`"
            )

        old_word = state["old_word"]
        new_word = state["new_word"]
        del REPLACE_STEPS[uid]

        count, _ = _do_replace(filepath, old_word, new_word)
        if count == 0:
            return await message.reply(
                f"{cfg.BOT_SYMBOL} **الكلمة غير موجودة** في الملف `{text}`."
            )

        await message.reply(
            f"{cfg.BOT_SYMBOL} ✅ **تم الاستبدال بنجاح!**\n\n"
            f"📁 الملف: `{text}`\n"
            f"🔄 تم استبدال: `{old_word}` ← `{new_word}`\n"
            f"📊 عدد مرات الاستبدال: **{count}**\n\n"
            f"🔄 جاري إعادة تشغيل البوت..."
        )

        await asyncio.sleep(2)
        os.execl(sys.executable, sys.executable, *sys.argv)
