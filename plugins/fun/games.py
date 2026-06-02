import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import is_chat_active
from helpers.utils import build_mention
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ─── بيانات الألعاب ───────────────────────────────────────────────
ARAB_CAPITALS = {
    "السعودية": "الرياض", "الإمارات": "أبوظبي", "الكويت": "الكويت",
    "قطر": "الدوحة", "البحرين": "المنامة", "عُمان": "مسقط",
    "الأردن": "عمّان", "مصر": "القاهرة", "العراق": "بغداد",
    "سوريا": "دمشق", "لبنان": "بيروت", "اليمن": "صنعاء",
    "ليبيا": "طرابلس", "تونس": "تونس", "الجزائر": "الجزائر",
    "المغرب": "الرباط", "السودان": "الخرطوم", "الصومال": "مقديشو",
    "فرنسا": "باريس", "ألمانيا": "برلين", "إيطاليا": "روما",
    "إسبانيا": "مدريد", "بريطانيا": "لندن", "روسيا": "موسكو",
    "الصين": "بكين", "اليابان": "طوكيو", "الهند": "نيودلهي",
    "البرازيل": "برازيليا", "أستراليا": "كانبيرا", "تركيا": "أنقرة",
}

FLAGS = {
    "🇸🇦": "السعودية", "🇦🇪": "الإمارات", "🇰🇼": "الكويت",
    "🇶🇦": "قطر", "🇧🇭": "البحرين", "🇴🇲": "عُمان",
    "🇯🇴": "الأردن", "🇪🇬": "مصر", "🇮🇶": "العراق",
    "🇫🇷": "فرنسا", "🇩🇪": "ألمانيا", "🇬🇧": "بريطانيا",
    "🇺🇸": "أمريكا", "🇯🇵": "اليابان", "🇨🇳": "الصين",
    "🇧🇷": "البرازيل", "🇮🇳": "الهند", "🇷🇺": "روسيا",
    "🇮🇹": "إيطاليا", "🇪🇸": "إسبانيا", "🇹🇷": "تركيا",
}

ANIME_LIST = {
    "ناروتو": ["ninja", "naruto", "ناروتو", "شيبودن"],
    "ون بيس": ["قراصنة", "one piece", "ون بيس", "لوفي"],
    "دراغون بول": ["سون غوكو", "dragon ball", "دراغون بول"],
    "هانتر هانتر": ["هانتر", "hunter", "غون"],
    "ديمون سلاير": ["قاتل الشياطين", "demon slayer", "تانجيرو"],
    "أتاك أون تايتن": ["هجوم العمالقة", "attack on titan", "إيرين"],
    "فولميتال ألكيميست": ["الخيميائي", "fullmetal", "إدوارد"],
    "ديث نوت": ["دفتر الموت", "death note", "لايت"],
    "دراغون بول Z": ["گوهان", "dbz", "فريزا"],
    "بليتش": ["bleach", "ايتشيغو", "شينيغامي"],
}

CARS = {
    "لامبورغيني": ["lamborghini", "أفنتادور", "هوراكان", "إيطاليا"],
    "فيراري": ["ferrari", "حصان", "إيطاليا", "f40"],
    "بوغاتي": ["bugatti", "شيرون", "أسرع سيارة"],
    "مرسيدس": ["mercedes", "ستار", "AMG"],
    "BMW": ["بي ام دبليو", "بايرن", "ألمانيا"],
    "فورد موستانج": ["mustang", "خيل", "أمريكا", "فورد"],
    "تويوتا": ["toyota", "سوبرا", "لاندكروزر"],
    "نيسان": ["nissan", "GTR", "غودزيلا"],
    "بورش": ["porsche", "911", "كايان"],
    "رانج روفر": ["range rover", "land rover", "إنجلترا"],
}

FOOTBALLERS = {
    "كريستيانو رونالدو": ["CR7", "سيو", "البرتغالي", "يوفنتوس", "ريال"],
    "ليونيل ميسي": ["GOAT", "الأرجنتيني", "برشلونة", "انتر ميامي"],
    "نيمار": ["البرازيلي", "PSG", "السانتوس"],
    "كيليان مبابي": ["الفرنسي", "باريس", "بالونور"],
    "محمد صلاح": ["الفرعون", "ليفربول", "المصري"],
    "روبرت ليفاندوفسكي": ["البولندي", "بايرن", "برشلونة"],
    "فيرجيل فان دايك": ["الهولندي", "ليفربول", "دفاع"],
    "إيرلينغ هالاند": ["النرويجي", "مانشستر سيتي", "آلة الأهداف"],
    "فيليبي أندرسون": ["البرازيلي", "ويست هام"],
    "زين الدين زيدان": ["زيزو", "الفرنسي", "ريال مدريد"],
}

