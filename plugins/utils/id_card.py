import random
import os
from io import BytesIO
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.raw.functions.users import GetFullUser
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from config import cfg
from database.redis_client import rdb, chat_key, user_key
from helpers.permissions import get_user_rank, is_chat_active
from helpers.get_create import get_creation_date


custom_ids = [
    '''
- ᴜѕᴇʀɴᴀᴍᴇ ➣ {اليوزر} .
- ᴍѕɢѕ ➣ {الرسائل} .
- ѕᴛᴀᴛѕ ➣ {الرتبه} .
- ʏᴏᴜʀ ɪᴅ ➣ {الايدي} .
- ᴇᴅɪᴛ ᴍsɢ ➣ {التعديل} .
- ᴅᴇᴛᴀɪʟs ➣ {التفاعل} .
{البايو}
''', '''
• USE 𖦹 {اليوزر}
• MSG 𖥳 {الرسائل}
• STA 𖦹 {الرتبه}
• iD 𖥳 {الايدي}
{البايو}
''', '''
➞: 𝒔𝒕𝒂𓂅 {اليوزر} 𓍯
➞: 𝒖𝒔𝒆𝒓𓂅 {المعرف} 𓍯
➞: 𝒎𝒔𝒈𝒆𓂅 {الرسائل} 𓍯
➞: 𝒊𝒅 𓂅 {الايدي} 𓍯
{البايو}
''', '''
♡ : 𝐼𝐷 𖠀 {الايدي} .
♡ : 𝑈𝑆𝐸𝑅 𖠀 {اليوزر} .
♡ : 𝑀𝑆𝐺𝑆 𖠀 {الرسائل} .
♡ : 𝑆𝑇𝐴𝑇𝑆 𖠀 {الرتبه} .
♡ : 𝐸𝐷𝐼𝑇  𖠀 {التعديل} .
{البايو}
''', '''
- الايـدي || {الايدي}.
• الاسـم  || {الاسم}.
• المُعرف || {اليوزر}.
• الرُتبـه || {الرتبه}.
• الرسائل || {الرسائل}.
{البايو}
''', '''
⌁ NaMe ⇨ {الاسم}
⌁ Use ⇨ {اليوزر}
⌁ Msg ⇨ {الرسائل}
⌁ Sta ⇨ {الرتبه}
⌁ iD ⇨ {الايدي}
{البايو}
''', '''
𖡋 𝐔𝐒𝐄 ⌯  {اليوزر}
𖡋 𝐌𝐒𝐆 ⌯  {الرسائل}
𖡋 𝐒𝐓𝐀 ⌯  {الرتبه}
𖡋 𝐈𝐃 ⌯  {الايدي}
𖡋 𝐄𝐃𝐈𝐓 ⌯  {التعديل}
{البايو}'''
]

comments = [
    'تيكفه لاتكتب ايدي',
    'يع',
    'جبر',
    'احلى من يكتب ايدي',
    'افخم ايدي',
    'لحد يرسل ايدي من بعده',
    'يلبييه اطلق ايدي',
    'ازق ايدي',
    'لعد تكتب ايدي',
    'للاسف ايديك تلوث بصري ):',
    'جابك الله انت وأيديك على شكل جبر خاطر لقلبّي'
]


def _get_rank_name(uid: int, cid: int) -> str:
    rank_num = get_user_rank(uid, cid)
    return cfg.RANK_NAMES.get(rank_num, "عضو")


def _get_tfa3l(msgs: int) -> str:
    if msgs > 10000:
        return 'اسطورة التلي'
    elif msgs > 5000:
        return 'اسطورة التفاعل'
    elif msgs > 2500:
        return 'متفاعل'
    elif msgs > 750:
        return 'تفاعل متوسط'
    elif msgs > 500:
        return 'يجي منك'
    elif msgs > 50:
        return 'شد حيلك'
    else:
        return 'تفاعل صفر'


@Client.on_message(filters.group, group=9)
async def addmsgCount(c: Client, m: Message):
    if not m.from_user:
        return
    if rdb.get(f'{m.from_user.id}:mute:{m.chat.id}{cfg.BOT_ID}'):
        return
    key = f'{cfg.BOT_ID}{m.chat.id}:TotalMsgs:{m.from_user.id}'
    current = rdb.get(key)
    if not current:
        rdb.set(key, 1)
    else:
        rdb.set(key, int(current) + 1)
    rdb.set(f"{m.from_user.id}:bankName", m.from_user.first_name[:25])


@Client.on_edited_message(filters.group, group=10)
async def addeditedmsgCount(c: Client, m: Message):
    if not m.from_user:
        return
    if rdb.get(f'{m.from_user.id}:mute:{m.chat.id}{cfg.BOT_ID}'):
        return
    key = f'{m.chat.id}:TotalEDMsgs:{m.from_user.id}{cfg.BOT_ID}'
    current = rdb.get(key)
    if not current:
        rdb.set(key, 1)
    else:
        rdb.set(key, int(current) + 1)


