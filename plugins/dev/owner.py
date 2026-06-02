import sys
import io
import os
import asyncio
import traceback
import psutil
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, get_active_chats
from database.redis_client import rdb, ping as redis_ping


def owner_filter():
    return filters.user(cfg.OWNER_ID) & filters.private | filters.user(cfg.OWNER_ID) & filters.group


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.user(cfg.OWNER_ID)


@Client.on_message(filters.command("eval") & filters.user(cfg.OWNER_ID))
async def eval_code(client: Client, message: Message):
    """تشغيل كود Python مباشرة"""
    code = message.text.split(None, 1)
    if len(code) < 2:
        return await message.reply(f"{cfg.BOT_SYMBOL} أرسل الكود بعد الأمر.")

    code = code[1]
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        exec_globals = {
            "client": client,
            "message": message,
            "rdb": rdb,
            "cfg": cfg,
        }
        exec(compile(f"async def __exec():\n{chr(10).join('    ' + l for l in code.splitlines())}", "<eval>", "exec"), exec_globals)
        result = await exec_globals["__exec"]()
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        response = ""
        if output:
            response += f"**Output:**\n```\n{output}\n```\n"
        if result is not None:
            response += f"**Return:**\n```\n{result}\n```"
        if not response:
            response = f"{cfg.BOT_SYMBOL} تم التنفيذ بنجاح (لا مخرجات)."

    except Exception:
        sys.stdout = old_stdout
        response = f"**خطأ:**\n```\n{traceback.format_exc()}\n```"

    await message.reply(response[:4000])


@Client.on_message(filters.command("sh") & filters.user(cfg.OWNER_ID))
async def shell_command(client: Client, message: Message):
    """تنفيذ أوامر الشل"""
    cmd = message.text.split(None, 1)
    if len(cmd) < 2:
        return await message.reply(f"{cfg.BOT_SYMBOL} أرسل الأمر بعد /sh")

    cmd = cmd[1]
    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري التنفيذ...")
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = (stdout + stderr).decode()
        if not output:
            output = "تم التنفيذ بدون مخرجات."
        await msg.edit(f"```\n{output[:3800]}\n```")
    except asyncio.TimeoutError:
        await msg.edit(f"{cfg.BOT_SYMBOL} انتهى الوقت المحدد للأمر.")
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **خطأ:** `{e}`")


@Client.on_message(filters.command("stats") & filters.user(cfg.OWNER_ID))
async def server_stats(client: Client, message: Message):
    """معلومات الخادم"""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    bot_info = await client.get_me()
    active = get_active_chats()
    redis_ok = redis_ping()

    await message.reply(
        f"「 معلومات السيرفر 」\n\n"
        f"🤖 البوت: **{bot_info.first_name}**\n"
        f"📊 المجموعات النشطة: **{len(active)}**\n"
        f"🟢 Redis: **{'متصل' if redis_ok else '❌ غير متصل'}**\n\n"
        f"💻 CPU: **{cpu}%**\n"
        f"🧠 RAM: **{ram.percent}%** ({ram.used // 1024**2}/{ram.total // 1024**2} MB)\n"
        f"💾 Disk: **{disk.percent}%** ({disk.used // 1024**3}/{disk.total // 1024**3} GB)"
    )


@Client.on_message(filters.command("broadcast") & filters.user(cfg.OWNER_ID))
async def broadcast(client: Client, message: Message):
    """بث رسالة لجميع المجموعات"""
    text = message.text.split(None, 1)
    if len(text) < 2:
        return await message.reply(f"{cfg.BOT_SYMBOL} أرسل النص بعد الأمر.")

    broadcast_text = text[1]
    chats = get_active_chats()
    sent, failed = 0, 0

    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري البث لـ **{len(chats)}** مجموعة...")

    for chat_id in chats:
        try:
            await client.send_message(chat_id, f"「 إشعار من الإدارة 」\n\n{broadcast_text}")
            sent += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1

    await msg.edit(
        f"{cfg.BOT_SYMBOL} اكتمل البث!\n"
        f"✅ أُرسل لـ **{sent}** مجموعة\n"
        f"❌ فشل في **{failed}** مجموعة"
    )


@Client.on_message(filters.command("dbstats") & filters.user(cfg.OWNER_ID))
async def db_stats(client: Client, message: Message):
    """إحصائيات قاعدة البيانات"""
    info = rdb.info()
    keys_count = rdb.dbsize()
    memory_used = info.get("used_memory_human", "N/A")
    uptime = info.get("uptime_in_seconds", 0)

    hours = uptime // 3600
    minutes = (uptime % 3600) // 60

    await message.reply(
        f"「 إحصائيات Redis 」\n\n"
        f"🔑 المفاتيح: **{keys_count:,}**\n"
        f"💾 الذاكرة: **{memory_used}**\n"
        f"⏱ وقت التشغيل: **{hours}س {minutes}د**\n"
        f"📌 الإصدار: **{info.get('redis_version', 'N/A')}**"
    )


@Client.on_message(filters.command("flushchat") & filters.user(cfg.OWNER_ID))
async def flush_chat(client: Client, message: Message):
    """مسح بيانات مجموعة معينة"""
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply(f"{cfg.BOT_SYMBOL} أرسل ID المجموعة بعد الأمر.")

    try:
        chat_id = int(parts[1])
    except ValueError:
        return await message.reply(f"{cfg.BOT_SYMBOL} ID غير صالح.")

    pattern = f"raad:{cfg.BOT_ID}:chat:{chat_id}:*"
    keys = rdb.keys(pattern)
    if keys:
        rdb.delete(*keys)

    await message.reply(
        f"{cfg.BOT_SYMBOL} تم حذف **{len(keys)}** مفتاح لمجموعة `{chat_id}` ✓"
    )


@Client.on_message(prefix_filter("الاوامر السرية"))
async def owner_commands(client: Client, message: Message):
    await message.reply(
        f"「 أوامر المالك الحصرية 」\n\n"
        f"/eval [كود] — تنفيذ Python\n"
        f"/sh [أمر] — تنفيذ شيل\n"
        f"/stats — معلومات الخادم\n"
        f"/broadcast [نص] — بث للمجموعات\n"
        f"/dbstats — إحصائيات Redis\n"
        f"/flushchat [id] — مسح بيانات مجموعة"
    )