WORD_COMPLETIONS = [
    ("ذهب إلى ال___", "مدرسة"),
    ("شرب كوب ال___", "ماء"),
    ("فتح ال___", "باب"),
    ("قرأ ال___", "كتاب"),
    ("أكل تفاحة ___ لونها", "أحمر"),
    ("السماء لونها ___", "أزرق"),
    ("الثلج لونه ___", "أبيض"),
    ("الليل لونه ___", "أسود"),
    ("النجوم تضيء في ___", "الليل"),
    ("الشمس تشرق من ___", "الشرق"),
]

EMOJI_PUZZLES = [
    ("🌊🏄‍♂️", "تزلج مائي"), ("🌙⭐🌟", "ليلة نجوم"), ("🔥💧", "نار وماء"),
    ("📚✏️🎓", "مدرسة"), ("🎵🎸🎤", "موسيقى"), ("🌹❤️", "حب"),
    ("🚗🏁", "سباق سيارات"), ("🍕🍔🌮", "وجبات"), ("⚽🏆", "كرة القدم"),
    ("🦁👑", "ملك الغابة"), ("🐟🌊🎣", "صيد السمك"), ("🌺🌸🌼", "حديقة"),
    ("✈️🌍🧳", "سفر"), ("🎮🕹️👾", "ألعاب فيديو"), ("🏋️💪🥊", "رياضة"),
]

CHALLENGES = [
    "تكلم بأسلوب رسمي لمدة دقيقة",
    "غيّر صورة البروفايل لمدة ساعة",
    "تكلم بالإنجليزي فقط لـ 5 دقائق",
    "أرسل 3 مجاملات متتالية لأعضاء المجموعة",
    "احكي نكتة مضحكة",
    "غنّي سطراً من أغنية",
    "أرسل صورة selfie",
    "اعترف بشيء محرج",
    "قل اسمك بالمقلوب",
    "صف نفسك بكلمتين فقط",
    "أرسل رسالة صوتية",
    "احكي قصة مضحكة من 3 سطور",
]

DEMON_QUESTIONS = [
    ("هل أنت نائم الآن؟ 😴", ["نعم نايم", "لا صاحي"], "لا صاحي"),
    ("كم عمرك؟", ["15-20", "21-25", "26-30", "+30"], None),
    ("ما هو تقييمك للمجموعة؟", ["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐"], None),
    ("هل تحب المجموعة؟ ❤️", ["أكيد!", "نوعاً ما", "لا يهمني"], "أكيد!"),
    ("من هو الأفضل في المجموعة؟", ["المشرفين", "الأعضاء", "البوت 🤖"], "البوت 🤖"),
]

# ─── متتبع الألعاب النشطة ────────────────────────────────────────
active_games: dict[int, dict] = {}


def add_game_score(chat_id: int, user_id: int, points: int = 1):
    rdb.zincrby(chat_key(chat_id, "game_scores"), points, str(user_id))


async def start_game(client, chat_id, game_type, question, answer, timeout=45, extra=None):
    active_games[chat_id] = {"type": game_type, "answer": answer, "extra": extra}
    await asyncio.sleep(timeout)
    if chat_id in active_games and active_games[chat_id].get("answer") == answer:
        del active_games[chat_id]
        await client.send_message(
            chat_id,
            f"{cfg.BOT_SYMBOL} انتهى الوقت! الجواب كان: **{answer}**"
        )


# ─── الألعاب ──────────────────────────────────────────────────────
@Client.on_message(prefix_filter("تخمين"))
async def word_guess(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    word = random.choice(["مدرسة", "سيارة", "كتاب", "شجرة", "بيت", "قمر",
                           "نجمة", "حقيبة", "باب", "نافذة", "طائرة", "بحر"])
    hidden = " _ ".join(["_"] * len(word))
    active_games[chat_id] = {"type": "word", "answer": word}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **تخمين الكلمة:**\n"
        f"الحروف: **{len(word)}** حروف\n"
        f"الكلمة: `{hidden}`\n\n⏳ **60 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "word", None, word, 60))


@Client.on_message(prefix_filter("عواصم"))
async def capitals_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    country, capital = random.choice(list(ARAB_CAPITALS.items()))
    active_games[chat_id] = {"type": "capital", "answer": capital}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **تخمين العواصم:**\n"
        f"ما هي عاصمة **{country}**؟\n\n⏳ **45 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "capital", None, capital, 45))


@Client.on_message(prefix_filter("أعلام"))
async def flags_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    flag, country = random.choice(list(FLAGS.items()))
    active_games[chat_id] = {"type": "flag", "answer": country}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **تخمين الأعلام:**\n\n{flag}\n\nما هذا العلم؟\n⏳ **30 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "flag", None, country, 30))


