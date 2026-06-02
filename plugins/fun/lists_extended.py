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


EXTENDED_LISTS = {
    "ملكه": "قائمة الملكات",
    "صياد": "قائمة الصيادين",
    "خروف": "قائمة الخرفان",
    "تيس": "قائمة التيوس",
    "ثور": "قائمة الثيران",
    "دجاجة": "قائمة الدجاج",
    "بقرة": "قائمة البقر",
    "هكر": "قائمة الهكر",
}

LIST_DISPLAY_NAMES = {
    "ملكه": "الملكات",
    "صياد": "الصيادين",
    "خروف": "الخرفان",
    "تيس": "التيوس",
    "ثور": "الثيران",
    "دجاجة": "الدجاج",
    "بقرة": "البقر",
    "هكر": "الهكر",
}


def get_ext_list(chat_id: int, key: str) -> list[dict]:
    raw = rdb.get(chat_key(chat_id, f"ext_list_{key}"))
    return json.loads(raw) if raw else []


def save_ext_list(chat_id: int, key: str, data: list[dict]):
    rdb.set(chat_key(chat_id, f"ext_list_{key}"), json.dumps(data, ensure_ascii=False))


def add_to_ext_list(chat_id: int, key: str, user_id: int, user_name: str) -> bool:
    lst = get_ext_list(chat_id, key)
    if not any(e["id"] == user_id for e in lst):
        lst.append({"id": user_id, "name": user_name})
        save_ext_list(chat_id, key, lst)
        return True
    return False


def remove_from_ext_list(chat_id: int, key: str, user_id: int) -> bool:
    lst = get_ext_list(chat_id, key)
    new_lst = [e for e in lst if e["id"] != user_id]
    if len(new_lst) < len(lst):
        save_ext_list(chat_id, key, new_lst)
        return True
    return False


def build_ext_list_text(chat_id: int, key: str) -> str:
    display = LIST_DISPLAY_NAMES.get(key, key)
    lst = get_ext_list(chat_id, key)
    if not lst:
        return f"{cfg.BOT_SYMBOL} قائمة **{display}** فارغة."
    lines = [f"「 قائمة {display} 」\n"]
    for i, entry in enumerate(lst, 1):
        lines.append(f"{i}. [{entry['name']}](tg://user?id={entry['id']})")
    return "\n".join(lines)


async def get_target(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    from helpers.utils import extract_user_and_reason
    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return None
    return await resolve_user(client, user_id)


ADD_PATTERN = r"رفع\s+(" + "|".join(EXTENDED_LISTS.keys()) + r")"
REMOVE_PATTERN = r"تنزيل\s+(" + "|".join(EXTENDED_LISTS.keys()) + r")"
SHOW_PATTERN = r"قائمة\s+(" + "|".join(LIST_DISPLAY_NAMES.values()) + r")"
CLEAR_PATTERN = r"مسح قائمة\s+(" + "|".join(LIST_DISPLAY_NAMES.values()) + r")"

KEY_BY_DISPLAY = {v: k for k, v in LIST_DISPLAY_NAMES.items()}


@Client.on_message(prefix_filter(ADD_PATTERN))
async def add_ext_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(ADD_PATTERN, message.text)
    if not m:
        return
    key = m.group(1).strip()
    if key not in EXTENDED_LISTS:
        return

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    target = await get_target(client, message)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    added = add_to_ext_list(message.chat.id, key, target.id, target.first_name)
    display = LIST_DISPLAY_NAMES[key]
    if added:
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم رفع {build_mention(target)} لقائمة **{display}** ✓"
        )
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} موجود بالفعل في القائمة.")


@Client.on_message(prefix_filter(REMOVE_PATTERN))
async def remove_ext_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(REMOVE_PATTERN, message.text)
    if not m:
        return
    key = m.group(1).strip()
    if key not in EXTENDED_LISTS:
        return

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    target = await get_target(client, message)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    removed = remove_from_ext_list(message.chat.id, key, target.id)
    display = LIST_DISPLAY_NAMES[key]
    if removed:
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم تنزيل {build_mention(target)} من قائمة **{display}** ✓"
        )
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} مو موجود في القائمة.")


@Client.on_message(prefix_filter(SHOW_PATTERN))
async def show_ext_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(SHOW_PATTERN, message.text)
    if not m:
        return
    display_name = m.group(1).strip()
    key = KEY_BY_DISPLAY.get(display_name)
    if not key:
        return
    await message.reply(build_ext_list_text(message.chat.id, key))


@Client.on_message(prefix_filter(CLEAR_PATTERN))
async def clear_ext_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    m = re.search(CLEAR_PATTERN, message.text)
    if not m:
        return
    display_name = m.group(1).strip()
    key = KEY_BY_DISPLAY.get(display_name)
    if not key:
        return

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    save_ext_list(message.chat.id, key, [])
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح قائمة **{display_name}** ✓")
