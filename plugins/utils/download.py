import os
import re
import uuid
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from config import cfg, ytdb, sounddb
from helpers.permissions import get_user_rank, is_chat_active
from helpers.utils import get_chat_setting, set_chat_setting, run_in_thread


def prefix_filter(cmd: str):
    return filters.regex(rf"^{cfg.BOT_PREFIX}\s+{cmd}") & filters.group


# ═══════════════════════════════════════════════════════════════════
#  أدوات مساعدة مشتركة
# ═══════════════════════════════════════════════════════════════════

def _unique_path(ext: str = "mp3") -> str:
    os.makedirs("downloads", exist_ok=True)
    return f"downloads/{uuid.uuid4().hex}.{ext}"


async def _ytdlp(url: str, audio_only: bool = True) -> tuple[str | None, str]:
    import yt_dlp
    ext = "mp3" if audio_only else "mp4"
    out = _unique_path(ext)

    ydl_opts: dict = {
        "outtmpl": out.replace(f".{ext}", ".%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts["format"] = "best[filesize<50M]/bestvideo[filesize<50M]+bestaudio/best"

    def _dl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)
            if audio_only and not fname.endswith(".mp3"):
                fname = os.path.splitext(fname)[0] + ".mp3"
            return fname, info.get("title", "Unknown")

    try:
        return await run_in_thread(_dl)
    except Exception as e:
        return None, str(e)


async def _search_youtube(query: str, limit: int = 4) -> list[dict]:
    def _do():
        from youtube_search import YoutubeSearch
        results = YoutubeSearch(query, max_results=limit).to_dict()
        return results

    try:
        return await run_in_thread(_do)
    except Exception:
        return []


def _yt_url(vid_id: str) -> str:
    return f"https://www.youtube.com/watch?v={vid_id}"


def _cache_get(db, key: str) -> str | None:
    try:
        return db.get(key)
    except Exception:
        return None


def _cache_set(db, key: str, value: str):
    try:
        db.set(key, value)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  يوتيوب — بحث بالكلمة (بسيط)
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"بحث\s+(.+)|يوت\s+(.+)"))
async def yt_quick_search(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "youtube_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} تحميل يوتيوب معطّل.")

    m = re.search(r"(?:بحث|يوت)\s+(.+)", message.text, re.DOTALL)
    query = m.group(1).strip() if m else ""
    if not query:
        return

    cached = _cache_get(ytdb, f"quick:{query}")
    if cached:
        return await message.reply_audio(cached, title=query)

    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري البحث والتحميل... 🔍")
    results = await _search_youtube(query, 1)
    if not results:
        return await msg.edit(f"{cfg.BOT_SYMBOL} **ما لقيت نتائج.**")

    url = _yt_url(results[0].get("id", ""))
    await msg.edit(f"{cfg.BOT_SYMBOL} وجدت: **{results[0].get('title','')}**\nجاري التحميل... ⬇️")
    filename, title = await _ytdlp(url, audio_only=True)

    if not filename or not os.path.exists(filename):
        return await msg.edit(f"{cfg.BOT_SYMBOL} **فشل التحميل:** `{title}`")
    try:
        sent = await client.send_audio(
            message.chat.id, filename, title=title,
            reply_to_message_id=message.id,
        )
        _cache_set(ytdb, f"quick:{query}", sent.audio.file_id)
        await msg.delete()
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **فشل الرفع:** `{e}`")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


