"""
Permission Service - نظام الصلاحيات المحسّن (v2.3)
التحسينات:
- SUPER_ADMIN يرث كل الصلاحيات
- OPERATOR يرث SUPPORT
- خريطة بادئات مركزية للتحقق من الصلاحيات بناءً على الـ Callback Data
"""

from typing import Dict, Any
from config.settings import UserRole
import logging

logger = logging.getLogger(__name__)


class PermissionService:
    """خدمة إدارة الصلاحيات"""
    
    # تعريف الصلاحيات لكل رتبة
    PERMISSIONS = {
        UserRole.SUPER_ADMIN: {
            'manage_products': True,
            'manage_payment_methods': True,
            'manage_orders': True,
            'manage_users': True,
            'manage_coupons': True,
            'view_stats': True,
            'broadcast': True,
            'manage_settings': True,
            'view_audit_logs': True,
            'manage_roles': True,
            'emergency_stop': True,
            'adm_main': True
        },
        UserRole.OPERATOR: {
            'manage_products': True,
            'manage_payment_methods': True,
            'manage_orders': True,
            'manage_users': False,
            'manage_coupons': False,
            'view_stats': True,
            'broadcast': False,
            'manage_settings': False,
            'view_audit_logs': False,
            'manage_roles': False,
            'emergency_stop': False,
            'adm_main': True
        },
        UserRole.SUPPORT: {
            'manage_products': False,
            'manage_payment_methods': False,
            'manage_orders': True,
            'manage_users': False,
            'manage_coupons': False,
            'view_stats': False,
            'broadcast': False,
            'manage_settings': False,
            'view_audit_logs': False,
            'manage_roles': False,
            'emergency_stop': False,
            'adm_main': True
        },
        UserRole.USER: {
            'manage_products': False,
            'manage_payment_methods': False,
            'manage_orders': False,
            'manage_users': False,
            'manage_coupons': False,
            'view_stats': False,
            'broadcast': False,
            'manage_settings': False,
            'view_audit_logs': False,
            'manage_roles': False,
            'emergency_stop': False,
            'adm_main': False
        }
    }

    # خريطة البادئات للصلاحيات المطلوبة
    PREFIX_PERMISSION_MAP = {
        'ao_v_': 'manage_orders', # عرض تفاصيل الطلب
        'ao_': 'manage_orders',
        'adm_ords': 'manage_orders',
        'adm_prods': 'manage_products',
        'adm_cats': 'manage_products',
        'adm_paym': 'manage_payment_methods',
        'adm_usrs': 'manage_users',
        'adm_stats': 'view_stats',
        'adm_brdcst': 'broadcast',
        'adm_coup': 'manage_coupons',
        'adm_sett': 'manage_settings',
        'adm_main': 'adm_main',
        'ac_': 'manage_products',
        'ap_': 'manage_products',
        'coupon_': 'manage_coupons',
        # تم إزالة 'admin_' العامة واستبدالها ببادئات محددة (H-04)
        'adm_u_': 'manage_users',
        'adm_m_': 'manage_settings'
    }
    
    @staticmethod
    def has_permission(user_role: str, permission: str) -> bool:
        """التحقق من صلاحية معينة"""
        if user_role not in PermissionService.PERMISSIONS:
            return False
        return PermissionService.PERMISSIONS[user_role].get(permission, False)
    
    @staticmethod
    def get_permission_for_callback(callback_data: str) -> str:
        """تحديد الصلاحية المطلوبة بناءً على الـ Callback Data"""
        for prefix, permission in PermissionService.PREFIX_PERMISSION_MAP.items():
            if callback_data.startswith(prefix):
                return permission
        return None

    @staticmethod
    def is_staff(user_role: str) -> bool:
        """التحقق من أن المستخدم من الطاقم الإداري"""
        return user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]

permission_service = PermissionService()
