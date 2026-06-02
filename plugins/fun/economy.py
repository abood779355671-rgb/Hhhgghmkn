import random
import time
from datetime import date
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import is_chat_active
from helpers.utils import build_mention, extract_user_and_reason, resolve_user
from database.redis_client import rdb, user_key, global_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ─── الدوال الأساسية ──────────────────────────────────────────────
def get_balance(user_id: int) -> int:
    val = rdb.get(user_key(user_id, "balance"))
    return int(val) if val else 0


def set_balance(user_id: int, amount: int):
    amount = max(0, amount)
    rdb.set(user_key(user_id, "balance"), amount)
    # Sorted Set لقائمة الأثرياء
    rdb.zadd(global_key("leaderboard:rich"), {str(user_id): amount})


def add_balance(user_id: int, amount: int) -> int:
    new = get_balance(user_id) + amount
    set_balance(user_id, new)
    return max(0, new)


def has_account(user_id: int) -> bool:
    return rdb.exists(user_key(user_id, "account")) > 0


def create_account(user_id: int):
    rdb.set(user_key(user_id, "account"), "1")
    set_balance(user_id, 1000)


def get_today() -> str:
    return date.today().isoformat()


def can_claim_salary(user_id: int) -> bool:
    return rdb.get(user_key(user_id, "last_salary")) != get_today()


def claim_salary(user_id: int):
    rdb.set(user_key(user_id, "last_salary"), get_today())


def add_stolen(thief_id: int, amount: int):
    rdb.zincrby(global_key("leaderboard:thieves"), amount, str(thief_id))


