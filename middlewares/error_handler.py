import logging
import traceback
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config.settings import ADMIN_IDS
from utils.notifications import notification_manager

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware لمعالجة الأخطاء بشكل مركزي (v2.3)
    يمنع توقف البوت ويقوم بتسجيل الـ Stack Trace الكامل وإخطار الأدمن
    """
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            user_id = event.from_user.id if hasattr(event, 'from_user') and event.from_user else "Unknown"
            full_traceback = traceback.format_exc()
            
            # تسجيل الخطأ في ملف الجول (Log File)
            logger.critical(f"CRITICAL ERROR for user {user_id}:\n{full_traceback}")
            
            # إخطار جميع الأدمنز (UF-03)
            bot = data.get('bot')
            if bot and ADMIN_IDS:
                try:
                    # Fixed L-01: Unified parse_mode to HTML
                    error_report = (
                        f"🚨 <b>خطأ حرج في النظام!</b>\n\n"
                        f"👤 المستخدم: <code>{user_id}</code>\n"
                        f"❌ الخطأ: <code>{str(e)}</code>\n\n"
                        f"ℹ️ تم تسجيل تفاصيل الخطأ (Stack Trace) في ملفات السجل (Logs) على الخادم."
                    )
                    await notification_manager.notify_admins(bot, error_report)
                except Exception as notify_error:
                    logger.error(f"Failed to notify admins about error: {notify_error}")
            
            # إخطار المستخدم بطريقة ودية
            friendly_msg = "⚠️ عذراً، حدث خطأ فني غير متوقع. تم إبلاغ الإدارة تلقائياً وسنقوم بإصلاحه قريباً."
            try:
                if isinstance(event, Message):
                    await event.answer(friendly_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(friendly_msg, show_alert=True)
            except Exception:
                pass
            
            return None