@Client.on_message(prefix_filter("إيموجي"))
async def emoji_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    emojis, answer = random.choice(EMOJI_PUZZLES)
    active_games[chat_id] = {"type": "emoji", "answer": answer}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **لعبة الإيموجي:**\n\n{emojis}\n\nماذا تمثل؟\n⏳ **30 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "emoji", None, answer, 30))


@Client.on_message(prefix_filter("أنمي"))
async def anime_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    anime, hints = random.choice(list(ANIME_LIST.items()))
    hint = random.choice(hints)
    active_games[chat_id] = {"type": "anime", "answer": anime}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **تخمين الأنمي:**\n"
        f"تلميح: **{hint}**\n\n"
        f"ما اسم هذا الأنمي؟\n⏳ **45 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "anime", None, anime, 45))


@Client.on_message(prefix_filter("سيارات"))
async def cars_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    car, hints = random.choice(list(CARS.items()))
    hint = random.choice(hints)
    active_games[chat_id] = {"type": "car", "answer": car}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **تخمين السيارة:**\n"
        f"تلميح: **{hint}**\n\n"
        f"ما هذه السيارة؟\n⏳ **45 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "car", None, car, 45))


@Client.on_message(prefix_filter("كرة قدم"))
async def football_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    player, hints = random.choice(list(FOOTBALLERS.items()))
    hint = random.choice(hints)
    active_games[chat_id] = {"type": "football", "answer": player}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **تخمين لاعب كرة القدم:**\n"
        f"تلميح: **{hint}**\n\n"
        f"من هذا اللاعب؟\n⏳ **45 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "football", None, player, 45))


@Client.on_message(prefix_filter("أكمل الجملة"))
async def word_completion_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    sentence, answer = random.choice(WORD_COMPLETIONS)
    active_games[chat_id] = {"type": "completion", "answer": answer}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **أكمل الجملة:**\n\n"
        f"「 {sentence} 」\n\n"
        f"ما الكلمة الناقصة؟\n⏳ **30 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "completion", None, answer, 30))


@Client.on_message(prefix_filter("حساب"))
async def math_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply(f"{cfg.BOT_SYMBOL} فيه لعبة شغالة!")

    a, b = random.randint(1, 50), random.randint(1, 50)
    op = random.choice(["+", "-", "×"])
    answer = a + b if op == "+" else (a - b if op == "-" else a * b)
    active_games[chat_id] = {"type": "math", "answer": str(answer)}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **مسألة حسابية:**\n\n"
        f"🧮 **{a} {op} {b} = ?**\n\n⏳ **20 ثانية**"
    )
    asyncio.create_task(start_game(client, chat_id, "math", None, str(answer), 20))


