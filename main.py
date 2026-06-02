import asyncio
import os
import sys
import logging
from pyrogram import Client, idle
from config import cfg
from database.redis_client import rdb, ping as redis_ping, global_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "plugins")


async def main():
    if not cfg.BOT_TOKEN:
        logger.error("BOT_TOKEN غير موجود في ملف .env")
        sys.exit(1)
    if not cfg.API_ID or not cfg.API_HASH:
        logger.error("API_ID أو API_HASH غير موجودين في ملف .env")
        sys.exit(1)

    if not redis_ping():
        logger.error("تعذر الاتصال بـ Redis — تأكد أن السيرفر شغال")
        sys.exit(1)
    logger.info("✅ Redis متصل")

    # ─── تحديث cfg من Redis (اسم البوت ورمزه) ───────────────────
    saved_name = rdb.get(global_key("bot_name"))
    if saved_name:
        cfg.BOT_NAME = saved_name
        cfg.BOT_PREFIX = saved_name
        logger.info(f"📝 اسم البوت محمّل من Redis: {cfg.BOT_NAME}")

    saved_symbol = rdb.get(global_key("bot_symbol"))
    if saved_symbol:
        cfg.BOT_SYMBOL = saved_symbol
        logger.info(f"💎 رمز البوت محمّل من Redis: {cfg.BOT_SYMBOL}")
    # ─────────────────────────────────────────────────────────────

    app = Client(
        "raad_bot",
        api_id=cfg.API_ID,
        api_hash=cfg.API_HASH,
        bot_token=cfg.BOT_TOKEN,
        plugins=dict(root="plugins"),
        workdir=os.path.dirname(__file__),
    )

    async with app:
        me = await app.get_me()
        cfg.BOT_ID = str(me.id)
        logger.info(f"🤖 {cfg.BOT_NAME} يعمل — @{me.username} (ID: {me.id})")
        logger.info(f"👑 المالك: {cfg.OWNER_ID}")

        from plugins.utils.cleanup import auto_cleanup_task
        asyncio.create_task(auto_cleanup_task(app))
        logger.info("🧹 مهمة التنظيف التلقائي تعمل في الخلفية")

        await idle()

    logger.info(f"🛑 {cfg.BOT_NAME} أُوقف.")


if __name__ == "__main__":
    asyncio.run(main())
