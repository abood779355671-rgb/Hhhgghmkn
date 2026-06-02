import random
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ─── الردود التلقائية ─────────────────────────────────────────────
SMART_REPLIES: list[tuple[list[str], list[str]]] = [
    (
        ["صباح الخير", "صباح النور", "صبح", "صباحيات"],
        ["صباح النور يا قلب 🌸", "صباح الورد والياسمين ☀️", "يسعد صباحك 😊",
         "صباح الخير، يومك بخير إن شاء الله 🌼", "صبّحتنا بالنور ☕"],
    ),
    (
        ["مساء الخير", "مساء النور", "مساء الورد"],
        ["مساء النور يا عسل 🌙", "مساء الورد والفل 🌹", "يسعد مساك 💛",
         "مساء الخير، ليلتك سعيدة 🌃", "مساؤك ألف خير ⭐"],
    ),
    (
        ["كيف حالك", "كيفك", "كيف الحال", "عامل ايه", "شلونك", "كيف الاحوال"],
        ["الحمد لله تمام 😄", "بخير والحمد لله، وأنت؟ 😊",
         "ماشي الحال 🙂", "تمام كالعادة 💪", "بألف خير والحمد لله ✨"],
    ),
    (
        ["شكراً", "شكرا", "شكراً جزيلاً", "مشكور", "يسلمو", "يسلموا", "ثانكيو"],
        ["العفو 😊", "على الرحب والسعة 🤍", "لا شكر على واجب ✨",
         "وش كلفت 😄", "أهلاً وسهلاً، دايماً في الخدمة 💙"],
    ),
    (
        ["وداعاً", "مع السلامة", "باي", "سلام", "تصبح على خير", "تصبحون على خير"],
        ["مع السلامة 👋", "إلى اللقاء 💛", "تصبح على خير 🌙",
         "سلّم عليّ الأهل 😊", "في أمان الله 🌹"],
    ),
    (
        ["الله", "سبحان الله", "الحمد لله", "لا اله الا الله", "ما شاء الله"],
        ["سبحان الله وبحمده 🤲", "الحمد لله دائماً وأبداً 💚",
         "لا إله إلا الله محمد رسول الله ☪️", "ما شاء الله تبارك الله ✨",
         "اللهم صلِّ على محمد 🌷"],
    ),
    (
        ["آية", "دعاء", "حديث", "اقتباس ديني"],
        [
            "﴿ وَمَن يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ ﴾ [الطلاق: 3] 🤲",
            "﴿ فَإِنَّ مَعَ الْعُسْرِ يُسْرًا ﴾ [الشرح: 5] 💚",
            "﴿ وَلَا تَيْأَسُوا مِن رَّوْحِ اللَّهِ ﴾ [يوسف: 87] 🌸",
            "اللهم اجعل في قلبي نوراً، وفي لساني نوراً 🤍",
            "« من قال سبحان الله وبحمده في يوم مائة مرة حُطّت خطاياه » 💛",
        ],
    ),
    (
        ["ملل", "بملل", "مليت"],
        ["روّح الحين 😄", "اقرأ شيء مفيد 📚", "شوف الأعضاء هنا 👀",
         "العب لعبة: اكتب «تخمين» 🎮", "خذ استراحة ☕"],
    ),
    (
        ["جوعان", "جوعانه", "بدي آكل", "بدي اكل"],
        ["اطبخ شيء حلو 🍳", "اطلب ديليفري 🍕", "شوف ثلاجتك أولاً 😄",
         "الأكل أمانة لا تخونها 🥗", "بعد كم وقت رح تاكل؟ 😂"],
    ),
    (
        ["نايم", "نعسان", "نعسانه", "تعبان"],
        ["نام وارتاح 😴", "قيلولة خفيفة تجدد النشاط 💤",
         "الله يعطيك العافية 🤍", "روح نام، الغروب ما راح يفوتك 😄"],
    ),
]

BAD_WORDS = [
    "كس", "طيز", "شرموطة", "عاهرة", "خول", "لعين", "زب",
    "متناك", "حمار", "كلب", "نيك",
]

BAD_WORD_WARNINGS = [
    f"{cfg.BOT_SYMBOL} ⚠️ تجنب الكلام الفاحش من فضلك!",
    f"{cfg.BOT_SYMBOL} ⚠️ الكلام هذا مو لائق، ارفع مستواك.",
    f"{cfg.BOT_SYMBOL} ⚠️ تحذير: الكلام الفاحش ممنوع في المجموعة.",
    f"{cfg.BOT_SYMBOL} ⚠️ راعِ الآخرين، الكلام الفاحش غير مقبول.",
]


def _smart_replies_enabled(chat_id: int) -> bool:
    return get_chat_setting(chat_id, "smart_replies", True)


# ─── تفعيل / تعطيل ────────────────────────────────────────────────
@Client.on_message(prefix_filter("تفعيل الردود"))
async def enable_smart(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "smart_replies", True)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل الردود الذكية** ✓")


@Client.on_message(prefix_filter("تعطيل الردود"))
async def disable_smart(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    set_chat_setting(message.chat.id, "smart_replies", False)
    await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل الردود الذكية** ✓")


# ─── handler الرئيسي ──────────────────────────────────────────────
@Client.on_message(filters.group & filters.text, group=31)
async def smart_reply_handler(client: Client, message: Message):
    if not message.text or not message.from_user:
        return
    if not is_chat_active(message.chat.id):
        return
    if not _smart_replies_enabled(message.chat.id):
        return

    text = message.text.strip().lower()

    # ─── فحص الكلام الفاحش ───
    for word in BAD_WORDS:
        if word in text:
            await message.reply(random.choice(BAD_WORD_WARNINGS))
            return

    # ─── اسم البوت / كلمة بوت ───
    bot_names = [cfg.BOT_NAME.lower(), cfg.BOT_PREFIX.lower(), "رعد", "بوت"]
    for bn in bot_names:
        if bn in text and len(text) > len(bn):
            snippets = [
                f"نعم؟ 👀", f"أنا هنا 😊", f"طلبك أمر 💙",
                f"أيوه وش تبي؟ 😄", f"خدمتك 🤍",
            ]
            await message.reply(random.choice(snippets))
            return

    # ─── الردود العاطفية والاجتماعية ───
    for triggers, responses in SMART_REPLIES:
        for trigger in triggers:
            if trigger in text:
                await message.reply(random.choice(responses))
                return
