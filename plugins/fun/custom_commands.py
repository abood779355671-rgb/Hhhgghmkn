import re
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from database.redis_client import rdb, chat_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


def _get_local_cmd(chat_id: int, cmd_name: str) -> str | None:
    return rdb.get(chat_key(chat_id, "custom_cmd", cmd_name))


def _set_local_cmd(chat_id: int, cmd_name: str, reply: str):
    rdb.set(chat_key(chat_id, "custom_cmd", cmd_name), reply)
    rdb.sadd(chat_key(chat_id, "custom_cmd_list"), cmd_name)


def _del_local_cmd(chat_id: int, cmd_name: str):
    rdb.delete(chat_key(chat_id, "custom_cmd", cmd_name))
    rdb.srem(chat_key(chat_id, "custom_cmd_list"), cmd_name)


def _get_all_local_cmds(chat_id: int) -> list[str]:
    return list(rdb.smembers(chat_key(chat_id, "custom_cmd_list")))


def _get_global_cmd(cmd_name: str) -> str | None:
    return rdb.get(global_key("custom_cmd", cmd_name))


def _set_global_cmd(cmd_name: str, reply: str):
    rdb.set(global_key("custom_cmd", cmd_name), reply)
    rdb.sadd(global_key("custom_cmd_list"), cmd_name)


def _del_global_cmd(cmd_name: str):
    rdb.delete(global_key("custom_cmd", cmd_name))
    rdb.srem(global_key("custom_cmd_list"), cmd_name)


def _get_all_global_cmds() -> list[str]:
    return list(rdb.smembers(global_key("custom_cmd_list")))


@Client.on_message(prefix_filter(r"اضف امر عام"), group=1)
async def add_global_cmd(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية. يحتاج رتبة مطور.**")

    rdb.set(f"add_global_cmd_step:{message.from_user.id}", "wait_cmd_name", ex=120)
    await message.reply(f"{cfg.BOT_SYMBOL} **أرسل اسم الأمر العام الجديد:**")


@Client.on_message(prefix_filter(r"مسح امر عام"), group=1)
async def del_global_cmd_cmd(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    rdb.set(f"del_global_cmd_step:{message.from_user.id}", "wait_cmd_name", ex=120)
    await message.reply(f"{cfg.BOT_SYMBOL} **أرسل اسم الأمر العام الذي تريد حذفه:**")


@Client.on_message(prefix_filter("الاوامر العامة"), group=1)
async def list_global_cmds(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    cmds = _get_all_global_cmds()
    if not cmds:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد أوامر عامة مضافة.**")
    lines = [f"{cfg.BOT_SYMBOL} **الأوامر العامة ({len(cmds)}):**\n"]
    for i, cmd in enumerate(sorted(cmds), 1):
        lines.append(f"{i}. `{cmd}`")
    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter(r"اضف امر"), group=1)
async def add_local_cmd(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_OWNER:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية. يحتاج المالك.**")

    rdb.set(f"add_local_cmd_step:{message.from_user.id}:{message.chat.id}", "wait_cmd_name", ex=120)
    await message.reply(f"{cfg.BOT_SYMBOL} **أرسل اسم الأمر الجديد:**")


@Client.on_message(prefix_filter(r"مسح امر"), group=1)
async def del_local_cmd_cmd(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_OWNER:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    rdb.set(f"del_local_cmd_step:{message.from_user.id}:{message.chat.id}", "wait_cmd_name", ex=120)
    await message.reply(f"{cfg.BOT_SYMBOL} **أرسل اسم الأمر الذي تريد حذفه:**")


@Client.on_message(prefix_filter("الاوامر المضافة"), group=1)
async def list_local_cmds(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    cmds = _get_all_local_cmds(message.chat.id)
    if not cmds:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد أوامر مخصصة في هذه المجموعة.**")
    lines = [f"{cfg.BOT_SYMBOL} **الأوامر المضافة ({len(cmds)}):**\n"]
    for i, cmd in enumerate(sorted(cmds), 1):
        lines.append(f"{i}. `{cmd}`")
    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("مسح الاوامر"), group=1)
async def clear_local_cmds(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    cmds = _get_all_local_cmds(message.chat.id)
    for cmd in cmds:
        _del_local_cmd(message.chat.id, cmd)
    await message.reply(f"{cfg.BOT_SYMBOL} تم مسح **{len(cmds)}** أمر مخصص ✓")


@Client.on_message(filters.group & filters.text, group=-1)
async def handle_custom_cmds(client: Client, message: Message):
    if not message.text or not message.from_user:
        return

    chat_id = message.chat.id
    text = message.text.strip()
    user_id = message.from_user.id

    step_local = rdb.get(f"add_local_cmd_step:{user_id}:{chat_id}")
    if step_local == "wait_cmd_name":
        rdb.set(f"add_local_cmd_name:{user_id}:{chat_id}", text, ex=120)
        rdb.set(f"add_local_cmd_step:{user_id}:{chat_id}", "wait_reply", ex=120)
        return await message.reply(f"{cfg.BOT_SYMBOL} **الآن أرسل الرد الذي سيظهر عند كتابة هذا الأمر:**")

    if step_local == "wait_reply":
        cmd_name = rdb.get(f"add_local_cmd_name:{user_id}:{chat_id}")
        if not cmd_name:
            return
        _set_local_cmd(chat_id, cmd_name, text)
        rdb.delete(f"add_local_cmd_step:{user_id}:{chat_id}")
        rdb.delete(f"add_local_cmd_name:{user_id}:{chat_id}")
        return await message.reply(f"{cfg.BOT_SYMBOL} تم إضافة الأمر `{cmd_name}` ✓")

    step_del_local = rdb.get(f"del_local_cmd_step:{user_id}:{chat_id}")
    if step_del_local == "wait_cmd_name":
        _del_local_cmd(chat_id, text)
        rdb.delete(f"del_local_cmd_step:{user_id}:{chat_id}")
        return await message.reply(f"{cfg.BOT_SYMBOL} تم حذف الأمر `{text}` ✓")

    step_global = rdb.get(f"add_global_cmd_step:{user_id}")
    if step_global == "wait_cmd_name":
        rdb.set(f"add_global_cmd_name:{user_id}", text, ex=120)
        rdb.set(f"add_global_cmd_step:{user_id}", "wait_reply", ex=120)
        return await message.reply(f"{cfg.BOT_SYMBOL} **الآن أرسل رد الأمر العام:**")

    if step_global == "wait_reply":
        cmd_name = rdb.get(f"add_global_cmd_name:{user_id}")
        if not cmd_name:
            return
        _set_global_cmd(cmd_name, text)
        rdb.delete(f"add_global_cmd_step:{user_id}")
        rdb.delete(f"add_global_cmd_name:{user_id}")
        return await message.reply(f"{cfg.BOT_SYMBOL} تم إضافة الأمر العام `{cmd_name}` ✓")

    step_del_global = rdb.get(f"del_global_cmd_step:{user_id}")
    if step_del_global == "wait_cmd_name":
        _del_global_cmd(text)
        rdb.delete(f"del_global_cmd_step:{user_id}")
        return await message.reply(f"{cfg.BOT_SYMBOL} تم حذف الأمر العام `{text}` ✓")

    if not is_chat_active(chat_id):
        return

    global_reply = _get_global_cmd(text)
    if global_reply:
        return await message.reply(global_reply)

    local_reply = _get_local_cmd(chat_id, text)
    if local_reply:
        return await message.reply(local_reply)
