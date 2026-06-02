from pyrogram import Client
from pyrogram.types import Message
from config import cfg
from database.redis_client import rdb, chat_key, user_key, global_key


def get_user_rank(user_id: int, chat_id: int = None) -> int:
    """إرجاع رتبة المستخدم (1=مالك، 6=عضو عادي)"""
    if user_id == cfg.OWNER_ID:
        return cfg.RANK_OWNER

    global_rank = rdb.get(user_key(user_id, "rank"))
    if global_rank:
        rank = int(global_rank)
        if rank <= cfg.RANK_MOD:
            return rank

    if chat_id:
        chat_rank = rdb.get(chat_key(chat_id, "user", user_id, "rank"))
        if chat_rank:
            return int(chat_rank)

    return cfg.RANK_MEMBER


def set_user_rank(user_id: int, rank: int, chat_id: int = None) -> bool:
    """تعيين رتبة المستخدم"""
    if rank <= cfg.RANK_MOD:
        rdb.set(user_key(user_id, "rank"), rank)
    if chat_id:
        rdb.set(chat_key(chat_id, "user", user_id, "rank"), rank)
    return True


def remove_user_rank(user_id: int, chat_id: int = None):
    """إزالة رتبة المستخدم"""
    rdb.delete(user_key(user_id, "rank"))
    if chat_id:
        rdb.delete(chat_key(chat_id, "user", user_id, "rank"))


def can_act_on(actor_rank: int, target_rank: int) -> bool:
    """يمكن التصرف على شخص ذي رتبة أدنى فقط"""
    return actor_rank < target_rank


def can_give_rank(giver_rank: int, new_rank: int) -> bool:
    """لا يمكن منح رتبة أعلى من رتبتك"""
    return giver_rank < new_rank


def require_rank(min_rank: int):
    """ديكوراتور للتحقق من الرتبة الدنيا المطلوبة"""
    def decorator(func):
        async def wrapper(client: Client, message: Message, *args, **kwargs):
            chat_id = message.chat.id
            user_id = message.from_user.id if message.from_user else 0
            rank = get_user_rank(user_id, chat_id)
            if rank > min_rank:
                await message.reply(
                    f"{cfg.BOT_SYMBOL} **ما عندك صلاحية هذا الأمر.**"
                )
                return
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator


def is_chat_active(chat_id: int) -> bool:
    """هل البوت مفعّل في هذه المجموعة؟"""
    return rdb.sismember(global_key("active_chats"), str(chat_id))


def activate_chat(chat_id: int):
    rdb.sadd(global_key("active_chats"), str(chat_id))


def deactivate_chat(chat_id: int):
    rdb.srem(global_key("active_chats"), str(chat_id))


def get_active_chats() -> list[int]:
    return [int(c) for c in rdb.smembers(global_key("active_chats"))]
