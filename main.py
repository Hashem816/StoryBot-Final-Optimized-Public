import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import BOT_TOKEN
from database.manager import db_manager
from middlewares.auth import AuthMiddleware, AdminMiddleware
from middlewares.throttling import ThrottlingMiddleware
from middlewares.error_handler import ErrorHandlerMiddleware

# استيراد الـ Routers
from handlers import (
    admin, user, products, admin_orders, 
    payments, admin_modes, admin_stats, 
    admin_broadcast, admin_coupons, admin_audit, language
)

# إعداد الـ Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global bot instance for notifications
bot_instance: Bot = None

async def shutdown(bot: Bot, dp: Dispatcher):
    """إيقاف البوت بشكل آمن (Fixed M-02)"""
    logger.info("Shutting down...")
    try:
        # Fixed M-02: Graceful Shutdown for DB and API Session
        from utils.api_client import api_client
        await api_client.close_session()
        
        await dp.stop_polling()
        await bot.session.close()
        # Close database pool
        await db_manager.close()
        logger.info("Bot stopped successfully!")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

async def main():
    """الدالة الرئيسية لتشغيل البوت v2.3 REBORN"""
    global bot_instance
    
    # التحقق من وجود التوكن (H-06)
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment variables!")
        sys.exit(1)

    # تهيئة قاعدة البيانات
    await db_manager.init_db()
    
    # تهيئة البوت والـ Dispatcher
    # Fixed: Support for Proxy (for restricted environments like PythonAnywhere)
    from os import getenv
    PROXY_URL = getenv("PROXY_URL")
    
    if PROXY_URL:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=PROXY_URL)
        bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
        logger.info(f"Using Proxy: {PROXY_URL}")
    else:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        
    bot_instance = bot
    dp = Dispatcher(storage=MemoryStorage())

    # NC-01: إعداد الـ Middlewares بالترتيب الصحيح
    # H-02: Unified all middlewares to outer_middleware for consistency.
    
    # 1. ErrorHandlerMiddleware (يجب أن يكون الأبعد لالتقاط كل شيء)
    dp.update.outer_middleware(ErrorHandlerMiddleware())
    
    # 2. AuthMiddleware (يوفر بيانات المستخدم للمراحل التالية)
    dp.update.outer_middleware(AuthMiddleware())
    
    # 3. ThrottlingMiddleware (حماية من السبام)
    dp.update.outer_middleware(ThrottlingMiddleware())
    
    # 4. AdminMiddleware (التحقق من الصلاحيات الإدارية)
    dp.update.outer_middleware(AdminMiddleware())

    # تسجيل الـ Routers (M-02, M-12)
    dp.include_router(admin.router)
    dp.include_router(admin_orders.router)
    dp.include_router(admin_coupons.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_audit.router)
    dp.include_router(admin_modes.router)
    dp.include_router(admin_stats.router)
    dp.include_router(products.router)
    dp.include_router(payments.router)
    dp.include_router(language.router)
    dp.include_router(user.router)

    logger.info("Starting Story Bot v2.3 REBORN...")
    
    # Fixed M-04: Support for Webhook and Polling
    from os import getenv
    USE_WEBHOOK = getenv("USE_WEBHOOK", "0") == "1"
    
    if USE_WEBHOOK:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web
        
        WEBHOOK_URL = getenv("WEBHOOK_URL")
        WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
        HOST = getenv("HOST", "0.0.0.0")
        PORT = int(getenv("PORT", "8080"))
        
        await bot.set_webhook(url=f"{WEBHOOK_URL}{WEBHOOK_PATH}", drop_pending_updates=True)
        
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        
        logger.info(f"Starting Webhook on {HOST}:{PORT}...")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, HOST, PORT)
        await site.start()
        
        # Keep running
        try:
            while True: await asyncio.sleep(3600)
        finally:
            await shutdown(bot, dp)
    else:
        # حذف الـ Webhook القديم وبدء الـ Polling
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot)
        finally:
            await shutdown(bot, dp)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