# ═══════════════════════════════════════════════════════════════════
#  يوتيوب — بحث بالكلمة (4 نتائج بأزرار)
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"يوتيوب\s+(?!https?://)(.+)"))
async def yt_search_inline(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "youtube_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} تحميل يوتيوب معطّل.")

    m = re.search(r"يوتيوب\s+(.+)", message.text, re.DOTALL)
    query = m.group(1).strip() if m else ""
    if not query:
        return

    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري البحث في يوتيوب... 🔍")
    results = await _search_youtube(query, 4)
    if not results:
        return await msg.edit(f"{cfg.BOT_SYMBOL} **ما لقيت نتائج.**")

    buttons = []
    for r in results:
        vid_id = r.get("id", "")
        title = r.get("title", "")[:50]
        duration = r.get("duration", "")
        buttons.append([
            InlineKeyboardButton(
                f"🎵 {title} [{duration}]",
                callback_data=f"ytdl:audio:{vid_id}",
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                f"🎬 تحميل فيديو",
                callback_data=f"ytdl:video:{vid_id}",
            )
        ])

    await msg.edit(
        f"{cfg.BOT_SYMBOL} **نتائج البحث عن:** `{query}`\nاختر:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_callback_query(filters.regex(r"^ytdl:(audio|video):(.+)$"))
async def yt_download_cb(client: Client, callback: CallbackQuery):
    m = re.match(r"^ytdl:(audio|video):(.+)$", callback.data)
    if not m:
        return
    kind = m.group(1)
    vid_id = m.group(2)
    url = _yt_url(vid_id)
    audio_only = kind == "audio"

    cache_key = f"{'a' if audio_only else 'v'}:{vid_id}"
    cached = _cache_get(ytdb, cache_key)
    if cached:
        await callback.message.delete()
        if audio_only:
            await client.send_audio(callback.message.chat.id, cached)
        else:
            await client.send_video(callback.message.chat.id, cached)
        return await callback.answer("✅ من الكاش")

    await callback.answer("جاري التحميل... ⬇️")
    await callback.message.edit_text(f"{cfg.BOT_SYMBOL} جاري التحميل... ⬇️")
    filename, title = await _ytdlp(url, audio_only=audio_only)

    if not filename or not os.path.exists(filename):
        return await callback.message.edit_text(f"{cfg.BOT_SYMBOL} **فشل التحميل:** `{title}`")
    try:
        if audio_only:
            sent = await client.send_audio(callback.message.chat.id, filename, title=title)
            _cache_set(ytdb, cache_key, sent.audio.file_id)
        else:
            sent = await client.send_video(callback.message.chat.id, filename, caption=title)
            _cache_set(ytdb, cache_key, sent.video.file_id)
        await callback.message.delete()
    except Exception as e:
        await callback.message.edit_text(f"{cfg.BOT_SYMBOL} **فشل الرفع:** `{e}`")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


# ═══════════════════════════════════════════════════════════════════
#  يوتيوب — رابط مباشر
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"يوتيوب\s+(https?://\S+)"))
async def youtube_audio_url(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "youtube_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} تحميل يوتيوب معطّل.")

    url = re.search(r"https?://\S+", message.text).group(0)
    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري التحميل... ⬇️")
    filename, title = await _ytdlp(url, audio_only=True)

    if not filename or not os.path.exists(filename):
        return await msg.edit(f"{cfg.BOT_SYMBOL} **فشل التحميل:** `{title}`")
    try:
        await msg.edit(f"{cfg.BOT_SYMBOL} جاري الرفع... 📤")
        await client.send_audio(
            message.chat.id, filename, title=title,
            reply_to_message_id=message.id,
        )
        await msg.delete()
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **فشل الرفع:** `{e}`")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


# ═══════════════════════════════════════════════════════════════════
#  فيديو — رابط مباشر
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"فيديو\s+(https?://\S+)"))
async def youtube_video_url(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "youtube_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} تحميل يوتيوب معطّل.")

    url = re.search(r"https?://\S+", message.text).group(0)
    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري تحميل الفيديو... ⬇️")
    filename, title = await _ytdlp(url, audio_only=False)

    if not filename or not os.path.exists(filename):
        return await msg.edit(f"{cfg.BOT_SYMBOL} **فشل التحميل:** `{title}`")
    try:
        await msg.edit(f"{cfg.BOT_SYMBOL} جاري الرفع... 📤")
        await client.send_video(
            message.chat.id, filename, caption=title,
            reply_to_message_id=message.id,
        )
        await msg.delete()
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **فشل الرفع:** `{e}`")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


# ═══════════════════════════════════════════════════════════════════
#  تيك توك
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"تيك\s+(https?://\S+)"))
async def tiktok_download(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "tiktok_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} تحميل تيك توك معطّل.")

    url = re.search(r"https?://\S+", message.text).group(0)
    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري تحميل من تيك توك... ⬇️")
    filename, title = await _ytdlp(url, audio_only=False)

    if not filename or not os.path.exists(filename):
        return await msg.edit(f"{cfg.BOT_SYMBOL} **فشل التحميل:** `{title}`")
    try:
        await msg.edit(f"{cfg.BOT_SYMBOL} جاري الرفع... 📤")
        await client.send_video(
            message.chat.id, filename, caption="🎵 تيك توك",
            reply_to_message_id=message.id,
        )
        await msg.delete()
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **فشل الرفع:** `{e}`")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


# ═══════════════════════════════════════════════════════════════════
#  ساوند كلاود — بحث أو رابط
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"ساوند\s+(.+)"))
async def soundcloud_handler(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if not get_chat_setting(message.chat.id, "soundcloud_enabled", True):
        return await message.reply(f"{cfg.BOT_SYMBOL} تحميل SoundCloud معطّل.")

    m = re.search(r"ساوند\s+(.+)", message.text, re.DOTALL)
    query = m.group(1).strip() if m else ""
    if not query:
        return

    is_url = query.startswith("http")
    if is_url:
        url = query
        cache_key = f"sc:{query}"
    else:
        cache_key = f"sc_q:{query}"
        url = None

    cached = _cache_get(sounddb, cache_key)
    if cached:
        return await message.reply_audio(cached)

    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري {'التحميل' if is_url else 'البحث والتحميل'} من SoundCloud... 🎵")

    if not is_url:
        def _sc_search():
            import yt_dlp
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
                    "default_search": "scsearch1"}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch1:{query}", download=False)
                entries = info.get("entries", [info])
                if entries:
                    return entries[0].get("webpage_url", "")
            return ""

        try:
            url = await run_in_thread(_sc_search)
        except Exception:
            url = ""

        if not url:
            return await msg.edit(f"{cfg.BOT_SYMBOL} **ما لقيت نتائج في SoundCloud.**")

    filename, title = await _ytdlp(url, audio_only=True)
    if not filename or not os.path.exists(filename):
        return await msg.edit(f"{cfg.BOT_SYMBOL} **فشل التحميل:** `{title}`")
    try:
        sent = await client.send_audio(
            message.chat.id, filename, title=title,
            reply_to_message_id=message.id,
        )
        _cache_set(sounddb, cache_key, sent.audio.file_id)
        await msg.delete()
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **فشل الرفع:** `{e}`")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


