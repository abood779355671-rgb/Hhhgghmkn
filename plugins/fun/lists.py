import json
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import build_mention, resolve_user
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


LIST_NAMES = [
    "كيك", "حمار", "كلب", "قرد", "تيس", "ثور",
    "هكر", "دجاجة", "خروف", "صياد", "بقرة", "مجنون",
    "نجم", "بطل", "أسد", "ذكاء",
]


def get_list(chat_id: int, list_name: str) -> list[dict]:
    raw = rdb.get(chat_key(chat_id, f"list_{list_name}"))
    return json.loads(raw) if raw else []


def save_list(chat_id: int, list_name: str, data: list[dict]):
    rdb.set(chat_key(chat_id, f"list_{list_name}"), json.dumps(data, ensure_ascii=False))


def add_to_list(chat_id: int, list_name: str, user_id: int, user_name: str):
    lst = get_list(chat_id, list_name)
    if not any(e["id"] == user_id for e in lst):
        lst.append({"id": user_id, "name": user_name})
        save_list(chat_id, list_name, lst)
        return True
    return False


def remove_from_list(chat_id: int, list_name: str, user_id: int) -> bool:
    lst = get_list(chat_id, list_name)
    new_lst = [e for e in lst if e["id"] != user_id]
    if len(new_lst) < len(lst):
        save_list(chat_id, list_name, new_lst)
        return True
    return False


def build_list_text(chat_id: int, list_name: str) -> str:
    lst = get_list(chat_id, list_name)
    if not lst:
        return f"{cfg.BOT_SYMBOL} قائمة **{list_name}** فارغة."
    lines = [f"「 قائمة {list_name} 」\n"]
    for i, entry in enumerate(lst, 1):
        lines.append(f"{i}. [{entry['name']}](tg://user?id={entry['id']})")
    return "\n".join(lines)


@Client.on_message(prefix_filter(r"رفع\s+(\S+)"))
async def add_to_fun_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    import re
    m = re.search(r"رفع\s+(\S+)", message.text)
    if not m:
        return
    list_name = m.group(1).strip()

    if list_name not in LIST_NAMES:
        return

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        user_id, _ = __import__("helpers.utils", fromlist=["extract_user_and_reason"]).extract_user_and_reason(message)
        if not user_id:
            return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")
        target = await resolve_user(client, user_id)
        if not target:
            return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    added = add_to_list(message.chat.id, list_name, target.id, target.first_name)
    if added:
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم إضافة {build_mention(target)} لقائمة **{list_name}** ✓"
        )
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} موجود بالفعل في القائمة.")


@Client.on_message(prefix_filter(r"تنزيل\s+(\S+)"))
async def remove_from_fun_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    import re
    m = re.search(r"تنزيل\s+(\S+)", message.text)
    if not m:
        return
    list_name = m.group(1).strip()

    if list_name not in LIST_NAMES:
        return

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        from helpers.utils import extract_user_and_reason
        user_id, _ = extract_user_and_reason(message)
        if not user_id:
            return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")
        target = await resolve_user(client, user_id)
        if not target:
            return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    removed = remove_from_list(message.chat.id, list_name, target.id)
    if removed:
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم إزالة {build_mention(target)} من قائمة **{list_name}** ✓"
        )
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} مو موجود في القائمة.")


@Client.on_message(prefix_filter(r"قائمة\s+(\S+)"))
async def show_fun_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    import re
    m = re.search(r"قائمة\s+(\S+)", message.text)
    if not m:
        return
    list_name = m.group(1).strip()

    if list_name not in LIST_NAMES:
        available = "، ".join(LIST_NAMES)
        return await message.reply(
            f"{cfg.BOT_SYMBOL} قائمة غير معروفة.\nالقوائم المتاحة: {available}"
        )

    await message.reply(build_list_text(message.chat.id, list_name))


@Client.on_message(prefix_filter(r"مسح قائمة\s+(\S+)"))
async def clear_fun_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    import re
    m = re.search(r"مسح قائمة\s+(\S+)", message.text)
    if not m:
        return
    list_name = m.group(1).strip()

    if list_name not in LIST_NAMES:
        return await message.reply(f"{cfg.BOT_SYMBOL} قائمة غير معروفة.")

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    save_list(message.chat.id, list_name, [])
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح قائمة **{list_name}** ✓")


@Client.on_message(prefix_filter("القوائم"))
async def all_lists(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    lines = [f"{cfg.BOT_SYMBOL} **القوائم المتاحة:**\n"]
    for name in LIST_NAMES:
        count = len(get_list(message.chat.id, name))
        lines.append(f"• **{name}** ({count} عضو)")
    await message.reply("\n".join(lines))
