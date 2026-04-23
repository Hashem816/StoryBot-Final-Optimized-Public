"""
نظام إدارة الكوبونات - Ultimate Edition (v2.3)
التحسينات:
- دعم الترجمة الكاملة لجميع الرسائل
- توحيد البادئات (adm_coup) لسهولة إدارة الصلاحيات
- تحسين واجهة المستخدم
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.manager import db_manager
from utils.translations import get_text, get_user_language
from config.settings import CouponType
from datetime import datetime, timedelta
import logging

router = Router()
logger = logging.getLogger(__name__)

class CouponStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_value = State()
    waiting_for_max_uses = State()
    waiting_for_min_amount = State()

@router.callback_query(F.data == "adm_coup")
async def admin_coupons_main(callback: types.CallbackQuery, user: dict):
    """القائمة الرئيسية لإدارة الكوبونات"""
    lang = get_user_language(user) or "ar"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ " + get_text("create_coupon", lang), callback_data="adm_coup_add"))
    builder.row(InlineKeyboardButton(text="📋 " + get_text("list_coupons", lang), callback_data="adm_coup_list"))
    builder.row(InlineKeyboardButton(text="📊 " + get_text("admin_stats", lang), callback_data="adm_coup_stats"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main"))
    
    await callback.message.edit_text(
        f"<b>{get_text('coupons_management', lang)}</b>",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "adm_coup_list")
async def admin_coupon_list(callback: types.CallbackQuery, user: dict):
    """عرض قائمة الكوبونات (M-07)"""
    lang = get_user_language(user) or "ar"
    coupons = await db_manager.get_all_coupons()
    
    if not coupons:
        return await callback.answer("لا توجد كوبونات.", show_alert=True)
    
    text = "📋 <b>قائمة الكوبونات:</b>\n\n"
    for c in coupons:
        # Fix: Unified Coupon Types (L-02)
        type_display = "نسبة مئوية %" if c['type'] == CouponType.PERCENT else "مبلغ ثابت $"
        value_display = f"{c['value']}%" if c['type'] == CouponType.PERCENT else f"{c['value']/100:.2f}$"
        
        text += f"🎟️ <code>{c['code']}</code> | {type_display} ({value_display})\n"
        text += f"📈 الاستخدام: {c['used_count']}/{c['max_uses']} | أدنى طلب: {c['min_amount']/100:.2f}$\n"
        text += "-------------------\n"
        
    if len(text) > 4000: text = text[:4000] + "\n..."
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_coup"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "adm_coup_stats")
async def admin_coupon_stats(callback: types.CallbackQuery, user: dict):
    """إحصائيات الكوبونات"""
    lang = get_user_language(user)
    db = await db_manager.connect()
    cursor = await db.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(used_count) as total_uses,
            SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active
        FROM coupons
    """)
    stats = await cursor.fetchone()
    
    total = stats['total'] or 0
    total_uses = stats['total_uses'] or 0
    active = stats['active'] or 0
    
    text = (
        f"📊 <b>{get_text('admin_stats', lang)}</b>\n\n"
        f"🎟️ إجمالي الكوبونات: <code>{total}</code>\n"
        f"✅ كوبونات نشطة: <code>{active}</code>\n"
        f"📈 إجمالي مرات الاستخدام: <code>{total_uses}</code>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_coup"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "adm_coup_add")
async def admin_coupon_create_start(callback: types.CallbackQuery, state: FSMContext, user: dict):
    """بدء إنشاء كوبون جديد"""
    lang = get_user_language(user)
    await state.set_state(CouponStates.waiting_for_code)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_coup"))
    
    await callback.message.edit_text(
        "🎟️ <b>إنشاء كوبون جديد</b>\n\nالخطوة 1/5: أرسل كود الكوبون (مثال: WELCOME2024)",
        reply_markup=builder.as_markup()
    )

