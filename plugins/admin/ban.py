from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from config import cfg
from helpers.permissions import get_user_rank, can_act_on, is_chat_active, get_active_chats
from helpers.utils import extract_user_and_reason, resolve_user, build_mention
from database.redis_client import rdb, chat_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


@Client.on_message(prefix_filter("حظر"))
async def local_ban(client: Client, message: Message):
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
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تحظر شخص برتبة مساوية أو أعلى.**")

    try:
        await client.ban_chat_member(message.chat.id, target.id)
        rdb.sadd(chat_key(message.chat.id, "banned"), str(target.id))
        reason_text = f"\n📌 السبب: {reason}" if reason else ""
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم حظر {build_mention(target)} من المجموعة.{reason_text}"
        )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الحظر:** `{e}`")


@Client.on_message(prefix_filter("رفع الحظر"))
async def local_unban(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **اذكر @يوزر أو ID المستخدم.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    try:
        await client.unban_chat_member(message.chat.id, target.id)
        rdb.srem(chat_key(message.chat.id, "banned"), str(target.id))
        await message.reply(f"{cfg.BOT_SYMBOL} تم رفع الحظر عن {build_mention(target)} ✓")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل رفع الحظر:** `{e}`")


@Client.on_message(prefix_filter("حظر عام"))
async def global_ban(client: Client, message: Message):
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
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تحظر هذا الشخص.**")

    rdb.sadd(global_key("gbanned"), str(target.id))
    if reason:
        rdb.set(global_key("gban_reason", target.id), reason)

    chats = get_active_chats()
    failed = 0
    for chat_id in chats:
        try:
            await client.ban_chat_member(chat_id, target.id)
            rdb.sadd(chat_key(chat_id, "banned"), str(target.id))
        except Exception:
            failed += 1

    reason_text = f"\n📌 السبب: {reason}" if reason else ""
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم الحظر العام لـ {build_mention(target)} من {len(chats) - failed} مجموعة.{reason_text}"
    )


@Client.on_message(prefix_filter("الغاء الحظر العام"))
async def global_unban(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **هذا الأمر للمطورين فقط.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **اذكر @يوزر أو ID المستخدم.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    rdb.srem(global_key("gbanned"), str(target.id))
    rdb.delete(global_key("gban_reason", target.id))

    chats = get_active_chats()
    for chat_id in chats:
        try:
            await client.unban_chat_member(chat_id, target.id)
            rdb.srem(chat_key(chat_id, "banned"), str(target.id))
        except Exception:
            pass

    await message.reply(f"{cfg.BOT_SYMBOL} تم رفع الحظر العام عن {build_mention(target)} ✓")


@Client.on_message(prefix_filter("طرد"))
async def kick_user(client: Client, message: Message):
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
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تطرد شخص برتبة مساوية أو أعلى.**")

    try:
        await client.ban_chat_member(message.chat.id, target.id)
        await client.unban_chat_member(message.chat.id, target.id)
        reason_text = f"\n📌 السبب: {reason}" if reason else ""
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم طرد {build_mention(target)} من المجموعة.{reason_text}"
        )
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل الطرد:** `{e}`")


@Client.on_message(prefix_filter("المحظورين"))
async def list_banned(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    banned = rdb.smembers(chat_key(message.chat.id, "banned"))
    if not banned:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا يوجد محظورون في هذه المجموعة.**")

    lines = [f"{cfg.BOT_SYMBOL} **قائمة المحظورين:**\n"]
    for uid in banned:
        try:
            u = await client.get_users(int(uid))
            lines.append(f"• [{u.first_name}](tg://user?id={uid}) — `{uid}`")
        except Exception:
            lines.append(f"• `{uid}`")
    await message.reply("\n".join(lines))


@Client.on_chat_member_updated()
async def auto_gban_on_join(client: Client, update: ChatMemberUpdated):
    """طرد المحظورين عاماً فور دخولهم"""
    if not update.new_chat_member:
        return
    if not is_chat_active(update.chat.id):
        return

    user = update.new_chat_member.user
    if rdb.sismember(global_key("gbanned"), str(user.id)):
        try:
            reason = rdb.get(global_key("gban_reason", user.id)) or "حظر عام"
            await client.ban_chat_member(update.chat.id, user.id)
            await client.send_message(
                update.chat.id,
                f"{cfg.BOT_SYMBOL} تم طرد {build_mention(user)} تلقائياً — محظور عاماً.\n📌 السبب: {reason}"
            )
        except Exception:
            pass
