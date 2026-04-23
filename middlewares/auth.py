"""
Middleware للمصادقة والصلاحيات - v2.3 REBORN
التحسينات:
- استخدام PermissionService بشكل مركزي للتحقق من الصلاحيات
- إنفاذ صارم للصلاحيات بناءً على الإجراءات وليس فقط البادئات
- حماية ضد الوصول غير المصرح به
"""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from config.settings import ADMIN_IDS, UserRole
from database.manager import db_manager
from services.permission_service import permission_service
import logging

logger = logging.getLogger(__name__)

class AdminMiddleware(BaseMiddleware):
    """
    Middleware للتحقق من صلاحيات الإدارة (v2.3 REBORN)
    يعتمد على PermissionService لاتخاذ قرارات الوصول.
    """
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # استخراج الحدث الفعلي من التحديث
        actual_event = event.message or event.callback_query
        if not actual_event:
            return await handler(event, data)

        user_id = actual_event.from_user.id
        user = await db_manager.get_user(user_id)
        user_role = user['role'] if user else UserRole.USER
        
        # تمرير الصلاحيات للمعالجات (Handlers) للتوافق مع الكود القديم
        data['user_role'] = user_role
        data['is_super_admin'] = (user_role == UserRole.SUPER_ADMIN)
        data['is_operator'] = user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR]
        data['is_support'] = user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
        data['is_admin'] = data['is_super_admin']
        
        # Fixed S-01: Deny-by-Default for Admin Callbacks
        if event.callback_query:
            callback_data = event.callback_query.data
            
            # Check if it's an admin callback (starts with adm_ or other admin prefixes)
            is_admin_callback = any(callback_data.startswith(p) for p in ['adm_', 'ao_', 'ac_', 'ap_', 'coupon_'])
            
            if is_admin_callback:
                required_permission = permission_service.get_permission_for_callback(callback_data)
                
                # If no specific permission mapped, default to SUPER_ADMIN only (Deny-by-Default)
                if not required_permission:
                    if user_role != UserRole.SUPER_ADMIN:
                        logger.warning(f"Blocked unmapped admin callback {callback_data} for user {user_id}")
                        return await event.callback_query.answer("⚠️ وصول غير مصرح به.", show_alert=True)
                else:
                    if not permission_service.has_permission(user_role, required_permission):
                        logger.warning(f"Unauthorized access attempt by {user_id} (Role: {user_role}) to {callback_data}")
                        return await event.callback_query.answer("⚠️ ليس لديك الصلاحية الكافية لهذا الإجراء.", show_alert=True)
        
        return await handler(event, data)

class AuthMiddleware(BaseMiddleware):
    """
    Middleware للمصادقة العامة وحالة الحظر
    """
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # استخراج الحدث الفعلي من التحديث
        actual_event = event.message or event.callback_query
        if not actual_event:
            return await handler(event, data)

        user_id = actual_event.from_user.id
        user = await db_manager.get_user(user_id)
        
        if not user:
            # إنشاء مستخدم جديد
            role = UserRole.SUPER_ADMIN if user_id in ADMIN_IDS else UserRole.USER
            await db_manager.create_user(
                user_id,
                actual_event.from_user.username or "Unknown",
                first_name=actual_event.from_user.first_name,
                last_name=actual_event.from_user.last_name,
                role=role
            )
            user = await db_manager.get_user(user_id)
        
        # التحقق من الحظر
        if user['is_blocked']:
            msg = "🚫 حسابك محظور حالياً."
            if event.message: await event.message.answer(msg)
            elif event.callback_query: await event.callback_query.answer(msg, show_alert=True)
            return
            
        # التحقق من وضع الطوارئ (لغير الإداريين)
        if not permission_service.is_staff(user['role']):
            emergency = await db_manager.get_setting("emergency_stop", "0")
            if emergency == "1":
                msg = "🚨 المتجر متوقف مؤقتاً لحالة طوارئ."
                if event.message: await event.message.answer(msg)
                elif event.callback_query: await event.callback_query.answer(msg, show_alert=True)
                return

        data['user'] = user
        return await handler(event, data)
