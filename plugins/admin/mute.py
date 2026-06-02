from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from config import cfg
from helpers.permissions import get_user_rank, can_act_on, is_chat_active, get_active_chats
from helpers.utils import extract_user_and_reason, resolve_user, build_mention, safe_delete
from database.redis_client import rdb, chat_key, user_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


NO_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

ALL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)


@Client.on_message(prefix_filter("كتم"))
async def local_mute(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, reason = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    target_rank = get_user_rank(target.id, message.chat.id)
    if not can_act_on(actor_rank, target_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تكتم شخص برتبة مساوية أو أعلى.**")

    try:
        await client.restrict_chat_member(message.chat.id, target.id, NO_PERMS)
        rdb.sadd(chat_key(message.chat.id, "muted"), str(target.id))
        reason_text = f"\n📌 السبب: {reason}" if reason else ""
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم كتم {build_mention(target)} في هذه المجموعة.{reason_text}"
        )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الكتم:** `{e}`")


@Client.on_message(prefix_filter("الغاء الكتم"))
async def local_unmute(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    try:
        await client.restrict_chat_member(message.chat.id, target.id, ALL_PERMS)
        rdb.srem(chat_key(message.chat.id, "muted"), str(target.id))
        await message.reply(f"{cfg.BOT_SYMBOL} تم رفع الكتم عن {build_mention(target)} ✓")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل رفع الكتم:** `{e}`")


@Client.on_message(prefix_filter("كتم عام"))
async def global_mute(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **هذا الأمر للمطورين فقط.**")

    user_id, reason = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    target_rank = get_user_rank(target.id)
    if not can_act_on(actor_rank, target_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تكتم هذا الشخص.**")

    rdb.sadd(global_key("gmuted"), str(target.id))
    chats = get_active_chats()
    failed = 0
    for chat_id in chats:
        try:
            await client.restrict_chat_member(chat_id, target.id, NO_PERMS)
            rdb.sadd(chat_key(chat_id, "muted"), str(target.id))
        except Exception:
            failed += 1

    reason_text = f"\n📌 السبب: {reason}" if reason else ""
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم الكتم العام لـ {build_mention(target)} في {len(chats) - failed} مجموعة.{reason_text}"
    )


@Client.on_message(prefix_filter("الغاء الكتم العام"))
async def global_unmute(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **هذا الأمر للمطورين فقط.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    rdb.srem(global_key("gmuted"), str(target.id))
    chats = get_active_chats()
    for chat_id in chats:
        try:
            await client.restrict_chat_member(chat_id, target.id, ALL_PERMS)
            rdb.srem(chat_key(chat_id, "muted"), str(target.id))
        except Exception:
            pass

    await message.reply(f"{cfg.BOT_SYMBOL} تم رفع الكتم العام عن {build_mention(target)} ✓")


@Client.on_message(prefix_filter("تقييد"))
async def restrict_user(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, reason = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    target_rank = get_user_rank(target.id, message.chat.id)
    if not can_act_on(actor_rank, target_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تقيّد هذا الشخص.**")

    read_only = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_other_messages=False,
    )
    try:
        await client.restrict_chat_member(message.chat.id, target.id, read_only)
        rdb.sadd(chat_key(message.chat.id, "restricted"), str(target.id))
        reason_text = f"\n📌 السبب: {reason}" if reason else ""
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم تقييد {build_mention(target)} — يبقى في المجموعة لكن لا يرسل.{reason_text}"
        )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل التقييد:** `{e}`")


@Client.on_message(prefix_filter("الغاء تقييد"))
async def unrestrict_user(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    try:
        await client.restrict_chat_member(message.chat.id, target.id, ALL_PERMS)
        rdb.srem(chat_key(message.chat.id, "restricted"), str(target.id))
        await message.reply(f"{cfg.BOT_SYMBOL} تم رفع التقييد عن {build_mention(target)} ✓")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل رفع التقييد:** `{e}`")


@Client.on_message(prefix_filter("المكتومين"))
async def list_muted(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    muted = rdb.smembers(chat_key(message.chat.id, "muted"))
    if not muted:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا يوجد مكتومون في هذه المجموعة.**")

    lines = [f"{cfg.BOT_SYMBOL} **قائمة المكتومين:**\n"]
    for uid in muted:
        try:
            u = await client.get_users(int(uid))
            lines.append(f"• [{u.first_name}](tg://user?id={uid}) — `{uid}`")
        except Exception:
            lines.append(f"• `{uid}`")
    await message.reply("\n".join(lines))


@Client.on_message(filters.group)
async def auto_delete_muted(client: Client, message: Message):
    if not message.from_user:
        return
    if not is_chat_active(message.chat.id):
        return

    user_id = str(message.from_user.id)
    is_gmuted = rdb.sismember(global_key("gmuted"), user_id)
    is_muted = rdb.sismember(chat_key(message.chat.id, "muted"), user_id)

    if is_gmuted or is_muted:
        await safe_delete(message)
