from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import is_chat_active
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


def increment_messages(chat_id: int, user_id: int):
    rdb.zincrby(chat_key(chat_id, "msg_count"), 1, str(user_id))
    rdb.incr(chat_key(chat_id, "total_msgs"))


@Client.on_message(filters.group, group=10)
async def count_messages(client: Client, message: Message):
    """يعدّ جميع أنواع الرسائل — نصوص وصور وفيديو وملصقات وغيرها"""
    if not message.from_user or not is_chat_active(message.chat.id):
        return
    if message.service:
        return
    increment_messages(message.chat.id, message.from_user.id)


@Client.on_message(prefix_filter("حسابي"))
async def my_stats(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    chat_id = message.chat.id

    count = rdb.zscore(chat_key(chat_id, "msg_count"), str(user.id))
    count = int(count) if count else 0

    rank_list = rdb.zrevrange(chat_key(chat_id, "msg_count"), 0, -1)
    try:
        rank_pos = rank_list.index(str(user.id)) + 1
    except ValueError:
        rank_pos = "غير مصنف"

    total = rdb.get(chat_key(chat_id, "total_msgs")) or "0"

    await message.reply(
        f"「 إحصائيات {user.first_name} 」\n"
        f"{cfg.BOT_SYMBOL} الرسائل: **{count:,}**\n"
        f"{cfg.BOT_SYMBOL} الترتيب: **#{rank_pos}**\n"
        f"{cfg.BOT_SYMBOL} إجمالي المجموعة: **{int(total):,}** رسالة"
    )


@Client.on_message(prefix_filter("ترتيب"))
async def ranking(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    user_id = message.from_user.id

    top = rdb.zrevrange(chat_key(chat_id, "msg_count"), 0, 9, withscores=True)
    if not top:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد إحصائيات بعد.**")

    my_score = rdb.zscore(chat_key(chat_id, "msg_count"), str(user_id))
    my_score = int(my_score) if my_score else 0
    my_rank_list = rdb.zrevrange(chat_key(chat_id, "msg_count"), 0, -1)
    try:
        my_pos = my_rank_list.index(str(user_id)) + 1
    except ValueError:
        my_pos = "غير مصنف"

    medals = ["🥇", "🥈", "🥉"] + ["☆"] * 7
    lines = [f"{cfg.BOT_SYMBOL} **ترتيب الأعضاء:**\n"]
    for i, (uid, score) in enumerate(top):
        try:
            u = await client.get_users(int(uid))
            name = u.first_name[:15]
        except Exception:
            name = f"ID:{uid}"
        lines.append(f"{medals[i]} {name} — **{int(score):,}** رسالة")

    lines.append(f"\n{cfg.BOT_SYMBOL} ترتيبك: **#{my_pos}** ({my_score:,} رسالة)")
    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("توب"))
async def top_members(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id

    top = rdb.zrevrange(chat_key(chat_id, "msg_count"), 0, 4, withscores=True)
    if not top:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد إحصائيات بعد.**")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = [f"「 توب 5 أكثر الأعضاء نشاطاً 」\n"]
    for i, (uid, score) in enumerate(top):
        try:
            u = await client.get_users(int(uid))
            mention = f"[{u.first_name[:12]}](tg://user?id={uid})"
        except Exception:
            mention = f"`{uid}`"
        lines.append(f"{medals[i]} {mention} — **{int(score):,}** رسالة")

    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("مسح الاحصائيات"))
async def reset_stats(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    from helpers.permissions import get_user_rank
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    rdb.delete(chat_key(message.chat.id, "msg_count"))
    rdb.delete(chat_key(message.chat.id, "total_msgs"))
    await message.reply(f"{cfg.BOT_SYMBOL} تم **مسح إحصائيات المجموعة** ✓")
