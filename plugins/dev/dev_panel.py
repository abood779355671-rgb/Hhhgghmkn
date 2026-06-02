import asyncio
import os
import sys
import time
import traceback
from io import StringIO
from datetime import datetime, timedelta
import psutil
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import cfg
from helpers.permissions import get_user_rank, get_active_chats
from database.redis_client import rdb, global_key


_START_TIME = time.time()


def is_dev(user_id: int) -> bool:
    rank = get_user_rank(user_id)
    return rank <= cfg.RANK_DEV


def is_owner(user_id: int) -> bool:
    return user_id == cfg.OWNER_ID


def build_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="dev_stats"),
            InlineKeyboardButton("🖥 معلومات السيرفر", callback_data="dev_server"),
        ],
        [
            InlineKeyboardButton("📢 إذاعة", callback_data="dev_broadcast"),
            InlineKeyboardButton("🔄 تحديث", callback_data="dev_restart"),
        ],
        [
            InlineKeyboardButton("📝 اسم البوت", callback_data="dev_show_name"),
            InlineKeyboardButton("✏️ تعيين اسم البوت", callback_data="dev_set_name"),
        ],
        [
            InlineKeyboardButton("💎 رمز البوت", callback_data="dev_show_symbol"),
            InlineKeyboardButton("✏️ تعيين رمز البوت", callback_data="dev_set_symbol"),
        ],
    ])


@Client.on_message(filters.command("start") & filters.private)
async def dev_start(client: Client, message: Message):
    if not message.command or len(message.command) == 1:
        user_id = message.from_user.id
        if not is_dev(user_id):
            return await message.reply(
                f"{cfg.BOT_SYMBOL} **أهلاً بك في {cfg.BOT_NAME}!**\n"
                f"استخدم البوت في المجموعات 🤖"
            )
        await message.reply(
            f"{cfg.BOT_SYMBOL} **لوحة تحكم {cfg.BOT_NAME}**\n"
            f"مرحباً بك يا مطور 👨‍💻",
            reply_markup=build_panel_keyboard(),
        )


