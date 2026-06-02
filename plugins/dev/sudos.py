import sys
import os
import html
import time
import asyncio
import traceback
import platform
import psutil
from io import StringIO
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from database.redis_client import rdb
from helpers.permissions import get_user_rank

try:
    from meval import meval
    MEVAL_OK = True
except ImportError:
    MEVAL_OK = False

try:
    from pytio import Tio, TioRequest
    tio = Tio()
    langslist = tio.query_languages()
    TIO_OK = True
except Exception:
    TIO_OK = False
    langslist = []

langs_list_link = "https://amanoteam.com/etc/langs.html"


def _is_dev(uid: int) -> bool:
    return get_user_rank(uid) <= cfg.RANK_DEV


def get_size(bytes_val: int, suffix: str = "B") -> str:
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes_val < factor:
            return f"{bytes_val:.2f}{unit}{suffix}"
        bytes_val /= factor


async def _aexec(code: str, client: Client, message: Message):
    exec(
        "async def __aexec(client, message): "
        + "".join(f"\n {line}" for line in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)


async def _shell_exec(cmd: str):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip()


def _owner_filter(_, __, m: Message) -> bool:
    if not m.from_user:
        return False
    uid = m.from_user.id
    rank = get_user_rank(uid)
    return rank <= cfg.RANK_DEV


owner_filter = filters.create(_owner_filter)


@Client.on_message(filters.command("eval") & filters.private & owner_filter)
async def executor(client: Client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply("» هات كود عشان انفذ!")

    cmd = message.text.split(None, 1)[1] if len(message.command) >= 2 else message.reply_to_message.text

    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None

    try:
        await _aexec(cmd, client, message)
    except Exception:
        exc = traceback.format_exc()

    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    if exc:
        evaluation = exc
    elif stderr:
        evaluation = stderr
    elif stdout:
        evaluation = stdout
    else:
        evaluation = "SUCCESS"

    final_output = f"`OUTPUT:`\n\n```{evaluation.strip()}```"
    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as f:
            f.write(str(evaluation.strip()))
        await message.reply_document(
            document=filename,
            caption=f"`INPUT:`\n`{cmd[0:980]}`\n\n`OUTPUT:`\n`attached document`",
            quote=False,
        )
        await message.delete()
        os.remove(filename)
    else:
        await message.reply(final_output)


@Client.on_message(filters.command("exec") & filters.private & owner_filter)
async def exec_tio(c: Client, m: Message):
    if not TIO_OK:
        return await m.reply("مكتبة pytio غير مثبتة.")
    if len(m.command) < 3:
        return await m.reply(f"الاستخدام: /exec <اللغة> <الكود>\nقائمة اللغات: {langs_list_link}")

    language = m.command[1]
    code = m.text.split(None, 2)[2]

    if language not in langslist:
        return await m.reply(
            f"اللغة <b>{html.escape(language)}</b> غير مدعومة.\nقائمة اللغات: {langs_list_link}",
            parse_mode="html"
        )

    tioreq = TioRequest(lang=language, code=code)
    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(None, tio.send, tioreq)

    result = resp.result or "None"
    error = resp.error or "None"
    stats = resp.debug.decode() if resp.debug else "None"

    if resp.error is None:
        text = (
            f"<b>Language:</b> <code>{html.escape(language)}</code>\n\n"
            f"<b>Code:</b>\n<code>{html.escape(code)}</code>\n\n"
            f"<b>Results:</b>\n<code>{html.escape(result)}</code>\n\n"
            f"<b>Stats:</b><code>{html.escape(stats)}</code>"
        )
    else:
        text = (
            f"<b>Language:</b> <code>{html.escape(language)}</code>\n\n"
            f"<b>Code:</b>\n<code>{html.escape(code)}</code>\n\n"
            f"<b>Results:</b>\n<code>{html.escape(result)}</code>\n\n"
            f"<b>Errors:</b>\n<code>{html.escape(error)}</code>"
        )
    await m.reply(text, parse_mode="html")


@Client.on_message(filters.command("cmd") & filters.private & owner_filter)
async def run_shell(c: Client, m: Message):
    if len(m.command) < 2:
        return await m.reply("الاستخدام: /cmd <الأمر>")
    cmd = m.text.split(None, 1)[1]
    import re
    if re.match(r"(?i)poweroff|halt|shutdown|reboot", cmd):
        return await m.reply("ممنوع استخدام هذا الأمر.")
    stdout, stderr = await _shell_exec(cmd)
    result = (
        f"<b>Output:</b>\n<code>{html.escape(stdout)}</code>" if stdout else ""
    ) + (
        f"\n<b>Errors:</b>\n<code>{html.escape(stderr)}</code>" if stderr else ""
    )
    await m.reply(result or "لا يوجد مخرجات.", parse_mode="html")


@Client.on_message(filters.command(["server", "سيرفر"]) & owner_filter)
async def server_info(c: Client, m: Message):
    k = cfg.BOT_SYMBOL
    uname = platform.uname()

    try:
        import distro
        os_ver = distro.name(pretty=True)
    except Exception:
        os_ver = uname.release

    svmem = psutil.virtual_memory()
    disk = psutil.disk_partitions()
    usage = psutil.disk_usage(disk[0].mountpoint) if disk else None
    uptime = time.strftime('%dD - %HH - %MM - %Ss', time.gmtime(time.time() - psutil.boot_time()))

    text = '——— SYSTEM INFO ———'
    text += f'\n{k} النظام : {uname.system}'
    text += f'\n{k} الاصدار: `{os_ver}`'
    text += '\n——— R.A.M INFO ———'
    text += f'\n{k} رامات السيرفر: `{get_size(svmem.total)}`'
    text += f'\n{k} المستهلك: `{get_size(svmem.used)}/{get_size(svmem.available)}`'
    text += f'\n{k} نسبة الاستهلاك: `{svmem.percent}%`'

    if usage:
        text += '\n——— HARD DISK ———'
        text += f'\n{k} ذاكرة التخزين: `{get_size(usage.total)}`'
        text += f'\n{k} المستهلك: `{get_size(usage.used)}`'
        text += f'\n{k} نسبة الاستهلاك: `{usage.percent}%`'

    text += '\n——— U.P T.I.M.E ———'
    text += f'\n{uptime}'
    text += f'\n\n{k}'

    await m.reply(text, disable_web_page_preview=True)
