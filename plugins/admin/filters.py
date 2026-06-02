import json
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import safe_delete
from database.redis_client import rdb, chat_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


def get_filters(chat_id: int) -> dict:
    raw = rdb.get(chat_key(chat_id, "filters"))
    return json.loads(raw) if raw else {}


def save_filters(chat_id: int, data: dict):
    rdb.set(chat_key(chat_id, "filters"), json.dumps(data, ensure_ascii=False))


def get_global_filters() -> dict:
    raw = rdb.get(global_key("filters"))
    return json.loads(raw) if raw else {}


def save_global_filters(data: dict):
    rdb.set(global_key("filters"), json.dumps(data, ensure_ascii=False))


def get_commands(chat_id: int) -> dict:
    raw = rdb.get(chat_key(chat_id, "commands"))
    return json.loads(raw) if raw else {}


def save_commands(chat_id: int, data: dict):
    rdb.set(chat_key(chat_id, "commands"), json.dumps(data, ensure_ascii=False))


@Client.on_message(prefix_filter(r"اضف رد\s+(.+)"))
async def add_filter(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    if not message.reply_to_message:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} **ردّ على الرسالة التي تريد إرسالها عند تفعيل الرد.**"
        )

    import re
    m = re.search(r"اضف رد\s+(.+)", message.text)
    if not m:
        return
    keyword = m.group(1).strip().lower()

    reply_msg = message.reply_to_message
    response = {
        "type": "text",
        "content": reply_msg.text or reply_msg.caption or "",
        "file_id": None,
    }

    if reply_msg.sticker:
        response["type"] = "sticker"
        response["file_id"] = reply_msg.sticker.file_id
    elif reply_msg.photo:
        response["type"] = "photo"
        response["file_id"] = reply_msg.photo.file_id
        response["content"] = reply_msg.caption or ""
    elif reply_msg.video:
        response["type"] = "video"
        response["file_id"] = reply_msg.video.file_id
        response["content"] = reply_msg.caption or ""
    elif reply_msg.document:
        response["type"] = "document"
        response["file_id"] = reply_msg.document.file_id
        response["content"] = reply_msg.caption or ""

    local_filters = get_filters(message.chat.id)
    if keyword not in local_filters:
        local_filters[keyword] = []
    local_filters[keyword].append(response)
    save_filters(message.chat.id, local_filters)

    await message.reply(
        f"{cfg.BOT_SYMBOL} تم إضافة رد تلقائي على كلمة **\"{keyword}\"** ✓"
    )


@Client.on_message(prefix_filter(r"اضف رد عام\s+(.+)"))
async def add_global_filter(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **هذا الأمر للمطورين فقط.**")

    if not message.reply_to_message:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على الرسالة أولاً.**")

    import re
    m = re.search(r"اضف رد عام\s+(.+)", message.text)
    if not m:
        return
    keyword = m.group(1).strip().lower()

    reply_msg = message.reply_to_message
    response = {
        "type": "text",
        "content": reply_msg.text or reply_msg.caption or "",
        "file_id": None,
    }

    gf = get_global_filters()
    if keyword not in gf:
        gf[keyword] = []
    gf[keyword].append(response)
    save_global_filters(gf)

    await message.reply(
        f"{cfg.BOT_SYMBOL} تم إضافة رد **عام** على كلمة **\"{keyword}\"** ✓"
    )


@Client.on_message(prefix_filter(r"حذف رد\s+(.+)"))
async def delete_filter(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    import re
    m = re.search(r"حذف رد\s+(.+)", message.text)
    if not m:
        return
    keyword = m.group(1).strip().lower()

    local_filters = get_filters(message.chat.id)
    if keyword in local_filters:
        del local_filters[keyword]
        save_filters(message.chat.id, local_filters)
        await message.reply(f"{cfg.BOT_SYMBOL} تم حذف رد **\"{keyword}\"** ✓")
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} ما فيه رد باسم **\"{keyword}\"**.")


@Client.on_message(prefix_filter("الردود"))
async def list_filters(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    local_filters = get_filters(message.chat.id)
    gf = get_global_filters()

    if not local_filters and not gf:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد ردود تلقائية.**")

    text = f"{cfg.BOT_SYMBOL} **الردود التلقائية:**\n\n"
    if local_filters:
        text += "**محلية:**\n"
        for kw in local_filters:
            count = len(local_filters[kw])
            text += f"• `{kw}` — {count} رد\n"
    if gf:
        text += "\n**عامة:**\n"
        for kw in gf:
            count = len(gf[kw])
            text += f"• `{kw}` — {count} رد\n"

    await message.reply(text)


@Client.on_message(prefix_filter(r"اضف امر\s+(\S+)\s+(.+)"))
async def add_command(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    import re
    m = re.search(r"اضف امر\s+(\S+)\s+(.+)", message.text, re.DOTALL)
    if not m:
        return
    cmd_name = m.group(1).strip().lower()
    cmd_response = m.group(2).strip()

    cmds = get_commands(message.chat.id)
    cmds[cmd_name] = {"type": "text", "content": cmd_response}
    save_commands(message.chat.id, cmds)

    await message.reply(
        f"{cfg.BOT_SYMBOL} تم إضافة الأمر **\"{cmd_name}\"** ✓\n"
        f"الاستخدام: `{cfg.BOT_PREFIX} {cmd_name}`"
    )


@Client.on_message(filters.group & filters.text)
async def handle_filters_and_commands(client: Client, message: Message):
    if not message.from_user or not is_chat_active(message.chat.id):
        return
    if not message.text:
        return

    text_lower = message.text.lower().strip()
    chat_id = message.chat.id

    import re
    cmd_prefix = cfg.BOT_PREFIX.lower()
    cmd_match = re.match(rf"^{re.escape(cmd_prefix)}\s+(\S+)", text_lower)
    if cmd_match:
        cmd_name = cmd_match.group(1)
        cmds = get_commands(chat_id)
        if cmd_name in cmds:
            resp = cmds[cmd_name]
            if resp["type"] == "text":
                await message.reply(resp["content"])
            return

    local_filters = get_filters(chat_id)
    gf = get_global_filters()

    for keyword, responses in {**gf, **local_filters}.items():
        if keyword in text_lower:
            resp = random.choice(responses)
            try:
                if resp["type"] == "text":
                    await message.reply(resp["content"])
                elif resp["type"] == "sticker":
                    await message.reply_sticker(resp["file_id"])
                elif resp["type"] == "photo":
                    await message.reply_photo(resp["file_id"], caption=resp.get("content", ""))
                elif resp["type"] == "video":
                    await message.reply_video(resp["file_id"], caption=resp.get("content", ""))
                elif resp["type"] == "document":
                    await message.reply_document(resp["file_id"], caption=resp.get("content", ""))
            except Exception:
                pass
            break
