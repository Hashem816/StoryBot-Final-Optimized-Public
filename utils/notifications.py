# نظام الإشعارات الموحد - v2.3 REBORN
import logging
from typing import Optional, List, Any
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from config.settings import ADMIN_IDS

logger = logging.getLogger(__name__)

class NotificationManager:
    """مدير الإشعارات المركزي (Fixed L-01: Unified to HTML)"""
    
    @staticmethod
    async def notify_user(bot: Bot, user_id: int, message: str, parse_mode: str = "HTML", reply_markup=None) -> bool:
        """إرسال إشعار لمستخدم"""
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            logger.info(f"Notification sent to user {user_id}")
            return True
        except TelegramForbiddenError:
            logger.warning(f"User {user_id} blocked the bot")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Bad request when sending to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            return False
    
    @staticmethod
    async def notify_admins(bot: Bot, message: str, parse_mode: str = "HTML", admin_ids: List[int] = None) -> int:
        """إرسال إشعار لجميع الأدمن (UF-03)"""
        target_ids = admin_ids or ADMIN_IDS
        success_count = 0
        for admin_id in target_ids:
            if await NotificationManager.notify_user(bot, admin_id, message, parse_mode):
                success_count += 1
        return success_count
    
    @staticmethod
    async def notify_admins_new_order(order_id: int, user_id: int, product_id: int, bot: Bot, order_data: dict = None):
        """
        Fixed L-05: Admin Notification for new orders
        Fixed P-01: Optimized performance by passing order_data directly
        """
        from database.manager import db_manager
        
        if order_data:
            order = order_data
            product_name = order.get('product_name', 'Unknown')
            username = order.get('username', 'N/A')
        else:
            product = await db_manager.get_product(product_id)
            user = await db_manager.get_user(user_id)
            username = f"@{user['username']}" if user and user.get('username') else "N/A"
            product_name = product['name'] if product else "Unknown"
        
        message = (
            f"🆕 <b>طلب جديد #{order_id}</b>\n\n"
            f"👤 المستخدم: {username} (<code>{user_id}</code>)\n"
            f"📦 المنتج: {product_name}\n"
            f"⏰ الوقت: الآن"
        )
        await NotificationManager.notify_admins(bot, message)

    @staticmethod
    async def notify_order_status_change(bot: Bot, user_id: int, order_id: int, status: str, details: str = None):
        """إشعار بتغيير حالة الطلب"""
        status_messages = {
            "PAID": "✅ تم تأكيد الدفع",
            "IN_PROGRESS": "⏳ جاري تنفيذ طلبك",
            "COMPLETED": "✅ تم إكمال طلبك بنجاح",
            "FAILED": "❌ فشل تنفيذ الطلب",
            "CANCELED": "❌ تم إلغاء الطلب"
        }
        
        message = f"📦 <b>الطلب #{order_id}</b>\n\n{status_messages.get(status, status)}"
        if details:
            message += f"\n\n📝 {details}"
        
        await NotificationManager.notify_user(bot, user_id, message)
    
    @staticmethod
    async def notify_balance_change(bot: Bot, user_id: int, amount_cents: int, new_balance_cents: int, reason: str):
        """
        Fixed F-02: Precision Financial Operations (Cents-based)
        """
        amount = amount_cents / 100
        new_balance = new_balance_cents / 100
        sign = "+" if amount > 0 else ""
        message = (
            f"💰 <b>تحديث الرصيد</b>\n\n"
            f"المبلغ: <code>{sign}{amount:.2f}$</code>\n"
            f"الرصيد الجديد: <code>{new_balance:.2f}$</code>\n"
            f"السبب: {reason}"
        )
        await NotificationManager.notify_user(bot, user_id, message)

# إنشاء instance عام
notification_service = NotificationManager()
notification_manager = notification_service # Alias for compatibility