@Client.on_message(filters.text & filters.group, group=11)
async def idCardHandler(c: Client, m: Message):
    if not m.from_user:
        return
    if not is_chat_active(m.chat.id):
        return
    if rdb.get(f'{m.from_user.id}:mute:{m.chat.id}{cfg.BOT_ID}'):
        return
    if rdb.get(f'{m.from_user.id}:mute:{cfg.BOT_ID}'):
        return

    text = m.text
    if text.startswith(f'{cfg.BOT_PREFIX} '):
        text = text[len(cfg.BOT_PREFIX) + 1:]

    k = cfg.BOT_SYMBOL

    if text == 'ايدي' and not m.reply_to_message:
        if rdb.get(f'{m.chat.id}:disableID:{cfg.BOT_ID}'):
            return

        id_template = rdb.get(f'{m.chat.id}:customID:{cfg.BOT_ID}') or \
                      rdb.get(f'customID:{cfg.BOT_ID}') or \
                      '''
𖡋 𝐔𝐒𝐄 ⌯  {اليوزر}
𖡋 𝐌𝐒𝐆 ⌯  {الرسائل}
𖡋 𝐒𝐓𝐀 ⌯  {الرتبه}
𖡋 𝐈𝐃 ⌯  {الايدي}
𖡋 𝐄𝐃𝐈𝐓 ⌯  {التعديل}
𖡋 𝐂𝐑  ⌯  {الانشاء}
{البايو}'''

        if m.from_user.usernames:
            username = ''.join(f"@{u.username} " for u in m.from_user.usernames)
        elif m.from_user.username:
            username = f'@{m.from_user.username}'
        else:
            username = 'مافي يوزر'

        rank = _get_rank_name(m.from_user.id, m.chat.id)
        msg_raw = rdb.get(f'{cfg.BOT_ID}{m.chat.id}:TotalMsgs:{m.from_user.id}')
        msg = int(msg_raw) if msg_raw else 0
        edit_raw = rdb.get(f'{m.chat.id}:TotalEDMsgs:{m.from_user.id}{cfg.BOT_ID}')
        edits = int(edit_raw) if edit_raw else 0
        name = m.from_user.first_name
        create = await get_creation_date(m.from_user.id)
        tfa3l = _get_tfa3l(msg)
        comment = random.choice(comments)

        try:
            get_chat = await c.get_chat(m.from_user.id)
            bio = get_chat.bio or 'مافي بايو'
        except Exception:
            bio = 'مافي بايو'

        card_text = id_template \
            .replace('{الاسم}', name) \
            .replace('{اليوزر}', username) \
            .replace('{الرسائل}', str(msg)) \
            .replace('{التعديل}', str(edits)) \
            .replace('{الانشاء}', create) \
            .replace('{البايو}', bio) \
            .replace('{الايدي}', f'`{m.from_user.id}`') \
            .replace('{الرتبه}', rank) \
            .replace('{التفاعل}', tfa3l) \
            .replace('{تعليق}', comment)

        if rdb.get(f'{m.chat.id}:disableIDPHOTO:{cfg.BOT_ID}') or not m.from_user.photo:
            await m.reply(card_text, disable_web_page_preview=True)
            return

        try:
            get_user = await c.invoke(GetFullUser(id=await c.resolve_peer(m.from_user.id)))
            photo = get_user.full_user.profile_photo
            video_sizes = photo.video_sizes if photo else None

            if video_sizes:
                video = video_sizes[-2] if len(video_sizes) == 3 else video_sizes[-1]
                file = BytesIO()
                cache_key = f"{photo.access_hash}:{m.from_user.id}"
                cached_id = rdb.get(cache_key)
                if cached_id:
                    await m.reply_animation(cached_id, caption=card_text)
                    return
                async for chunk in c.stream_media(
                    message=FileId(
                        file_type=FileType.PHOTO,
                        dc_id=photo.dc_id,
                        media_id=photo.id,
                        access_hash=photo.access_hash,
                        file_reference=photo.file_reference,
                        thumbnail_source=ThumbnailSource.THUMBNAIL,
                        thumbnail_file_type=FileType.PHOTO,
                        thumbnail_size=video.type,
                        volume_id=0, local_id=0
                    ).encode()
                ):
                    file.write(chunk)
                file.name = f'{m.from_user.id}vid{m.chat.id}.mp4'
                sent = await m.reply_animation(file, caption=card_text)
                rdb.set(cache_key, sent.animation.file_id, ex=3600)
            else:
                file_id = FileId(
                    file_type=FileType.PHOTO,
                    dc_id=photo.dc_id,
                    media_id=photo.id,
                    access_hash=photo.access_hash,
                    file_reference=photo.file_reference,
                    thumbnail_source=ThumbnailSource.THUMBNAIL,
                    thumbnail_file_type=FileType.PHOTO,
                    thumbnail_size=photo.sizes[0].type,
                    volume_id=0, local_id=0
                ).encode()
                await m.reply_photo(file_id, caption=card_text)
        except Exception:
            await m.reply(card_text, disable_web_page_preview=True)

    elif text == 'ايدي' and m.reply_to_message and m.reply_to_message.from_user:
        await m.reply(f'الايدي ↢ ( `{m.reply_to_message.from_user.id}` )')

    elif text == 'ايديي':
        await m.reply(f'( `{m.from_user.id}` )')

    elif text.startswith('افتار ') and len(text.split()) == 2:
        if rdb.get(f'{m.chat.id}:disableAV:{cfg.BOT_ID}'):
            return
        target = text.split()[1]
        try:
            uid = int(target) if target.lstrip('-').isdigit() else target
            get = await c.get_chat(uid)
            if get.photo:
                async for p in c.get_chat_photos(get.id, limit=1):
                    photo_id = p.file_id
                caption = f'`{get.bio}`' if get.bio else None
                await m.reply_photo(photo_id, caption=caption)
        except Exception:
            pass


@Client.on_message(filters.new_chat_members, group=1)
async def addContact(c: Client, m: Message):
    if not m.from_user:
        return
    for member in m.new_chat_members:
        if m.from_user.id != member.id:
            key = f'{m.chat.id}TotalContacts{m.from_user.id}{cfg.BOT_ID}'
            current = rdb.get(key)
            if not current:
                rdb.set(key, 1)
            else:
                rdb.set(key, int(current) + 1)