@router.message(CouponStates.waiting_for_code)
async def admin_coupon_code_received(message: types.Message, state: FSMContext, user: dict):
    """استقبال كود الكوبون"""
    lang = get_user_language(user)
    code = message.text.strip().upper()
    
    existing = await db_manager.get_coupon(code)
    if existing:
        return await message.answer("❌ هذا الكوبون موجود مسبقاً! أرسل كوداً آخر.")
    
    await state.update_data(code=code)
    await state.set_state(CouponStates.waiting_for_type)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💯 نسبة مئوية (%)", callback_data=f"adm_coup_type_{CouponType.PERCENT}"),
        InlineKeyboardButton(text="💵 مبلغ ثابت ($)", callback_data=f"adm_coup_type_{CouponType.FIXED}")
    )
    builder.row(InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_coup"))
    
    await message.answer(f"✅ الكود: <code>{code}</code>\n\nالخطوة 2/5: اختر نوع الخصم:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("adm_coup_type_"))
async def admin_coupon_type_selected(callback: types.CallbackQuery, state: FSMContext, user: dict):
    """اختيار نوع الكوبون"""
    lang = get_user_language(user)
    coupon_type = callback.data.split("_")[3]
    await state.update_data(type=coupon_type)
    await state.set_state(CouponStates.waiting_for_value)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_coup"))
    
    prompt = "الخطوة 3/5: أرسل نسبة الخصم (مثال: 10 لخصم 10%)" if coupon_type == CouponType.PERCENT else "الخطوة 3/5: أرسل قيمة الخصم بالسنتات (مثال: 500 لخصم 5$)"
    await callback.message.edit_text(prompt, reply_markup=builder.as_markup())

@router.message(CouponStates.waiting_for_value)
async def admin_coupon_value_received(message: types.Message, state: FSMContext, user: dict):
    """استقبال قيمة الخصم"""
    lang = get_user_language(user)
    try:
        value = int(message.text)
        if value <= 0: raise ValueError
        
        data = await state.get_data()
        if data['type'] == CouponType.PERCENT and value > 100:
            return await message.answer("❌ النسبة يجب أن تكون بين 1 و 100")
        
        await state.update_data(value=value)
        await state.set_state(CouponStates.waiting_for_max_uses)
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="♾️ غير محدود", callback_data="adm_coup_uses_unlim"))
        builder.row(InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_coup"))
        
        await message.answer("الخطوة 4/5: أرسل الحد الأقصى لعدد الاستخدامات (أو اضغط 'غير محدود'):", reply_markup=builder.as_markup())
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

@router.callback_query(F.data == "adm_coup_uses_unlim")
async def admin_coupon_unlimited_uses(callback: types.CallbackQuery, state: FSMContext, user: dict):
    """تعيين استخدامات غير محدودة"""
    await state.update_data(max_uses=999999)
    await admin_coupon_ask_min_amount(callback, state, user)

@router.message(CouponStates.waiting_for_max_uses)
async def admin_coupon_max_uses_received(message: types.Message, state: FSMContext, user: dict):
    """استقبال عدد الاستخدامات"""
    lang = get_user_language(user)
    try:
        max_uses = int(message.text)
        if max_uses <= 0: raise ValueError
        await state.update_data(max_uses=max_uses)
        await admin_coupon_ask_min_amount(message, state, user)
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

async def admin_coupon_ask_min_amount(event, state: FSMContext, user: dict):
    """طلب الحد الأدنى للمبلغ"""
    lang = get_user_language(user)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="0️⃣ بدون حد أدنى", callback_data="adm_coup_min_zero"))
    builder.row(InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_coup"))
    
    text = "الخطوة 5/5: أرسل الحد الأدنى لمبلغ الطلب بالسنتات (أو اضغط 'بدون حد أدنى'):"
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await event.answer(text, reply_markup=builder.as_markup())
    await state.set_state(CouponStates.waiting_for_min_amount)

@router.callback_query(F.data == "adm_coup_min_zero")
async def admin_coupon_min_zero(callback: types.CallbackQuery, state: FSMContext, user: dict):
    """تعيين حد أدنى صفر"""
    await state.update_data(min_amount=0)
    await admin_coupon_finalize(callback, state, user)

@router.message(CouponStates.waiting_for_min_amount)
async def admin_coupon_min_amount_received(message: types.Message, state: FSMContext, user: dict):
    """استقبال الحد الأدنى"""
    lang = get_user_language(user)
    try:
        min_amount = int(message.text)
        if min_amount < 0: raise ValueError
        await state.update_data(min_amount=min_amount)
        await admin_coupon_finalize(message, state, user)
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

async def admin_coupon_finalize(event, state: FSMContext, user: dict):
    """إنهاء إنشاء الكوبون"""
    lang = get_user_language(user)
    data = await state.get_data()
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    
    try:
        await db_manager.create_coupon(
            code=data['code'],
            type=data['type'],
            value=data['value'],
            max_uses=data['max_uses'],
            min_amount=data['min_amount'],
            expires_at=expires_at,
            created_by=event.from_user.id
        )
        await state.clear()
        msg = get_text("coupon_created", lang)
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(f"✅ {msg}", reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_coup")).as_markup())
        else:
            await event.answer(f"✅ {msg}")
            # العودة للقائمة
            builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_coup"))
            await event.answer("🎟️ العودة لإدارة الكوبونات:", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Error creating coupon: {e}")
        await event.answer("❌ حدث خطأ أثناء إنشاء الكوبون.")
