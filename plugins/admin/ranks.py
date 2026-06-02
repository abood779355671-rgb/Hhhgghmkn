from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import (
    get_user_rank, set_user_rank, remove_user_rank,
    can_act_on, can_give_rank, is_chat_active
)
from helpers.utils import extract_user_and_reason, resolve_user, build_mention


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


@Client.on_message(prefix_filter("رفع مشرف"))
async def promote_admin(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_id = message.from_user.id
    actor_rank = get_user_rank(actor_id, message.chat.id)

    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    target_rank = get_user_rank(target.id, message.chat.id)
    new_rank = cfg.RANK_ADMIN

    if not can_give_rank(actor_rank, new_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تعطي رتبة أعلى من رتبتك.**")

    if not can_act_on(actor_rank, target_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تعدّل رتبة شخص برتبة مساوية أو أعلى.**")

    set_user_rank(target.id, new_rank, message.chat.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم رفع {build_mention(target)} إلى رتبة **{cfg.RANK_NAMES[new_rank]}** ☆"
    )


@Client.on_message(prefix_filter("تنزيل مشرف"))
async def demote_admin(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_id = message.from_user.id
    actor_rank = get_user_rank(actor_id, message.chat.id)

    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    target_rank = get_user_rank(target.id, message.chat.id)

    if not can_act_on(actor_rank, target_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تعدّل رتبة شخص برتبة مساوية أو أعلى.**")

    remove_user_rank(target.id, message.chat.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم تنزيل {build_mention(target)} إلى **{cfg.RANK_NAMES[cfg.RANK_MEMBER]}**."
    )


@Client.on_message(prefix_filter("رفع مطور"))
async def promote_dev(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_id = message.from_user.id
    actor_rank = get_user_rank(actor_id, message.chat.id)

    if actor_rank > cfg.RANK_DEV:
        return await message.reply(f"{cfg.BOT_SYMBOL} **هذا الأمر للمطورين فقط.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    target_rank = get_user_rank(target.id, message.chat.id)
    new_rank = cfg.RANK_DEV2

    if not can_give_rank(actor_rank, new_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تعطي رتبة أعلى من رتبتك.**")

    if not can_act_on(actor_rank, target_rank):
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما تقدر تعدّل رتبة شخص برتبة مساوية أو أعلى.**")

    set_user_rank(target.id, new_rank, message.chat.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم رفع {build_mention(target)} إلى رتبة **{cfg.RANK_NAMES[new_rank]}** ☆"
    )


@Client.on_message(prefix_filter("تنزيل مطور"))
async def demote_dev(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_id = message.from_user.id
    actor_rank = get_user_rank(actor_id, message.chat.id)

    if actor_rank > cfg.RANK_OWNER:
        return await message.reply(f"{cfg.BOT_SYMBOL} **هذا الأمر للمالك فقط.**")

    user_id, _ = extract_user_and_reason(message)
    if not user_id:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ردّ على شخص أو اذكر @يوزر.**")

    target = await resolve_user(client, user_id)
    if not target:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت المستخدم.**")

    remove_user_rank(target.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم إزالة رتبة المطور من {build_mention(target)}."
    )


@Client.on_message(prefix_filter("رتبتي"))
async def my_rank(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    rank = get_user_rank(user.id, message.chat.id)
    await message.reply(
        f"「 {build_mention(user)} 」\n"
        f"{cfg.BOT_SYMBOL} رتبتك: **{cfg.RANK_NAMES.get(rank, 'عضو')}**"
    )