# ═══════════════════════════════════════════════════════════════════
#  شازام — تعرف على الأغنية أو ابحث عن كلماتها
# ═══════════════════════════════════════════════════════════════════

@Client.on_message(prefix_filter(r"شازام\s*(.*)"))
async def shazam_handler(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return

    m = re.search(r"شازام\s*(.*)", message.text, re.DOTALL)
    song_name = (m.group(1) or "").strip() if m else ""

    # شازام [اسم أغنية] — بحث عن كلمات
    if song_name:
        msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري البحث عن كلمات **{song_name}**... 🎵")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.get(
                    "https://api.lyrics.ovh/v1/",
                    params={"q": song_name},
                )
            if r.status_code == 200:
                data = r.json()
                lyrics = data.get("lyrics") or data.get("result", {}).get("lyrics", "")
                if lyrics:
                    short = lyrics[:3000] + ("..." if len(lyrics) > 3000 else "")
                    return await msg.edit(
                        f"🎵 **كلمات:** {song_name}\n\n{short}"
                    )
        except Exception:
            pass

        # محاولة بديلة: Genius-style search
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.get(
                    "https://lyrist.vercel.app/api/" + song_name.replace(" ", "%20")
                )
            if r.status_code == 200:
                data = r.json()
                lyrics = data.get("lyrics", "")
                if lyrics:
                    short = lyrics[:3000] + ("..." if len(lyrics) > 3000 else "")
                    return await msg.edit(
                        f"🎵 **كلمات:** {song_name}\n\n{short}"
                    )
        except Exception:
            pass

        return await msg.edit(f"{cfg.BOT_SYMBOL} **ما لقيت كلمات لهذه الأغنية.**")

    # شازام بدون نص — تعرف على صوت
    reply = message.reply_to_message
    if not reply or not (reply.voice or reply.audio or reply.video_note):
        return await message.reply(
            f"{cfg.BOT_SYMBOL} ردّ على صوت أو فويس للتعرف عليه، "
            f"أو اكتب: `{cfg.BOT_PREFIX} شازام [اسم أغنية]` للحصول على الكلمات."
        )

    msg = await message.reply(f"{cfg.BOT_SYMBOL} جاري التعرف على الأغنية... 🎵")
    file_path = None
    try:
        os.makedirs("downloads", exist_ok=True)
        file_path = await client.download_media(reply, file_name=f"downloads/shazam_{uuid.uuid4().hex}")
        from shazamio import Shazam
        result = await Shazam().recognize(file_path)
        track = (result or {}).get("track")
        if track:
            title = track.get("title", "غير معروف")
            artist = track.get("subtitle", "غير معروف")
            await msg.edit(
                f"{cfg.BOT_SYMBOL} **تم التعرف على الأغنية!** 🎵\n\n"
                f"🎵 **الاسم:** {title}\n🎤 **الفنان:** {artist}"
            )
        else:
            await msg.edit(f"{cfg.BOT_SYMBOL} **ما قدرت أتعرف على الأغنية.**")
    except Exception as e:
        await msg.edit(f"{cfg.BOT_SYMBOL} **خطأ:** `{e}`")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# ═══════════════════════════════════════════════════════════════════
#  تفعيل / تعطيل الخدمات
# ═══════════════════════════════════════════════════════════════════

SERVICES = {
    "يوتيوب": "youtube_enabled",
    "تيك توك": "tiktok_enabled",
    "ساوند كلاود": "soundcloud_enabled",
}


@Client.on_message(prefix_filter(r"تفعيل (يوتيوب|تيك توك|ساوند كلاود)"))
async def enable_service(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    m = re.search(r"تفعيل (يوتيوب|تيك توك|ساوند كلاود)", message.text)
    if not m:
        return
    svc = m.group(1)
    key = SERVICES.get(svc)
    if key:
        set_chat_setting(message.chat.id, key, True)
        await message.reply(f"{cfg.BOT_SYMBOL} تم **تفعيل {svc}** ✓")


@Client.on_message(prefix_filter(r"تعطيل (يوتيوب|تيك توك|ساوند كلاود)"))
async def disable_service(client: Client, message: Message):
    if not is_chat_active(message.chat.id):
        return
    if get_user_rank(message.from_user.id, message.chat.id) > cfg.RANK_MOD:
        return await message.reply(f"{cfg.BOT_SYMBOL} **ما عندك صلاحية.**")
    m = re.search(r"تعطيل (يوتيوب|تيك توك|ساوند كلاود)", message.text)
    if not m:
        return
    svc = m.group(1)
    key = SERVICES.get(svc)
    if key:
        set_chat_setting(message.chat.id, key, False)
        await message.reply(f"{cfg.BOT_SYMBOL} تم **تعطيل {svc}** ✓")
