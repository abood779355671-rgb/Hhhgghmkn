import random
import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import build_mention, get_chat_setting, set_chat_setting
from database.redis_client import rdb, chat_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


LOVE_REPLIES = [
    f"وأنا أحبك أكثر! 🥰",
    f"يا هلا فيك، أنت النور 💛",
    f"والله حبك يحيّيني ❤️",
    f"أنا دايم هنا معك 🤍",
    f"حبك يجعلني أشتغل بروح 💙",
]

HATE_REPLIES = [
    f"بصراحة؟ أنا أحبك حتى لو أكرهتني 😌",
    f"أوكي، بس أنا ما أقدر أكرهك 😅",
    f"تمام، بس أنا ما خذيت بالي 😤",
    f"ههه، مو مشكلة — أنا بخير 😇",
    f"حسناً، سأتجاهل ذلك 🙃",
]

MEME_FILE_IDS_KEY = global_key("meme_file_ids")


def get_meme_file_ids() -> list[str]:
    ids = rdb.lrange(MEME_FILE_IDS_KEY, 0, -1)
    return ids if ids else []


@Client.on_message(filters.group & filters.text, group=30)
async def auto_replies(client: Client, message: Message):
    if not message.text or not message.from_user:
        return
    if not is_chat_active(message.chat.id):
        return

    text = message.text.strip().lower()
    chat_id = message.chat.id

    bot_triggers = ["بوت", cfg.BOT_NAME.lower(), "رعد"]
    if any(t in text for t in bot_triggers) and text in bot_triggers:
        return await message.reply(f"نعم؟ 👀")

    if text == "احبك":
        return await message.reply(random.choice(LOVE_REPLIES))

    if text == "اكرهك":
        return await message.reply(random.choice(HATE_REPLIES))

    if text == "ميمز":
        memes = get_meme_file_ids()
        if memes:
            return await message.reply_photo(random.choice(memes))
        else:
            return await message.reply(
                f"{cfg.BOT_SYMBOL} **لا توجد ميمز محفوظة حالياً.**\n"
                f"لإضافة ميمز: أرسل صورة للبوت في الخاص وأضف file_id لـ Redis:\n"
                f"`rpush {MEME_FILE_IDS_KEY} <file_id>`"
            )

    import re
    quran_match = re.search(r"سورة\s+(\d+)(?:\s+آية\s+(\d+))?", text)
    if quran_match:
        surah = quran_match.group(1)
        ayah = quran_match.group(2) or "1"
        await send_quran_ayah(client, message, surah, ayah)


async def send_quran_ayah(client: Client, message: Message, surah: str, ayah: str):
    url = f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/ar.alafasy"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url)
            data = resp.json()
        if data.get("status") == "OK":
            ayah_data = data["data"]
            text = ayah_data.get("text", "")
            surah_name = ayah_data.get("surah", {}).get("name", f"سورة {surah}")
            number = ayah_data.get("numberInSurah", ayah)
            await message.reply(
                f"「 {surah_name} — الآية {number} 」\n\n"
                f"﴿ {text} ﴾"
            )
        else:
            await message.reply(f"{cfg.BOT_SYMBOL} **ما لقيت الآية. تأكد من رقم السورة والآية.**")
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} **فشل جلب الآية:** `{e}`")


@Client.on_message(prefix_filter(r"اطلع|اطلعي"), group=5)
async def leave_group(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_OWNER:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية. هذا الأمر للمالك فقط.**")

    await message.reply(f"{cfg.BOT_SYMBOL} **حسناً، إلى اللقاء! 👋**")
    await asyncio.sleep(1)
    await client.leave_chat(message.chat.id)


@Client.on_chat_member_updated()
async def member_events(client: Client, update: ChatMemberUpdated):
    if not update.new_chat_member or not update.old_chat_member:
        return

    chat_id = update.chat.id
    if not is_chat_active(chat_id):
        return

    old_status = update.old_chat_member.status.name
    new_status = update.new_chat_member.status.name
    user = update.new_chat_member.user

    if old_status in ("LEFT", "BANNED") and new_status == "MEMBER":
        from plugins.utils.welcome import get_welcome_data
        data = get_welcome_data(chat_id)
        if data.get("enabled", False):
            name = user.first_name or "عضو جديد"
            chat_title = update.chat.title or "المجموعة"
            welcome_text = data.get("message") or (
                f"أهلاً وسهلاً بـ {build_mention(user)} في {chat_title}! 🎉\n"
                f"نورت يا {name}، يا هلا والله ☆"
            )
            welcome_text = welcome_text.replace("{name}", build_mention(user)).replace("{chat}", chat_title)
            try:
                if data.get("with_photo") and user.photo:
                    photos = await client.get_profile_photos(user.id, limit=1)
                    if photos.total_count > 0:
                        await client.send_photo(chat_id, photos[0].file_id, caption=welcome_text)
                        return
                await client.send_message(chat_id, welcome_text)
            except Exception:
                pass

    elif new_status in ("LEFT", "BANNED") and old_status == "MEMBER":
        farewell_enabled = get_chat_setting(chat_id, "farewell_enabled", False)
        if farewell_enabled:
            name = user.first_name or "عضو"
            try:
                await client.send_message(
                    chat_id,
                    f"{cfg.BOT_SYMBOL} مع السلامة **{name}** 👋\nنتمنى نشوفك مرة ثانية!"
                )
            except Exception:
                pass


@Client.on_message(prefix_filter("تفعيل الوداع"), group=5)
async def enable_farewell(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "farewell_enabled", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل رسالة الوداع** ✓")


@Client.on_message(prefix_filter("تعطيل الوداع"), group=5)
async def disable_farewell(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    if actor_rank > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "farewell_enabled", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل رسالة الوداع** ✓")
