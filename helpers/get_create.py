import aiohttp
from database.redis_client import rdb


async def get_creation_date(user_id: int) -> str:
    cached = rdb.get(f'{user_id}:CreateDate')
    if cached:
        return cached

    url = "https://restore-access.indream.app/regdate"
    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Nicegram/92 CFNetwork/1390 Darwin/22.0.0",
        "x-api-key": "e758fb28-79be-4d1c-af6b-066633ded128",
        "accept-language": "en-US,en;q=0.9"
    }
    data = {"telegramId": user_id}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                date_str = result['data']['date'].replace('-', '/')
                rdb.set(f'{user_id}:CreateDate', date_str)
                return date_str
    except Exception:
        return "غير معروف"
