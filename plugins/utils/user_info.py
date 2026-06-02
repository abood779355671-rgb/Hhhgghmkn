from pyrogram import Client, filters
from pyrogram.types import Message
from config import cfg
from database.redis_client import rdb, chat_key, user_key
from helpers.permissions import get_user_rank, is_chat_active
from helpers.get_create import get_creation_date


def _rank_name(uid: int, cid: int) -> str:
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


def _get_top(entries: list) -> list:
    return sorted(entries, key=lambda x: x.get('msgs', 0), reverse=True)


def _get_emoji(pos: int) -> str:
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    return medals.get(pos, f'{pos}. ')


@Client.on_message(filters.text & filters.group, group=12)
async def user_info_handler(c: Client, m: Message):
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
    uid = m.from_user.id
    cid = m.chat.id

    if text == 'معلوماتي':
        msg_raw = rdb.get(f'{cfg.BOT_ID}{cid}:TotalMsgs:{uid}')
        msgs = int(msg_raw) if msg_raw else 0
        edit_raw = rdb.get(f'{cid}:TotalEDMsgs:{uid}{cfg.BOT_ID}')
        edits = int(edit_raw) if edit_raw else 0
        contacts_raw = rdb.get(f'{cid}TotalContacts{uid}{cfg.BOT_ID}')
        contacts = int(contacts_raw) if contacts_raw else 0
        tfa3l = _get_tfa3l(msgs)

        if m.from_user.usernames:
            username = ''.join(f"@{u.username} " for u in m.from_user.usernames)
        elif m.from_user.username:
            username = f'@{m.from_user.username}'
        else:
            username = 'مافي يوزر'

        rank = _rank_name(uid, cid)
        info = f'''
{k} **المعلومات**
❁ الاسم ↼ {m.from_user.mention}
❁ اليوزر ↼ {username}
❁ الايدي ↼ `{uid}`
❁ الرتبه ↼ {rank}
┄─┅═ـ═┅─┄
{k} **احصائيات الرسايل**
❁ الرسايل ↼ {msgs:,}
❁ التعديل ↼ {edits:,}
❁ الجهات ↼ {contacts}
❁ التفاعل ↼ {tfa3l}
'''
        await m.reply(info)

    elif text == 'كشف' and m.reply_to_message and m.reply_to_message.from_user:
        target = m.reply_to_message.from_user
        msg_raw = rdb.get(f'{cfg.BOT_ID}{cid}:TotalMsgs:{target.id}')
        msgs = int(msg_raw) if msg_raw else 0
        rank = _rank_name(target.id, cid)

        if target.usernames:
            username = ''.join(f"@{u.username} " for u in target.usernames)
        elif target.username:
            username = f'@{target.username}'
        else:
            username = 'مافي يوزر'

        try:
            member = await m.chat.get_member(target.id)
            from pyrogram.enums import ChatMemberStatus
            status_map = {
                ChatMemberStatus.OWNER: 'مالك المجموعة',
                ChatMemberStatus.ADMINISTRATOR: 'مشرف',
                ChatMemberStatus.RESTRICTED: 'مقيد',
                ChatMemberStatus.LEFT: 'طالع',
                ChatMemberStatus.MEMBER: 'عضو',
                ChatMemberStatus.BANNED: 'محظور',
            }
            group_status = status_map.get(member.status, 'عضو')
        except Exception:
            group_status = 'غير معروف'

        info = f'''
{k} **كشف العضو**
❁ الاسم ↼ {target.mention}
❁ اليوزر ↼ {username}
❁ الايدي ↼ `{target.id}`
❁ رتبته بالبوت ↼ {rank}
❁ رتبته بالمجموعة ↼ {group_status}
❁ الرسايل ↼ {msgs:,}
'''
        await m.reply(info)

    elif text == 'كشف' and not m.reply_to_message:
        await m.reply(f'{k} ردّ على رسالة العضو أو ارسل منشنه أو ايديه')

    elif text == 'صلاحياتي':
        rank = _rank_name(uid, cid)
        rank_num = get_user_rank(uid, cid)
        perms_list = []
        if rank_num <= cfg.RANK_OWNER:
            perms_list = ['تفعيل/تعطيل البوت', 'جميع الصلاحيات', 'نقل الملكية']
        elif rank_num <= cfg.RANK_DEV:
            perms_list = ['جميع أوامر المطور', 'تعيين الرتب', 'الأوامر العالمية']
        elif rank_num <= cfg.RANK_DEV2:
            perms_list = ['أوامر نائب المطور', 'تعيين الإدارة']
        elif rank_num <= cfg.RANK_MOD:
            perms_list = ['أوامر المدير', 'تعيين الإداريين', 'الحظر الكامل']
        elif rank_num <= cfg.RANK_ADMIN:
            perms_list = ['أوامر الإداري', 'كتم وطرد الأعضاء', 'قفل وفتح المجموعة']
        else:
            perms_list = ['أوامر العضو الأساسية']

        perms_text = '\n'.join(f'  ✓ {p}' for p in perms_list)
        await m.reply(f'{k} **صلاحياتك**\n{k} رتبتك ↼ {rank}\n\n**الصلاحيات:**\n{perms_text}')

    elif text == 'صلاحياته' and m.reply_to_message and m.reply_to_message.from_user:
        target = m.reply_to_message.from_user
        rank = _rank_name(target.id, cid)
        rank_num = get_user_rank(target.id, cid)
        perms_list = []
        if rank_num <= cfg.RANK_OWNER:
            perms_list = ['تفعيل/تعطيل البوت', 'جميع الصلاحيات', 'نقل الملكية']
        elif rank_num <= cfg.RANK_DEV:
            perms_list = ['جميع أوامر المطور', 'تعيين الرتب', 'الأوامر العالمية']
        elif rank_num <= cfg.RANK_DEV2:
            perms_list = ['أوامر نائب المطور', 'تعيين الإدارة']
        elif rank_num <= cfg.RANK_MOD:
            perms_list = ['أوامر المدير', 'تعيين الإداريين', 'الحظر الكامل']
        elif rank_num <= cfg.RANK_ADMIN:
            perms_list = ['أوامر الإداري', 'كتم وطرد الأعضاء', 'قفل وفتح المجموعة']
        else:
            perms_list = ['أوامر العضو الأساسية']

        perms_text = '\n'.join(f'  ✓ {p}' for p in perms_list)
        await m.reply(f'{k} **صلاحيات** {target.mention}\n{k} رتبته ↼ {rank}\n\n**الصلاحيات:**\n{perms_text}')

    elif text in ('المتفاعلين', 'توب المتفاعلين'):
        users_keys = rdb.keys(f"{cfg.BOT_ID}{cid}:TotalMsgs:*")
        entries = []
        for ukey in users_keys:
            try:
                user_id = int(ukey.split("TotalMsgs:")[1])
                msgs_val = rdb.get(ukey)
                name = rdb.get(f"{user_id}:bankName") or str(user_id)
                entries.append({"name": name, "id": user_id, "msgs": int(msgs_val)})
            except Exception:
                pass
        top = _get_top(entries)
        result = "**- توب اكثر 20 متفاعل :**\n━━━━━━━━━\n"
        for i, entry in enumerate(top[:20], 1):
            emoji = _get_emoji(i)
            result += f"{emoji} {entry['msgs']:,} ↼ [{entry['name']}](tg://user?id={entry['id']})\n"
        await c.send_message(cid, result, disable_web_page_preview=True, reply_to_message_id=m.id)

    elif text in ('ترتيبي', 'تفاعلي'):
        users_keys = rdb.keys(f"{cfg.BOT_ID}{cid}:TotalMsgs:*")
        entries = []
        for ukey in users_keys:
            try:
                user_id = int(ukey.split("TotalMsgs:")[1])
                msgs_val = rdb.get(ukey)
                entries.append({"id": user_id, "msgs": int(msgs_val)})
            except Exception:
                pass
        top = _get_top(entries)
        ids = [e["id"] for e in top]
        try:
            rank_pos = ids.index(uid) + 1
        except ValueError:
            rank_pos = len(ids) + 1
        msg_raw = rdb.get(f"{cfg.BOT_ID}{cid}:TotalMsgs:{uid}")
        my_msgs = int(msg_raw) if msg_raw else 0
        await m.reply(f"{k} ترتيبك بالمتفاعلين ↢ {rank_pos}\n{k} رسائلك بالتفاعل ↢ {my_msgs:,}")

    elif text == 'مجموعاتي':
        groups = rdb.smembers(f'{uid}:groups')
        if not groups:
            await m.reply(f'{k} ماعندك مجموعات')
        else:
            await m.reply(f'{k} عدد مجموعاتك ↼ ( {len(groups)} )')

    elif text == 'انشائي':
        date = await get_creation_date(uid)
        await m.reply(f'{k} الانشاء ( {date} )')

    elif text == 'الانشاء' and m.reply_to_message and m.reply_to_message.from_user:
        date = await get_creation_date(m.reply_to_message.from_user.id)
        await m.reply(f'{k} الانشاء ( {date} )')

    elif text == 'الانشاء' and not m.reply_to_message:
        date = await get_creation_date(uid)
        await m.reply(f'{k} الانشاء ( {date} )')

    elif text == 'لقبي':
        try:
            member = await m.chat.get_member(uid)
            title = member.custom_title
            if not title:
                await m.reply(f'{k} ماعندك لقب')
            else:
                await m.reply(f'{k} لقبك ↢ ( {title} )')
        except Exception:
            await m.reply(f'{k} ما قدرت اجيب لقبك')

    elif text == 'جهاتي':
        contacts_raw = rdb.get(f'{cid}TotalContacts{uid}{cfg.BOT_ID}')
        contacts = int(contacts_raw) if contacts_raw else 0
        await m.reply(f'{k} عدد جهاتك ↢ {contacts}')

    elif text == 'بايو' and not m.reply_to_message:
        if rdb.get(f'{cid}:disableBio:{cfg.BOT_ID}'):
            return
        try:
            user_chat = await c.get_chat(uid)
            if not user_chat.bio:
                await m.reply(f'{k} ماعندك بايو')
            else:
                await m.reply(f'`{user_chat.bio}`')
        except Exception:
            await m.reply(f'{k} ما قدرت اجيب بايوك')

    elif text == 'بايو' and m.reply_to_message and m.reply_to_message.from_user:
        if rdb.get(f'{cid}:disableBio:{cfg.BOT_ID}'):
            return
        try:
            user_chat = await c.get_chat(m.reply_to_message.from_user.id)
            if not user_chat.bio:
                await m.reply(f'{k} ماعنده بايو')
            else:
                await m.reply(f'`{user_chat.bio}`')
        except Exception:
            await m.reply(f'{k} ما قدرت اجيب بايوه')

    elif text == 'افتاري':
        if rdb.get(f'{cid}:disableAV:{cfg.BOT_ID}'):
            return
        if not m.from_user.photo:
            await m.reply(f'{k} ما قدرت اجيب افتارك، ارسل نقطة بالخاص وارجع جرّب')
            return
        try:
            if m.from_user.username:
                photo = f'http://t.me/{m.from_user.username}'
            else:
                async for p in c.get_chat_photos(uid, limit=1):
                    photo = p.file_id
            try:
                user_chat = await c.get_chat(uid)
                caption = f'`{user_chat.bio}`' if user_chat.bio else None
            except Exception:
                caption = None
            await m.reply_photo(photo, caption=caption)
        except Exception:
            await m.reply(f'{k} ما قدرت اجيب افتارك')

    elif text == 'افتار' and m.reply_to_message and m.reply_to_message.from_user:
        if rdb.get(f'{cid}:disableAV:{cfg.BOT_ID}'):
            return
        target = m.reply_to_message.from_user
        if not target.photo:
            await m.reply(f'{k} مقدر اجيب افتاره، يمكن حاظرني')
            return
        try:
            if target.username:
                photo = f'http://t.me/{target.username}'
            else:
                async for p in c.get_chat_photos(target.id, limit=1):
                    photo = p.file_id
            try:
                user_chat = await c.get_chat(target.id)
                caption = f'`{user_chat.bio}`' if user_chat.bio else None
            except Exception:
                caption = None
            await m.reply_photo(photo, caption=caption)
        except Exception:
            await m.reply(f'{k} ما قدرت اجيب افتاره')