# ─── الأوامر ──────────────────────────────────────────────────────
@Client.on_message(prefix_filter("انشاء حساب بنكي"))
async def create_bank_account(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if has_account(user.id):
        bal = get_balance(user.id)
        return await message.reply(
            f"{cfg.BOT_SYMBOL} عندك حساب بنكي بالفعل.\n💰 رصيدك: **{bal:,}** ريال"
        )
    create_account(user.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم إنشاء حسابك البنكي يا {build_mention(user)} ✓\n"
        f"💰 رصيدك الابتدائي: **1,000** ريال\n"
        f"استخدم `{cfg.BOT_PREFIX} راتب` لأخذ راتبك اليومي!"
    )


@Client.on_message(prefix_filter("فلوسي"))
async def my_balance(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(
            f"{cfg.BOT_SYMBOL} ما عندك حساب. استخدم `{cfg.BOT_PREFIX} انشاء حساب بنكي`"
        )
    bal = get_balance(user.id)
    # ترتيبه في القائمة
    rank_pos = rdb.zrevrank(global_key("leaderboard:rich"), str(user.id))
    rank_text = f"#{rank_pos + 1}" if rank_pos is not None else "غير مصنف"
    await message.reply(
        f"「 حسابي البنكي 」\n"
        f"{cfg.BOT_SYMBOL} {build_mention(user)}\n"
        f"💰 الرصيد: **{bal:,}** ريال\n"
        f"📊 الترتيب: **{rank_text}**"
    )


@Client.on_message(prefix_filter("راتب"))
async def daily_salary(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")
    if not can_claim_salary(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} خذيت راتبك اليوم، اجي بكره! 📅")

    salary = random.randint(500, 2000)
    new_bal = add_balance(user.id, salary)
    claim_salary(user.id)
    await message.reply(
        f"{cfg.BOT_SYMBOL} صُرِّف راتبك اليومي يا {build_mention(user)}!\n"
        f"💵 الراتب: **{salary:,}** ريال\n"
        f"💰 الرصيد الجديد: **{new_bal:,}** ريال"
    )


@Client.on_message(prefix_filter("بخشيش"))
async def tip(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")

    now = int(time.time())
    last = rdb.get(user_key(user.id, "last_tip"))
    if last and now - int(last) < 3600:
        mins = (3600 - (now - int(last))) // 60
        return await message.reply(f"{cfg.BOT_SYMBOL} انتظر **{mins}** دقيقة للبخشيش القادم ⏳")

    amount = random.choice([0, 0, 50, 100, 200, 500, 1000, 2000])
    rdb.set(user_key(user.id, "last_tip"), str(now))

    if amount == 0:
        return await message.reply(f"{cfg.BOT_SYMBOL} بحثت وما لقيت شي 😅")

    new_bal = add_balance(user.id, amount)
    await message.reply(
        f"{cfg.BOT_SYMBOL} حصلت على بخشيش **{amount:,}** ريال! 💸\n"
        f"💰 رصيدك: **{new_bal:,}** ريال"
    )


@Client.on_message(prefix_filter("كنز"))
async def find_treasure(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")

    now = int(time.time())
    last = rdb.get(user_key(user.id, "last_kanz"))
    if last and now - int(last) < 7200:
        remaining = 7200 - (now - int(last))
        return await message.reply(
            f"{cfg.BOT_SYMBOL} انتظر **{remaining // 3600}س {(remaining % 3600) // 60}د** ⏳"
        )

    rdb.set(user_key(user.id, "last_kanz"), str(now))
    roll = random.random()

    if roll < 0.4:
        return await message.reply(f"{cfg.BOT_SYMBOL} بحثت في الصحراء... ما لقيت شي! 🏜️")
    elif roll < 0.7:
        amount = random.randint(200, 800)
        msg = f"وجدت كنزاً صغيراً! 🪙"
    elif roll < 0.9:
        amount = random.randint(1000, 5000)
        msg = f"☆ كنز كبير! 💎"
    else:
        amount = random.randint(10000, 50000)
        msg = f"「 ༄ الجاكبوت! 」🏆 الكنز الأسطوري!"

    new_bal = add_balance(user.id, amount)
    await message.reply(
        f"{cfg.BOT_SYMBOL} {msg}\n"
        f"**+{amount:,}** ريال\n"
        f"💰 رصيدك: **{new_bal:,}** ريال"
    )


@Client.on_message(prefix_filter("عجلة"))
async def wheel_bet(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")

    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        return await message.reply(f"{cfg.BOT_SYMBOL} الاستخدام: `{cfg.BOT_PREFIX} عجلة [المبلغ]`")

    bet = int(parts[2])
    bal = get_balance(user.id)
    if bet > bal:
        return await message.reply(f"{cfg.BOT_SYMBOL} ما عندك كافي! رصيدك: **{bal:,}**")
    if bet < 10:
        return await message.reply(f"{cfg.BOT_SYMBOL} الحد الأدنى **10** ريال.")

    outcomes = [
        ("خسرت كل شي 😭", -1.0),
        ("خسرت نص الرهان 😓", -0.5),
        ("خسرت 😕", -0.25),
        ("تعادل ↔️", 0),
        ("ربحت! ✅", 0.5),
        ("ربحت الضعف! 🎉", 1.0),
        ("ربحت 3x! 🤑", 2.0),
    ]
    text, mult = random.choices(outcomes, weights=[5, 15, 20, 20, 20, 15, 5], k=1)[0]
    change = int(bet * mult)
    new_bal = add_balance(user.id, change)
    sign = "+" if change >= 0 else ""
    await message.reply(
        f"{cfg.BOT_SYMBOL} العجلة تدور... 🎡\n\n"
        f"النتيجة: **{text}**\n"
        f"التغيير: **{sign}{change:,}** ريال\n"
        f"💰 رصيدك: **{new_bal:,}** ريال"
    )


@Client.on_message(prefix_filter("استثمار فلوسي"))
async def invest(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")

    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        return await message.reply(f"{cfg.BOT_SYMBOL} الاستخدام: `{cfg.BOT_PREFIX} استثمار فلوسي [المبلغ]`")

    amount = int(parts[2])
    bal = get_balance(user.id)
    if amount > bal:
        return await message.reply(f"{cfg.BOT_SYMBOL} رصيدك **{bal:,}** — ما يكفي!")

    roll = random.random()
    if roll < 0.35:
        loss = int(amount * random.uniform(0.1, 0.5))
        new_bal = add_balance(user.id, -loss)
        await message.reply(
            f"{cfg.BOT_SYMBOL} الاستثمار خسر 📉\nخسرت **{loss:,}** ريال\n💰 رصيدك: **{new_bal:,}**"
        )
    elif roll < 0.8:
        gain = int(amount * random.uniform(0.1, 0.8))
        new_bal = add_balance(user.id, gain)
        await message.reply(
            f"{cfg.BOT_SYMBOL} الاستثمار نجح 📈\nربحت **{gain:,}** ريال\n💰 رصيدك: **{new_bal:,}**"
        )
    else:
        gain = int(amount * random.uniform(1.0, 3.0))
        new_bal = add_balance(user.id, gain)
        await message.reply(
            f"{cfg.BOT_SYMBOL} ☆ استثمار ناجح جداً! 🚀\nربحت **{gain:,}** ريال\n💰 رصيدك: **{new_bal:,}**"
        )


@Client.on_message(prefix_filter("تحويل"))
async def transfer(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    user = message.from_user
    if not has_account(user.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")

    parts = message.text.split()
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply(f"{cfg.BOT_SYMBOL} ردّ على شخص تريد تحويله فلوس.")
    if len(parts) < 3 or not parts[2].isdigit():
        return await message.reply(f"{cfg.BOT_SYMBOL} الاستخدام: ردّ على شخص واكتب `{cfg.BOT_PREFIX} تحويل [المبلغ]`")

    target = message.reply_to_message.from_user
    if target.id == user.id:
        return await message.reply(f"{cfg.BOT_SYMBOL} ما تقدر تحول لنفسك 😄")
    if not has_account(target.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} {build_mention(target)} ما عنده حساب بنكي.")

    amount = int(parts[2])
    bal = get_balance(user.id)
    if amount > bal:
        return await message.reply(f"{cfg.BOT_SYMBOL} رصيدك **{bal:,}** — ما يكفي!")
    if amount < 1:
        return await message.reply(f"{cfg.BOT_SYMBOL} المبلغ يجب أن يكون أكبر من 0.")

    add_balance(user.id, -amount)
    add_balance(target.id, amount)
    await message.reply(
        f"{cfg.BOT_SYMBOL} تم تحويل **{amount:,}** ريال\n"
        f"من: {build_mention(user)}\n"
        f"إلى: {build_mention(target)} ✓"
    )


@Client.on_message(prefix_filter("زرف"))
async def steal(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    thief = message.from_user
    if not has_account(thief.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} افتح حساباً أولاً.")

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply(f"{cfg.BOT_SYMBOL} ردّ على شخص تريد سرقته.")

    now = int(time.time())
    last = rdb.get(user_key(thief.id, "last_steal"))
    if last and now - int(last) < 1800:
        mins = (1800 - (now - int(last))) // 60
        return await message.reply(f"{cfg.BOT_SYMBOL} انتظر **{mins}** دقيقة قبل السرقة مرة أخرى ⏳")

    target = message.reply_to_message.from_user
    if target.id == thief.id:
        return await message.reply(f"{cfg.BOT_SYMBOL} ما تقدر تسرق نفسك 😂")
    if not has_account(target.id):
        return await message.reply(f"{cfg.BOT_SYMBOL} ما عنده حساب!")

    target_bal = get_balance(target.id)
    if target_bal < 100:
        return await message.reply(f"{cfg.BOT_SYMBOL} ما يستاهل، رصيده فاضي 😂")

    rdb.set(user_key(thief.id, "last_steal"), str(now))
    roll = random.random()
    if roll < 0.45:
        penalty = random.randint(100, 500)
        new_bal = add_balance(thief.id, -penalty)
        await message.reply(
            f"{cfg.BOT_SYMBOL} انمسكت وانت تحاول تسرق {build_mention(target)} 🚔\n"
            f"غرامة: **{penalty:,}** ريال\n💰 رصيدك: **{new_bal:,}**"
        )
    else:
        stolen = int(target_bal * random.uniform(0.05, 0.25))
        add_balance(target.id, -stolen)
        new_bal = add_balance(thief.id, stolen)
        add_stolen(thief.id, stolen)
        await message.reply(
            f"{cfg.BOT_SYMBOL} نجحت! سرقت **{stolen:,}** ريال من {build_mention(target)} 🎭\n"
            f"💰 رصيدك: **{new_bal:,}**"
        )


@Client.on_message(prefix_filter("توب الفلوس"))
async def top_rich_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    top = rdb.zrevrange(global_key("leaderboard:rich"), 0, 9, withscores=True)
    if not top:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد بيانات بعد.**")

    medals = ["🥇", "🥈", "🥉"] + ["☆"] * 7
    lines = [f"「 توب أثرياء البوت 」\n"]
    for i, (uid, bal) in enumerate(top):
        try:
            u = await client.get_users(int(uid))
            name = u.first_name[:12]
        except Exception:
            name = f"ID:{uid}"
        lines.append(f"{medals[i]} {name} — **{int(bal):,}** ريال")

    await message.reply("\n".join(lines))


@Client.on_message(prefix_filter("توب الحراميه"))
async def top_thieves_list(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    top = rdb.zrevrange(global_key("leaderboard:thieves"), 0, 9, withscores=True)
    if not top:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد بيانات بعد.**")

    medals = ["🥇", "🥈", "🥉"] + ["☆"] * 7
    lines = [f"「 توب الحراميه 」\n"]
    for i, (uid, stolen) in enumerate(top):
        try:
            u = await client.get_users(int(uid))
            name = u.first_name[:12]
        except Exception:
            name = f"ID:{uid}"
        lines.append(f"{medals[i]} {name} — سرق **{int(stolen):,}** ريال")

    await message.reply("\n".join(lines))