@Client.on_message(prefix_filter("الأحكام"))
async def challenges(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply(f"{cfg.BOT_SYMBOL} ردّ على شخص لتكليفه بحكم.")

    target = message.reply_to_message.from_user
    challenge = random.choice(CHALLENGES)
    await message.reply(
        f"「 حكم عشوائي 🎯 」\n\n"
        f"{build_mention(target)} عليك أن:\n\n"
        f"**{challenge}**"
    )


@Client.on_message(prefix_filter("الديمون"))
async def demon_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    question, options, correct = random.choice(DEMON_QUESTIONS)

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [[InlineKeyboardButton(opt, callback_data=f"demon:{opt}")] for opt in options]

    await message.reply(
        f"「 الديمون 🎭 」\n\n"
        f"**{question}**",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(prefix_filter("نرد"))
async def dice_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user

    if message.reply_to_message and message.reply_to_message.from_user:
        opponent = message.reply_to_message.from_user
        my_roll = random.randint(1, 6)
        their_roll = random.randint(1, 6)

        if my_roll > their_roll:
            result = f"🏆 {build_mention(user)} فاز!"
            add_game_score(message.chat.id, user.id)
        elif their_roll > my_roll:
            result = f"🏆 {build_mention(opponent)} فاز!"
            add_game_score(message.chat.id, opponent.id)
        else:
            result = "🤝 تعادل!"

        await message.reply(
            f"{cfg.BOT_SYMBOL} **النرد:**\n"
            f"{build_mention(user)}: 🎲 **{my_roll}**\n"
            f"{build_mention(opponent)}: 🎲 **{their_roll}**\n\n{result}"
        )
    else:
        roll = random.randint(1, 6)
        await message.reply(f"{cfg.BOT_SYMBOL} رميت النرد: 🎲 **{roll}**")


@Client.on_message(prefix_filter("روليت"))
async def roulette(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    players_key = chat_key(message.chat.id, "roulette_players")
    rdb.sadd(players_key, str(user.id))
    rdb.expire(players_key, 600)
    count = rdb.scard(players_key)

    await message.reply(
        f"{cfg.BOT_SYMBOL} {build_mention(user)} انضم للروليت! 🎰\n"
        f"المشاركون: **{count}**\n"
        f"استخدم `{cfg.BOT_PREFIX} تدوير` لتدوير الروليت."
    )


@Client.on_message(prefix_filter("تدوير"))
async def spin_roulette(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    players_key = chat_key(message.chat.id, "roulette_players")
    players = list(rdb.smembers(players_key))

    if len(players) < 2:
        return await message.reply(f"{cfg.BOT_SYMBOL} يحتاج لاعبان على الأقل!")

    loser_id = random.choice(players)
    rdb.delete(players_key)

    try:
        loser = await client.get_users(int(loser_id))
        await message.reply(
            f"{cfg.BOT_SYMBOL} الروليت تدور... 🎰\n\n"
            f"💀 الخسران: {build_mention(loser)} — ضربته الرصاصة!"
        )
    except Exception:
        await message.reply(f"{cfg.BOT_SYMBOL} الخسران: `{loser_id}`")


@Client.on_message(prefix_filter("حجر ورقة مقص"))
async def rock_paper_scissors(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    choices = {"حجر": "🪨", "ورقة": "📄", "مقص": "✂️"}
    beats = {"حجر": "مقص", "ورقة": "حجر", "مقص": "ورقة"}

    parts = message.text.split()
    if len(parts) < 3 or parts[2] not in choices:
        return await message.reply(
            f"{cfg.BOT_SYMBOL} الاستخدام: `{cfg.BOT_PREFIX} حجر ورقة مقص [حجر/ورقة/مقص]`"
        )

    player_choice = parts[2]
    bot_choice = random.choice(list(choices.keys()))
    user = message.from_user

    if player_choice == bot_choice:
        result = "🤝 تعادل!"
    elif beats[player_choice] == bot_choice:
        result = f"🏆 {build_mention(user)} فاز!"
        add_game_score(message.chat.id, user.id)
    else:
        result = "🤖 البوت فاز!"

    await message.reply(
        f"{cfg.BOT_SYMBOL} **حجر ورقة مقص:**\n"
        f"أنت: {choices[player_choice]} **{player_choice}**\n"
        f"البوت: {choices[bot_choice]} **{bot_choice}**\n\n{result}"
    )


# ─── مستمع الإجابات (group=5 لتجنب التعارض مع stats) ─────────────
@Client.on_message(filters.group & filters.text, group=5)
async def handle_game_answers(client: Client, message: Message):
    if not message.from_user or not is_chat_active(message.chat.id):
        return

    chat_id = message.chat.id
    if chat_id not in active_games:
        return

    game = active_games[chat_id]
    answer = (game.get("answer") or "").strip().lower()
    user_text = message.text.strip().lower()

    if user_text == answer:
        user = message.from_user
        del active_games[chat_id]
        add_game_score(chat_id, user.id)
        await message.reply(
            f"{cfg.BOT_SYMBOL} 🏆 **{build_mention(user)} أجاب صح!**\n"
            f"الجواب: **{game['answer']}** ✓"
        )


# ─── توب الألعاب ─────────────────────────────────────────────────
@Client.on_message(prefix_filter("توب الألعاب"))
async def top_games(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    top = rdb.zrevrange(chat_key(message.chat.id, "game_scores"), 0, 9, withscores=True)
    if not top:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد بيانات ألعاب.**")

    medals = ["🥇", "🥈", "🥉"] + ["☆"] * 7
    lines = [f"「 توب لاعبي المجموعة 」\n"]
    for i, (uid, score) in enumerate(top):
        try:
            u = await client.get_users(int(uid))
            name = u.first_name[:12]
        except Exception:
            name = f"ID:{uid}"
        lines.append(f"{medals[i]} {name} — **{int(score)}** انتصار")

    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("انهاء اللعبة"))
async def end_game(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    from helpers.permissions import get_user_rank
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    if message.chat.id in active_games:
        game = active_games.pop(message.chat.id)
        await message.reply(
            f"{cfg.BOT_SYMBOL} تم إنهاء اللعبة.\nالجواب كان: **{game.get('answer', '?')}**"
        )
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} لا توجد لعبة نشطة حالياً.")
