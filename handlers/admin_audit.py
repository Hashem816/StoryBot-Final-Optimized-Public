"""
نظام عرض سجل العمليات (Audit Log) - v2.3
التحسينات:
- دعم البادئات الجديدة (adm_audit)
- دعم الترجمة الكاملة
"""

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.manager import db_manager
from utils.translations import get_text, get_user_language
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "adm_audit")
async def admin_audit_logs_main(callback: types.CallbackQuery, user: dict, **kwargs):
    """عرض سجل العمليات الإدارية"""
    lang = get_user_language(user)
    logs = await db_manager.get_audit_logs(limit=20)
    
    if not logs:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main"))
        return await callback.message.edit_text("📭 لا توجد سجلات حالياً", reply_markup=builder.as_markup())
    
    text = "📝 <b>سجل العمليات الإدارية</b>\n\nآخر 20 عملية:\n\n"
    for log in logs:
        admin_id = log['admin_id']
        action = log['action']
        details = log['details'] or ''
        created_at = log['created_at']
        
        text += f"🔹 <code>{action}</code>\n"
        text += f"   👤 Admin: <code>{admin_id}</code>\n"
        if details:
            text += f"   📄 {details[:50]}\n"
        text += f"   ⏰ <code>{created_at}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 إحصائيات السجل", callback_data="adm_audit_stats"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "adm_audit_stats")
async def admin_audit_stats(callback: types.CallbackQuery, user: dict, **kwargs):
    """عرض إحصائيات سجل العمليات"""
    lang = get_user_language(user)
    db = await db_manager.connect()
    
    cursor = await db.execute("SELECT action, COUNT(*) as count FROM audit_logs GROUP BY action ORDER BY count DESC LIMIT 10")
    action_stats = await cursor.fetchall()
    
    cursor = await db.execute("SELECT admin_id, COUNT(*) as count FROM audit_logs GROUP BY admin_id ORDER BY count DESC LIMIT 5")
    admin_stats = await cursor.fetchall()
    
    text = "📊 <b>إحصائيات سجل العمليات</b>\n\n🔝 أكثر العمليات:\n"
    for stat in action_stats:
        text += f"   • <code>{stat['action']}</code>: {stat['count']}\n"
    
    text += "\n👥 أكثر الأدمن نشاطاً:\n"
    for stat in admin_stats:
        text += f"   • Admin <code>{stat['admin_id']}</code>: {stat['count']} عملية\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_audit"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