@Client.on_callback_query(filters.regex(r"^dev_stats$"))
async def cb_stats(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    active_chats = get_active_chats()
    user_keys = rdb.keys("raad:*:user:*:rank")
    await callback.message.edit_text(
        f"{cfg.BOT_SYMBOL} **إحصائيات {cfg.BOT_NAME}:**\n\n"
        f"🏘 المجموعات النشطة: **{len(active_chats)}**\n"
        f"👤 المستخدمون في Redis: **{len(user_keys)}**",
        reply_markup=build_panel_keyboard(),
    )
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^dev_server$"))
async def cb_server(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime_sec = int(time.time() - _START_TIME)
    uptime_str = str(timedelta(seconds=uptime_sec))

    await callback.message.edit_text(
        f"{cfg.BOT_SYMBOL} **معلومات السيرفر:**\n\n"
        f"💻 CPU: **{cpu}%**\n"
        f"🧠 RAM: **{mem.percent}%** ({mem.used // 1024 // 1024} MB / {mem.total // 1024 // 1024} MB)\n"
        f"💾 Disk: **{disk.percent}%** ({disk.used // 1024 // 1024 // 1024} GB / {disk.total // 1024 // 1024 // 1024} GB)\n"
        f"⏱ Uptime: **{uptime_str}**",
        reply_markup=build_panel_keyboard(),
    )
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^dev_restart$"))
async def cb_restart(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    await callback.message.edit_text(f"{cfg.BOT_SYMBOL} **جاري إعادة التشغيل...** 🔄")
    await callback.answer("إعادة تشغيل...")
    await asyncio.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_callback_query(filters.regex(r"^dev_broadcast$"))
async def cb_broadcast(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    rdb.set(f"dev_broadcast_wait:{callback.from_user.id}", "1", ex=300)
    await callback.message.reply(
        f"{cfg.BOT_SYMBOL} **أرسل الرسالة التي تريد إذاعتها لكل المجموعات النشطة:**\n"
        f"(ترسَل بشكل forward)"
    )
    await callback.answer("أرسل الرسالة")


@Client.on_callback_query(filters.regex(r"^dev_show_name$"))
async def cb_show_name(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    await callback.answer(f"اسم البوت الحالي: {cfg.BOT_NAME}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^dev_set_name$"))
async def cb_set_name(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    rdb.set(f"dev_set_name_wait:{callback.from_user.id}", "1", ex=120)
    await callback.message.reply(f"{cfg.BOT_SYMBOL} **أرسل الاسم الجديد للبوت:**")
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^dev_show_symbol$"))
async def cb_show_symbol(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    await callback.answer(f"رمز البوت الحالي: {cfg.BOT_SYMBOL}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^dev_set_symbol$"))
async def cb_set_symbol(client: Client, callback: CallbackQuery):
    if not is_dev(callback.from_user.id):
        return await callback.answer("ما عندك صلاحية", show_alert=True)
    rdb.set(f"dev_set_symbol_wait:{callback.from_user.id}", "1", ex=120)
    await callback.message.reply(f"{cfg.BOT_SYMBOL} **أرسل الرمز الجديد للبوت:**")
    await callback.answer()


@Client.on_message(filters.private & filters.text)
async def dev_private_handler(client: Client, message: Message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    text = message.text.strip()

    if rdb.get(f"dev_broadcast_wait:{user_id}") and is_dev(user_id):
        rdb.delete(f"dev_broadcast_wait:{user_id}")
        active_chats = get_active_chats()
        sent = 0
        failed = 0
        for chat_id in active_chats:
            try:
                await message.forward(chat_id)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        return await message.reply(
            f"{cfg.BOT_SYMBOL} **تمت الإذاعة:**\n"
            f"✅ نجح: **{sent}**\n"
            f"❌ فشل: **{failed}**"
        )

    if rdb.get(f"dev_set_name_wait:{user_id}") and is_dev(user_id):
        rdb.delete(f"dev_set_name_wait:{user_id}")
        cfg.BOT_NAME = text
        rdb.set(global_key("bot_name"), text)
        return await message.reply(f"{cfg.BOT_SYMBOL} تم تعيين اسم البوت إلى: **{text}** ✓")

    if rdb.get(f"dev_set_symbol_wait:{user_id}") and is_dev(user_id):
        rdb.delete(f"dev_set_symbol_wait:{user_id}")
        cfg.BOT_SYMBOL = text
        rdb.set(global_key("bot_symbol"), text)
        return await message.reply(f"{cfg.BOT_SYMBOL} تم تعيين رمز البوت إلى: **{text}** ✓")

    if text.startswith(". ") and is_owner(user_id):
        code = text[2:].strip()
        await execute_code(client, message, code)


async def execute_code(client: Client, message: Message, code: str):
    env = {
        "client": client,
        "message": message,
        "cfg": cfg,
        "rdb": rdb,
        "__builtins__": __builtins__,
    }
    old_stdout = sys.stdout
    sys.stdout = buf = StringIO()
    result = None
    error = None
    try:
        exec_globals = env.copy()
        exec(compile(code, "<dev_exec>", "exec"), exec_globals)
        if "result" in exec_globals:
            result = exec_globals["result"]
    except Exception:
        error = traceback.format_exc()
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()
    response = f"{cfg.BOT_SYMBOL} **تنفيذ الكود:**\n"
    if output:
        response += f"\n📤 **Output:**\n```\n{output[:3000]}\n```"
    if result is not None:
        response += f"\n✅ **Result:** `{str(result)[:500]}`"
    if error:
        response += f"\n❌ **Error:**\n```\n{error[:2000]}\n```"
    if not output and result is None and not error:
        response += "\n✅ **نُفِّذ بنجاح (لا يوجد ناتج)**"

    await message.reply(response)


@Client.on_message(filters.regex(r"^\. ") & filters.private)
async def meval_shortcut(client: Client, message: Message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    code = message.text[2:].strip()
    await execute_code(client, message, code)
