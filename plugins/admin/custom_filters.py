import json
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


def _get_filter(chat_id: int, keyword: str) -> dict | None:
    raw = rdb.get(chat_key(chat_id, "filter", keyword))
    return json.loads(raw) if raw else None


def _set_filter(chat_id: int, keyword: str, data: dict):
    rdb.set(chat_key(chat_id, "filter", keyword), json.dumps(data, ensure_ascii=False))
    rdb.sadd(chat_key(chat_id, "filter_list"), keyword)


def _del_filter(chat_id: int, keyword: str):
    rdb.delete(chat_key(chat_id, "filter", keyword))
    rdb.srem(chat_key(chat_id, "filter_list"), keyword)


def _get_all_filters(chat_id: int) -> list[str]:
    return list(rdb.smembers(chat_key(chat_id, "filter_list")))


@Client.on_message(prefix_filter(r"اضف رد\s+(\S+)"), group=1)
async def add_filter(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    m = re.search(rf"^{cfg.BOT_PREFIX}\s+اضف رد\s+(\S+)", message.text)
    if not m:
        return
    keyword = m.group(1).strip()

    if not message.reply_to_message:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} **ردّ على الرسالة التي تريد إرسالها عند ذكر الكلمة `{keyword}`.**"
        )

    reply = message.reply_to_message
    data: dict = {}

    if reply.text:
        data = {"type": "text", "text": reply.text}
    elif reply.photo:
        data = {"type": "photo", "file_id": reply.photo.file_id, "caption": reply.caption or ""}
    elif reply.video:
        data = {"type": "video", "file_id": reply.video.file_id, "caption": reply.caption or ""}
    elif reply.sticker:
        data = {"type": "sticker", "file_id": reply.sticker.file_id}
    elif reply.audio:
        data = {"type": "audio", "file_id": reply.audio.file_id, "caption": reply.caption or ""}
    elif reply.voice:
        data = {"type": "voice", "file_id": reply.voice.file_id, "caption": reply.caption or ""}
    elif reply.document:
        data = {"type": "document", "file_id": reply.document.file_id, "caption": reply.caption or ""}
    else:
        return await message.reply(f"{cfg.BOT_SYMBOL} **نوع الرسالة غير مدعوم.**")

    _set_filter(message.chat.id, keyword, data)
    await message.reply(f"{cfg.BOT_SYMBOL} تم إضافة الرد على كلمة **{keyword}** ✓")


@Client.on_message(prefix_filter(r"مسح رد\s+(\S+)"), group=1)
async def del_filter(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    m = re.search(rf"^{cfg.BOT_PREFIX}\s+مسح رد\s+(\S+)", message.text)
    if not m:
        return
    keyword = m.group(1).strip()
    _del_filter(message.chat.id, keyword)
    await message.reply(f"{cfg.BOT_SYMBOL} تم حذف الرد على كلمة **{keyword}** ✓")


@Client.on_message(prefix_filter("الردود"), group=1)
async def list_filters(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    keywords = _get_all_filters(message.chat.id)
    if not keywords:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد ردود تلقائية في هذه المجموعة.**")
    lines = [f"{cfg.BOT_SYMBOL} **الردود التلقائية ({len(keywords)}):**\n"]
    for i, kw in enumerate(sorted(keywords), 1):
        d = _get_filter(message.chat.id, kw)
        t = d.get("type", "؟") if d else "؟"
        lines.append(f"{i}. `{kw}` — {t}")
    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("مسح الردود"), group=1)
async def clear_filters(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    keywords = _get_all_filters(message.chat.id)
    for kw in keywords:
        _del_filter(message.chat.id, kw)
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح **{len(keywords)}** رد تلقائي ✓")


async def _send_filter_response(client: Client, chat_id: int, data: dict, reply_to_id: int = None):
    kwargs = {"reply_to_message_id": reply_to_id} if reply_to_id else {}
    t = data.get("type")
    try:
        if t == "text":
            await client.send_message(chat_id, data["text"], **kwargs)
        elif t == "photo":
            await client.send_photo(chat_id, data["file_id"], caption=data.get("caption", ""), **kwargs)
        elif t == "video":
            await client.send_video(chat_id, data["file_id"], caption=data.get("caption", ""), **kwargs)
        elif t == "sticker":
            await client.send_sticker(chat_id, data["file_id"], **kwargs)
        elif t == "audio":
            await client.send_audio(chat_id, data["file_id"], caption=data.get("caption", ""), **kwargs)
        elif t == "voice":
            await client.send_voice(chat_id, data["file_id"], caption=data.get("caption", ""), **kwargs)
        elif t == "document":
            await client.send_document(chat_id, data["file_id"], caption=data.get("caption", ""), **kwargs)
    except Exception:
        pass


@Client.on_message(filters.group & filters.text, group=20)
async def check_local_filters(client: Client, message: Message):
    if not message.text or not message.from_user:
        return
    if not is_chat_active(message.chat.id):
        return

    text = message.text.strip().lower()
    chat_id = message.chat.id

    keywords = _get_all_filters(chat_id)
    for kw in keywords:
        if kw.lower() in text:
            data = _get_filter(chat_id, kw)
            if data:
                await _send_filter_response(client, chat_id, data, message.id)
                return
