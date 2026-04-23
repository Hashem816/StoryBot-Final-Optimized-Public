"""
Middleware للتحكم بمعدل الطلبات (Rate Limiting) - v2.3
التحسينات:
- تطبيق الحماية على الرسائل والأزرار (CallbackQuery)
- توحيد الرسائل التحذيرية للمستخدمين
- استثناء الطاقم الإداري من القيود
- إضافة وظيفة التنظيف التلقائي (Cleanup) لمنع تسريب الذاكرة
"""

import time
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from config.settings import UserRole

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware للتحكم بمعدل الطلبات
    يمنع المستخدمين من إرسال رسائل أو الضغط على الأزرار بشكل متكرر بسرعة
    """
    
    def __init__(self, slow_mode_delay: float = 1.0, flood_threshold: int = 12):
        """
        Args:
            slow_mode_delay: الحد الأدنى للوقت بين العمليات (بالثواني)
            flood_threshold: عدد العمليات المسموح بها في دقيقة واحدة
        """
        self.slow_mode_delay = slow_mode_delay
        self.flood_threshold = flood_threshold
        
        # تتبع آخر عملية لكل مستخدم
        self.user_last_action_time: Dict[int, float] = {}
        
        # تتبع عدد العمليات في الدقيقة الأخيرة
        self.user_action_count: Dict[int, list] = {}
        
        # تتبع المستخدمين المحظورين مؤقتاً
        self.temp_blocked: Dict[int, float] = {}
        
        # وقت آخر عملية تنظيف شاملة
        self.last_cleanup_time = time.time()

    def _cleanup_old_data(self, current_time: float):
        """تنظيف البيانات القديمة لمنع تسريب الذاكرة (v2.3 REBORN)"""
        # تنظيف كل 10 دقائق
        if current_time - self.last_cleanup_time < 600:
            return
            
        self.last_cleanup_time = current_time
        
        # 1. تنظيف الحظر المؤقت المنتهي
        expired_blocks = [uid for uid, until in self.temp_blocked.items() if current_time > until]
        for uid in expired_blocks:
            del self.temp_blocked[uid]
            
        # 2. تنظيف المستخدمين غير النشطين (أكثر من ساعة)
        inactive_users = [uid for uid, last in self.user_last_action_time.items() if current_time - last > 3600]
        for uid in inactive_users:
            if uid in self.user_last_action_time: del self.user_last_action_time[uid]
            if uid in self.user_action_count: del self.user_action_count[uid]
            
        if inactive_users or expired_blocks:
            logger.info(f"Throttling Cleanup: Removed {len(inactive_users)} inactive users and {len(expired_blocks)} expired blocks.")

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # استخراج الحدث الفعلي من التحديث
        actual_event = event.message or event.callback_query
        if not actual_event:
            return await handler(event, data)

        user_id = actual_event.from_user.id
        current_time = time.time()
        
        # تشغيل التنظيف التلقائي
        self._cleanup_old_data(current_time)
        
        # استثناء الطاقم الإداري من Rate Limiting (M-01)
        from config.settings import ADMIN_IDS
        user_role = data.get('user_role', UserRole.USER)
        if user_id in ADMIN_IDS or user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR]:
            return await handler(event, data)
        
        # التحقق من الحظر المؤقت
        if user_id in self.temp_blocked:
            block_until = self.temp_blocked[user_id]
            if current_time < block_until:
                remaining = int(block_until - current_time)
                msg = f"⚠️ حماية من السبام: يرجى الانتظار {remaining} ثانية."
                if event.message:
                    await event.message.answer(msg)
                elif event.callback_query:
                    await event.callback_query.answer(msg, show_alert=True)
                return
            else:
                del self.temp_blocked[user_id]
                if user_id in self.user_action_count:
                    self.user_action_count[user_id] = []
        
        # التحقق من Slow Mode (منع Race Conditions المالية)
        last_time = self.user_last_action_time.get(user_id, 0)
        if current_time - last_time < self.slow_mode_delay:
            msg = "⚠️ مهلاً! لا تضغط بسرعة كبيرة."
            if event.message:
                await event.message.answer(msg)
            elif event.callback_query:
                await event.callback_query.answer(msg, show_alert=False)
            return
        
        # التحقق من Flood Protection
        if user_id not in self.user_action_count:
            self.user_action_count[user_id] = []
        
        # تنظيف العمليات القديمة (أكثر من دقيقة)
        self.user_action_count[user_id] = [
            t for t in self.user_action_count[user_id]
            if current_time - t < 60
        ]
        
        # إضافة العملية الحالية
        self.user_action_count[user_id].append(current_time)
        
        # التحقق من تجاوز الحد
        if len(self.user_action_count[user_id]) > self.flood_threshold:
            # حظر مؤقت لمدة 60 ثانية
            self.temp_blocked[user_id] = current_time + 60
            logger.warning(f"Flood detected: User {user_id} sent {len(self.user_action_count[user_id])} actions/min")
            
            msg = "⚠️ تم اكتشاف نشاط مريب. تم حظرك مؤقتاً لمدة دقيقة واحدة لحماية النظام."
            if event.message:
                await event.message.answer(msg)
            elif event.callback_query:
                await event.callback_query.answer(msg, show_alert=True)
            return
        
        # تحديث آخر وقت عملية
        self.user_last_action_time[user_id] = current_time
        
        return await handler(event, data)
