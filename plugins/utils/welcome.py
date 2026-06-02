import json
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting, build_mention
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


def get_welcome_data(chat_id: int) -> dict:
    raw = rdb.get(chat_key(chat_id, "welcome"))
    return json.loads(raw) if raw else {"enabled": False, "message": "", "with_photo": False}


def save_welcome_data(chat_id: int, data: dict):
    rdb.set(chat_key(chat_id, "welcome"), json.dumps(data, ensure_ascii=False))


def get_rules(chat_id: int) -> str:
    return rdb.get(chat_key(chat_id, "rules")) or ""


def save_rules(chat_id: int, text: str):
    rdb.set(chat_key(chat_id, "rules"), text)


@Client.on_message(prefix_filter("تفعيل الترحيب"))
async def enable_welcome(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    data = get_welcome_data(message.chat.id)
    data["enabled"] = True
    save_welcome_data(message.chat.id, data)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل رسالة الترحيب** ✓")


@Client.on_message(prefix_filter("تعطيل الترحيب"))
async def disable_welcome(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    data = get_welcome_data(message.chat.id)
    data["enabled"] = False
    save_welcome_data(message.chat.id, data)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل رسالة الترحيب** ✓")


@Client.on_message(prefix_filter(r"رسالة الترحيب\s+(.+)"))
async def set_welcome(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    import re
    m = re.search(r"رسالة الترحيب\s+(.+)", message.text, re.DOTALL)
    if not m:
        return
    text = m.group(1).strip()

    data = get_welcome_data(message.chat.id)
    data["message"] = text
    save_welcome_data(message.chat.id, data)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم تعيين رسالة الترحيب ✓\n"
        f"يمكنك استخدام `{{name}}` لاسم العضو و `{{chat}}` لاسم المجموعة."
    )


@Client.on_message(prefix_filter("ترحيب بالصورة"))
async def welcome_with_photo(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    data = get_welcome_data(message.chat.id)
    data["with_photo"] = not data.get("with_photo", False)
    save_welcome_data(message.chat.id, data)
    status = "مفعّل" if data["with_photo"] else "معطّل"
    await message.reply(f"{cfg.BOT_SYMBOL} الترحيب بصورة العضو: **{status}**")


@Client.on_message(prefix_filter(r"القوانين\s*(.*)"))
async def handle_rules(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    import re
    m = re.search(r"القوانين\s*(.*)", message.text, re.DOTALL)
    content = (m.group(1) or "").strip() if m else ""

    if content:
        actor_rank = get_user_rank(message.from_user.id, message.chat.id)
        if actor_rank > cfg.RANK_ADMIN:
            return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية لتعيين القوانين.**")
        save_rules(message.chat.id, content)
        await message.reply(f"{cfg.BOT_SYMBOL} تم حفظ **قوانين المجموعة** ✓")
    else:
        rules = get_rules(message.chat.id)
        if not rules:
            return await message.reply(f"{cfg.BOT_SYMBOL} **لم يتم تعيين قوانين لهذه المجموعة بعد.**")
        await message.reply(
            f"「 قوانين {message.chat.title} 」\n\n{rules}"
        )


@Client.on_chat_member_updated()
async def send_welcome(client: Client, update: ChatMemberUpdated):
    if not update.new_chat_member:
        return
    if update.old_chat_member:
        old_status = update.old_chat_member.status.name
        new_status = update.new_chat_member.status.name
        if old_status != "LEFT" and old_status != "BANNED":
            return

    chat_id = update.chat.id
    if not is_chat_active(chat_id):
        return

    data = get_welcome_data(chat_id)
    if not data.get("enabled", False):
        return

    user = update.new_chat_member.user
    name = user.first_name or "مستخدم"
    chat = update.chat.title or "المجموعة"

    welcome_text = data.get("message") or (
        f"أهلاً وسهلاً بـ {build_mention(user)} في {chat}! 🎉\n"
        f"نورت يا {name}، يا هلا والله ☆"
    )
    welcome_text = welcome_text.replace("{name}", build_mention(user)).replace("{chat}", chat)

    try:
        if data.get("with_photo") and user.photo:
            photos = await client.get_profile_photos(user.id, limit=1)
            if photos.total_count > 0:
                await client.send_photo(
                    chat_id,
                    photos[0].file_id,
                    caption=welcome_text,
                )
                return
        await client.send_message(chat_id, welcome_text)
    except Exception:
        pass
