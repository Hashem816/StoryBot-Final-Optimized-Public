from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_admin_main_menu
from utils.translations import get_text, get_user_language
from config.settings import UserRole
import logging

router = Router()
logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    waiting_for_search_query = State()
    waiting_for_balance_amount = State()

@router.message(F.text.in_(["⚙️ لوحة التحكم", "⚙️ Admin Panel"]))
async def admin_panel(message: types.Message, is_support: bool, user_role: str, user: dict):
    if not is_support: return
    lang = get_user_language(user) or "ar"
    await message.answer(
        f"🛠 <b>لوحة التحكم - {user_role}</b>\n\nمرحباً بك في نظام الإدارة المطور v2.3 REBORN",
        reply_markup=get_admin_main_menu(user_role, lang)
    )

@router.callback_query(F.data == "adm_main")
async def admin_panel_callback(callback: types.CallbackQuery, is_support: bool, user_role: str, user: dict):
    if not is_support: return
    lang = get_user_language(user) or "ar"
    await callback.message.edit_text(
        f"🛠 <b>لوحة التحكم - {user_role}</b>\n\nمرحباً بك في نظام الإدارة المطور v2.3 REBORN",
        reply_markup=get_admin_main_menu(user_role, lang)
    )

@router.callback_query(F.data == "adm_usrs")
async def admin_users_manage(callback: types.CallbackQuery, is_super_admin: bool):
    if not is_super_admin: return
    
    try:
        db = await db_manager.connect()
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 10") as cursor:
            users = await cursor.fetchall()
        
        text = "👥 <b>إدارة المستخدمين</b>\n\nآخر 10 مستخدمين انضموا:\n\n"
        builder = InlineKeyboardBuilder()
        
        for u in users:
            status = "🚫" if u['is_blocked'] else "✅"
            # M-09: تحسين عرض الاسم وتجنب None
            display_name = u['username'] or u['first_name'] or str(u['telegram_id'])
            text += f"{status} <code>{u['telegram_id']}</code> - {display_name}\n"
            builder.row(InlineKeyboardButton(text=f"👤 {display_name[:20]}", callback_data=f"adm_u_v_{u['telegram_id']}"))
        
        # M-09: قص النص إذا تجاوز الحد
        if len(text) > 3500:
            text = text[:3500] + "\n... وآخرون"
            
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="adm_main"))
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Error in admin_users_manage: {e}")
        await callback.answer("❌ حدث خطأ أثناء جلب المستخدمين.")

@router.callback_query(F.data.startswith("adm_u_v_"))
async def admin_user_view(callback: types.CallbackQuery, is_super_admin: bool):
    if not is_super_admin: return
    user_id = int(callback.data.split("_")[3])
    u = await db_manager.get_user(user_id)
    
    if not u:
        return await callback.answer("❌ المستخدم غير موجود", show_alert=True)
    
    status = "🚫 محظور" if u['is_blocked'] else "✅ نشط"
    # M-09: حماية من قيم None
    first_name = u.get('first_name') or "غير محدد"
    last_name = u.get('last_name') or ""
    username = f"@{u['username']}" if u.get('username') else "لا يوجد"
    
    text = (
        f"👤 <b>تفاصيل المستخدم</b>\n\n"
        f"ID: <code>{u['telegram_id']}</code>\n"
        f"الاسم: {first_name} {last_name}\n"
        f"اليوزر: {username}\n"
        f"الرصيد: <b>{u['balance']/100:.2f}$</b>\n"
        f"الرتبة: <code>{u['role']}</code>\n"
        f"اللغة: <code>{u['language']}</code>\n"
        f"الحالة: {status}\n"
        f"تاريخ الانضمام: <code>{u['created_at']}</code>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 تعديل الرصيد", callback_data=f"adm_u_b_{user_id}"))
    builder.row(InlineKeyboardButton(text="🚫 حظر/إلغاء حظر", callback_data=f"adm_u_t_{user_id}"))
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="adm_usrs"))
    
    # Fix: Unified HTML Parse Mode
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("adm_u_b_"))
async def admin_user_balance_edit_start(callback: types.CallbackQuery, is_super_admin: bool, state: FSMContext):
    if not is_super_admin: return
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_balance_amount)
    
    # Fix: Unified HTML Parse Mode
    await callback.message.answer(
        "💰 <b>تعديل رصيد المستخدم</b>\n\n"
        "أدخل المبلغ المراد إضافته أو خصمه (بالدولار).\n"
        "مثال: <code>5</code> للإضافة، <code>-5</code> للخصم.",
        reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_u_v_{user_id}")).as_markup()
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_balance_amount)
async def admin_user_balance_edit_finish(message: types.Message, state: FSMContext, user: dict, is_super_admin: bool):
    """
    NR-02: Added is_super_admin check.
    """
    if not is_super_admin:
        await state.clear()
        return await message.answer("⚠️ لا تملك الصلاحية لتعديل الأرصدة.")

    try:
        # Fix: Precision Financial Operations (Decimal-based Cents)
        from decimal import Decimal, ROUND_HALF_UP
        amount_dec = Decimal(message.text.strip())
        amount_cents = int((amount_dec * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        
        data = await state.get_data()
        user_id = data.get('target_user_id')
        
        success, result = await db_manager.update_user_balance(
            user_id=user_id,
            amount=amount_cents,
            log_type="ADMIN_ADJUST",
            reason=f"تعديل يدوي من قبل الأدمن {user['telegram_id']}",
            admin_id=user['telegram_id']
        )
        
        if success:
            # Fix: Unified HTML Parse Mode
            await message.answer(f"✅ تم تعديل الرصيد بنجاح. الرصيد الجديد: <code>{result/100:.2f}$</code>")
            await state.clear()
        else:
            await message.answer(f"❌ فشل التعديل: {result}")
            
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح (مثال: 10.5 أو -5)")
    except Exception as e:
        logger.error(f"Error in balance edit: {e}")
        await message.answer(f"❌ حدث خطأ غير متوقع: {e}")

@router.callback_query(F.data.startswith("adm_u_t_"))
async def admin_user_toggle_block(callback: types.CallbackQuery, is_super_admin: bool):
    """
    NR-06: Added audit logging for block/unblock.
    """
    if not is_super_admin: return
    user_id = int(callback.data.split("_")[3])
    u = await db_manager.get_user(user_id)
    if not u: return await callback.answer("❌ المستخدم غير موجود")
    
    new_status = 0 if u['is_blocked'] else 1
    action = "BLOCK_USER" if new_status else "UNBLOCK_USER"
    
    async with db_manager.transaction() as db:
        await db.execute("UPDATE users SET is_blocked = ? WHERE telegram_id = ?", (new_status, user_id))
        await db_manager.log_admin_action(
            admin_id=callback.from_user.id,
            action=action,
            target_type="USER",
            target_id=user_id,
            details=f"{'Blocked' if new_status else 'Unblocked'} user {user_id}",
            commit=False,
            db_conn=db
        )
    
    await callback.answer(f"✅ تم {'حظر' if new_status else 'إلغاء حظر'} المستخدم")
    await admin_user_view(callback, is_super_admin)

from handlers.admin_stats import show_stats
from handlers.admin_audit import admin_audit_logs_main

@router.callback_query(F.data == "adm_stats")
async def admin_stats_view(callback: types.CallbackQuery, is_super_admin: bool):
    await show_stats(callback, is_super_admin)

@router.callback_query(F.data == "adm_audit")
async def admin_audit_view(callback: types.CallbackQuery, is_super_admin: bool, user: dict):
    await admin_audit_logs_main(callback, is_super_admin, user)
