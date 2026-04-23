"""
معالج الإحصائيات - v2.3
التحسينات:
- استخدام Analytics Service بشكل كامل
- دعم البادئات الجديدة (adm_stats)
- دعم الترجمة الكاملة
"""

from aiogram import Router, F, types
from database.manager import db_manager
from services.analytics_service import analytics_service
from utils.translations import get_text, get_user_language
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "adm_stats")
async def show_stats(callback: types.CallbackQuery, user: dict, **kwargs):
    """عرض الإحصائيات الشاملة"""
    lang = get_user_language(user)
    
    try:
        stats = await analytics_service.get_dashboard_stats()
        if not stats:
            return await callback.answer("❌ فشل جلب الإحصائيات", show_alert=True)
        
        text = (
            f"📊 <b>{get_text('admin_stats', lang)}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>المستخدمون</b>\n"
            f"• إجمالي المستخدمين: <code>{stats.get('total_users', 0)}</code>\n"
            f"• مستخدمون جدد اليوم: <code>{stats.get('new_users_today', 0)}</code>\n"
            f"• محظورون: <code>{stats.get('blocked_users', 0)}</code>\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>الطلبات</b>\n"
            f"• إجمالي الطلبات: <code>{stats.get('total_orders', 0)}</code>\n"
            f"• طلبات اليوم: <code>{stats.get('orders_today', 0)}</code>\n"
            f"• مكتملة: <code>{stats.get('completed_orders', 0)}</code>\n"
            f"• معدل النجاح: <code>{stats.get('success_rate', 0):.1f}%</code>\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>الإيرادات</b>\n"
            f"• إجمالي الإيرادات: <b>{stats.get('total_revenue', 0):.2f}$</b>\n"
            f"• إيرادات اليوم: <b>{stats.get('revenue_today', 0):.2f}$</b>\n"
            f"• متوسط قيمة الطلب: <b>{stats.get('avg_order_value', 0):.2f}$</b>\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>الأرصدة</b>\n"
            f"• إجمالي أرصدة المستخدمين: <b>{stats.get('total_balance', 0):.2f}$</b>\n"
            f"• حالة النظام المالي: <code>{'✅ سليم' if stats.get('is_financial_healthy') else '⚠️ فجوة: ' + str(stats.get('reconciliation_diff')) + '$'}</code>\n\n"
            
            f"📅 تم التحديث الآن"
        )
        
        builder = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📈 تفاصيل إضافية", callback_data="adm_stats_details")],
            [types.InlineKeyboardButton(text="🔄 تحديث", callback_data="adm_stats")],
            [types.InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=builder)
        await db_manager.log_admin_action(admin_id=callback.from_user.id, action="VIEW_STATS", target_type="SYSTEM")
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await callback.answer("❌ حدث خطأ")

@router.callback_query(F.data == "adm_stats_details")
async def show_stats_details(callback: types.CallbackQuery, user: dict, **kwargs):
    """عرض تفاصيل إضافية للإحصائيات"""
    lang = get_user_language(user)
    
    try:
        top_products = await analytics_service.get_top_products(limit=5)
        user_activity = await analytics_service.get_user_activity()
        
        text = f"📈 <b>تفاصيل الإحصائيات</b>\n\n━━━━━━━━━━━━━━━━━━━━\n🏆 <b>أكثر المنتجات مبيعاً</b>\n"
        if top_products:
            for i, product in enumerate(top_products, 1):
                text += f"{i}. {product['name']}: <code>{product['order_count']}</code> طلب (<b>{product['total_revenue']:.2f}$</b>)\n"
        else:
            text += "لا توجد بيانات\n"
        
        text += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>نشاط المستخدمين</b>\n"
            f"• مستخدمون نشطون (30 يوم): <code>{user_activity.get('active_users_month', 0)}</code>\n"
            f"• متوسط الطلبات لكل مستخدم: <code>{user_activity.get('avg_orders_per_user', 0)}</code>\n"
        )
        
        builder = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_stats")]
        ])
        
        await callback.message.edit_text(text, reply_markup=builder)
    except Exception as e:
        logger.error(f"Error showing stats details: {e}")
        await callback.answer("❌ حدث خطأ")
