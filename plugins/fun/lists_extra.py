import json
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import build_mention, resolve_user
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


EXTRA_LISTS = {
    "كيك":    {"display": "الكيك",    "plural": "قائمة الكيك"},
    "عسل":    {"display": "العسل",    "plural": "قائمة العسل"},
    "نصاب":   {"display": "النصابين", "plural": "قائمة النصابين"},
}


def _get(chat_id: int, key: str) -> list[dict]:
    raw = rdb.get(chat_key(chat_id, f"xlist_{key}"))
    return json.loads(raw) if raw else []


def _save(chat_id: int, key: str, data: list[dict]):
    rdb.set(chat_key(chat_id, f"xlist_{key}"), json.dumps(data, ensure_ascii=False))


def _add(chat_id: int, key: str, user_id: int, name: str) -> bool:
    lst = _get(chat_id, key)
    if not any(e["id"] == user_id for e in lst):
        lst.append({"id": user_id, "name": name})
        _save(chat_id, key, lst)
        return True
    return False


def _remove(chat_id: int, key: str, user_id: int) -> bool:
    lst = _get(chat_id, key)
    new = [e for e in lst if e["id"] != user_id]
    if len(new) < len(lst):
        _save(chat_id, key, new)
        return True
    return False


def _build_text(chat_id: int, key: str) -> str:
    info = EXTRA_LISTS[key]
    lst = _get(chat_id, key)
    if not lst:
        return f"{cfg.BOT_SYMBOL} **{info['plural']}** فارغة."
    lines = [f"「 {info['plural']} 」\n"]
    for i, e in enumerate(lst, 1):
        lines.append(f"{i}. [{e['name']}](tg://user?id={e['id']})")
    return "\n".join(lines)


async def _resolve_target(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    from helpers.utils import extract_user_and_reason
    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return None
    return await resolve_user(client, user_id)


# ─── رفع ───────────────────────────────────────────────────────────
@Client.on_message(prefix_filter(r"رفع\s+(كيك|عسل|نصاب)"))
async def xlist_add(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(r"رفع\s+(كيك|عسل|نصاب)", message.text)
    if not m:
        return
    key = m.group(1)

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    target = await _resolve_target(client, message)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    added = _add(message.chat.id, key, target.id, target.first_name)
    display = EXTRA_LISTS[key]["display"]
    if added:
        await message.reply(f"{cfg.BOT_SYMBOL} تم رفع {build_mention(target)} لقائمة **{display}** ✓")
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} موجود بالفعل في القائمة.")


# ─── تنزيل ─────────────────────────────────────────────────────────
@Client.on_message(prefix_filter(r"تنزيل\s+(كيك|عسل|نصاب)"))
async def xlist_remove(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(r"تنزيل\s+(كيك|عسل|نصاب)", message.text)
    if not m:
        return
    key = m.group(1)

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    target = await _resolve_target(client, message)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    removed = _remove(message.chat.id, key, target.id)
    display = EXTRA_LISTS[key]["display"]
    if removed:
        await message.reply(f"{cfg.BOT_SYMBOL} تم تنزيل {build_mention(target)} من قائمة **{display}** ✓")
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} مو موجود في القائمة.")


# ─── عرض ───────────────────────────────────────────────────────────
@Client.on_message(prefix_filter(r"قائمة\s+(الكيك|العسل|النصابين)"))
async def xlist_show(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(r"قائمة\s+(الكيك|العسل|النصابين)", message.text)
    if not m:
        return
    display_name = m.group(1)
    key = {"الكيك": "كيك", "العسل": "عسل", "النصابين": "نصاب"}.get(display_name)
    if not key:
        return
    await message.reply(_build_text(message.chat.id, key))


# ─── مسح ───────────────────────────────────────────────────────────
@Client.on_message(prefix_filter(r"مسح قائمة\s+(الكيك|العسل|النصابين)"))
async def xlist_clear(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    m = re.search(r"مسح قائمة\s+(الكيك|العسل|النصابين)", message.text)
    if not m:
        return
    display_name = m.group(1)
    key = {"الكيك": "كيك", "العسل": "عسل", "النصابين": "نصاب"}.get(display_name)
    if not key:
        return
    _save(message.chat.id, key, [])
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح **{EXTRA_LISTS[key]['plural']}** ✓")
