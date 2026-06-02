import json
from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from helpers.permissions import get_user_rank, is_chat_active
from database.redis_client import rdb, chat_key


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


PLUGIN_HASH = "custom_plugins"
MEDIA_TYPES = {"نص": "text", "صورة": "photo", "ستيكر": "sticker", "صوت": "voice"}

WIZARD_STEPS: dict[int, dict] = {}


def _get_plugins(chat_id: int) -> dict:
    raw = rdb.hget(chat_key(chat_id, PLUGIN_HASH), "data")
    return json.loads(raw) if raw else {}


def _save_plugins(chat_id: int, data: dict):
    rdb.hset(chat_key(chat_id, PLUGIN_HASH), "data", json.dumps(data, ensure_ascii=False))


def _del_plugin(chat_id: int, trigger: str) -> bool:
    data = _get_plugins(chat_id)
    if trigger not in data:
        return False
    del data[trigger]
    _save_plugins(chat_id, data)
    return True


# ═══════════════════════════════════════════════════════════════════
#  معالج إضافة ميزة — خطوات
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter("اضف ميزة"))
async def add_plugin_start(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    uid = message.from_user.id
    WIZARD_STEPS[uid] = {"step": "trigger", "chat_id": message.chat.id}

    await message.reply(
        f"{cfg.BOT_SYMBOL} **إضافة ميزة جديدة** 🛠\n\n"
        f"**الخطوة 1/3:** أرسل **الكلمة أو العبارة المحفزة** التي يكتبها العضو:"
    )


@Client.on_message(filters.group & filters.text, group=10)
async def plugin_wizard(client: Client, message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    if uid not in WIZARD_STEPS:
        return
    if WIZARD_STEPS[uid].get("chat_id") != message.chat.id:
        return
    if message.text and message.text.startswith(cfg.BOT_PREFIX):
        return

    state = WIZARD_STEPS[uid]
    text = message.text.strip()

    if state["step"] == "trigger":
        state["trigger"] = text
        state["step"] = "kind"
        types_display = " / ".join(MEDIA_TYPES.keys())
        await message.reply(
            f"{cfg.BOT_SYMBOL} **الخطوة 2/3:** اختر **نوع الرد:**\n{types_display}"
        )

    elif state["step"] == "kind":
        kind = MEDIA_TYPES.get(text)
        if not kind:
            types_display = " / ".join(MEDIA_TYPES.keys())
            return await message.reply(
                f"{cfg.BOT_SYMBOL} نوع غير صحيح. اختر من: **{types_display}**"
            )
        state["kind"] = kind
        state["step"] = "content"
        hints = {
            "text": "أرسل **النص** الذي تريد البوت يرسله.",
            "photo": "أرسل **صورة** (أو file_id) تريد البوت يرسلها.",
            "sticker": "أرسل **ملصقاً** تريد البوت يرسله.",
            "voice": "أرسل **فويس** تريد البوت يرسله.",
        }
        await message.reply(f"{cfg.BOT_SYMBOL} **الخطوة 3/3:** {hints[kind]}")

    elif state["step"] == "content":
        kind = state.get("kind")
        trigger = state.get("trigger")
        content = None

        if kind == "text":
            content = text
        elif kind == "photo":
            if message.photo:
                content = message.photo.file_id
            else:
                content = text
        elif kind == "sticker":
            if message.sticker:
                content = message.sticker.file_id
            else:
                del WIZARD_STEPS[uid]
                return await message.reply(f"{cfg.BOT_SYMBOL} **أرسل ملصقاً فعلياً.**")
        elif kind == "voice":
            if message.voice:
                content = message.voice.file_id
            else:
                del WIZARD_STEPS[uid]
                return await message.reply(f"{cfg.BOT_SYMBOL} **أرسل فويس فعلياً.**")

        if not content:
            del WIZARD_STEPS[uid]
            return await message.reply(f"{cfg.BOT_SYMBOL} **لم أتمكن من حفظ المحتوى.**")

        data = _get_plugins(message.chat.id)
        data[trigger] = {"kind": kind, "content": content}
        _save_plugins(message.chat.id, data)
        del WIZARD_STEPS[uid]

        await message.reply(
            f"{cfg.BOT_SYMBOL} ✅ **تم حفظ الميزة!**\n\n"
            f"🔑 الكلمة المحفزة: `{trigger}`\n"
            f"📦 نوع الرد: **{text if kind != 'text' else 'نص'}**\n\n"
            f"الآن عندما يكتب أي عضو `{trigger}` سيردّ البوت تلقائياً."
        )


# ═══════════════════════════════════════════════════════════════════
#  حذف ميزة
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"حذف ميزة\s+(.+)"))
async def del_plugin(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_ADMIN:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")

    import re
    m = re.search(r"حذف ميزة\s+(.+)", message.text, re.DOTALL)
    trigger = m.group(1).strip() if m else ""
    if not trigger:
        return

    if _del_plugin(message.chat.id, trigger):
        await message.reply(f"{cfg.BOT_SYMBOL} تم حذف الميزة: `{trigger}` ✓")
    else:
        await message.reply(f"{cfg.BOT_SYMBOL} لا توجد ميزة بهذه الكلمة: `{trigger}`")


# ═══════════════════════════════════════════════════════════════════
#  قائمة الميزات
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter("قائمة الميزات"))
async def list_plugins(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    data = _get_plugins(message.chat.id)
    if not data:
        return await message.reply(f"{cfg.BOT_SYMBOL} **لا توجد ميزات مضافة بعد.**")

    type_labels = {"text": "📝 نص", "photo": "🖼 صورة", "sticker": "🎭 ستيكر", "voice": "🔊 صوت"}
    lines = [f"{cfg.BOT_SYMBOL} **الميزات المضافة في هذه المجموعة:**\n"]
    for i, (trigger, val) in enumerate(data.items(), 1):
        label = type_labels.get(val.get("kind", "text"), "📝")
        lines.append(f"{i}. `{trigger}` ← {label}")

    await message.reply("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════
#  تطبيق الميزات — group=20
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.text, group=20)
async def apply_plugins(client: Client, message: Message):
    if not message.from_user or not message.text:
        return
    if not is_chat_active(message.chat.id):
        return
    if message.text.startswith(cfg.BOT_PREFIX):
        return

    data = _get_plugins(message.chat.id)
    if not data:
        return

    text = message.text.strip()
    plugin = data.get(text)
    if not plugin:
        return

    kind = plugin.get("kind", "text")
    content = plugin.get("content", "")

    try:
        if kind == "text":
            await message.reply(content)
        elif kind == "photo":
            await client.send_photo(message.chat.id, content, reply_to_message_id=message.id)
        elif kind == "sticker":
            await client.send_sticker(message.chat.id, content, reply_to_message_id=message.id)
        elif kind == "voice":
            await client.send_voice(message.chat.id, content, reply_to_message_id=message.id)
    except Exception as e:
        await message.reply(f"{cfg.BOT_SYMBOL} فشل تنفيذ الميزة: `{e}`")
