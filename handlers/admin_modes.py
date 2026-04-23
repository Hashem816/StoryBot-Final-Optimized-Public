"""
نظام أوضاع المتجر وإعدادات الصرف - v2.3
التحسينات:
- دعم الترجمة الكاملة
- دقة مالية بنظام السنتات
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from config.settings import StoreMode
from utils.translations import get_text, get_user_language
import logging

router = Router()
logger = logging.getLogger(__name__)

class DollarSettings(StatesGroup):
    waiting_for_rate = State()

def get_modes_keyboard(current_mode: str, emergency_stop: bool, lang: str):
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"{'✅ ' if current_mode == StoreMode.AUTO else ''}🟢 AUTO", callback_data=f"adm_sm_{StoreMode.AUTO}")],
        [types.InlineKeyboardButton(text=f"{'✅ ' if current_mode == StoreMode.MANUAL else ''}🟡 MANUAL", callback_data=f"adm_sm_{StoreMode.MANUAL}")],
        [types.InlineKeyboardButton(text=f"{'✅ ' if current_mode == StoreMode.MAINTENANCE else ''}🛠 MAINTENANCE", callback_data=f"adm_sm_{StoreMode.MAINTENANCE}")],
        [types.InlineKeyboardButton(
            text="🚨 إيقاف الطوارئ (ON)" if not emergency_stop else "🟢 إلغاء الطوارئ (OFF)", 
            callback_data="adm_te"
        )],
        [types.InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main")]
    ])
    return builder

@router.callback_query(F.data == "adm_mode")
async def show_store_modes(callback: types.CallbackQuery, user: dict, **kwargs):
    lang = get_user_language(user)
    current_mode = await db_manager.get_setting("store_mode", StoreMode.MANUAL)
    emergency_stop = (await db_manager.get_setting("emergency_stop", "0")) == "1"
    
    status_text = (
        f"🔌 <b>نظام تشغيل المتجر</b>\n\n"
        f"📍 الوضع الحالي: <code>{current_mode}</code>\n"
        f"🚨 حالة الطوارئ: <b>{'مفعلة' if emergency_stop else 'معطلة'}</b>\n\n"
        f"ℹ️ <b>الفرق بين الأوضاع:</b>\n"
        f"• 🛠 <b>الصيانة</b>: إيقاف المتجر للتحديثات.\n"
        f"• 🚨 <b>الطوارئ</b>: إيقاف فوري وشامل لجميع العمليات.\n"
        f"• 🤖 <b>AUTO</b>: تنفيذ تلقائي عبر API.\n"
        f"• 👤 <b>MANUAL</b>: تنفيذ يدوي."
    )
    
    await callback.message.edit_text(status_text, reply_markup=get_modes_keyboard(current_mode, emergency_stop, lang))

@router.callback_query(F.data.startswith("adm_sm_"))
async def set_mode(callback: types.CallbackQuery, user: dict, **kwargs):
    new_mode = callback.data.replace("adm_sm_", "")
    await db_manager.set_setting("store_mode", new_mode)
    await callback.answer(f"✅ تم الانتقال لوضع {new_mode}")
    await show_store_modes(callback, user)

@router.callback_query(F.data == "adm_te")
async def toggle_emergency(callback: types.CallbackQuery, user: dict, **kwargs):
    current = await db_manager.get_setting("emergency_stop", "0")
    new_val = "1" if current == "0" else "0"
    await db_manager.set_setting("emergency_stop", new_val)
    
    msg = "🚨 تم تفعيل إيقاف الطوارئ!" if new_val == "1" else "🟢 تم إلغاء إيقاف الطوارئ."
    await callback.answer(msg, show_alert=True)
    await show_store_modes(callback, user)

@router.callback_query(F.data == "adm_rate")
async def dollar_settings_main(callback: types.CallbackQuery, user: dict, **kwargs):
    lang = get_user_language(user)
    rate_cents = int(await db_manager.get_setting("dollar_rate", "1250000"))
    
    text = (
        f"💵 <b>إعدادات سعر الصرف</b>\n\n"
        f"سعر الدولار الحالي: <code>{rate_cents/100:,.2f} ل.س</code>\n\n"
        f"هذا السعر يستخدم لحساب تكلفة المنتجات."
    )
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ تعديل السعر", callback_data="adm_sr")],
        [types.InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=builder, )

@router.callback_query(F.data == "adm_sr")
async def set_rate_start(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    await state.set_state(DollarSettings.waiting_for_rate)
    await callback.message.edit_text("💵 <b>أدخل سعر الدولار الجديد (مثلاً: 13500.50):</b>")

@router.message(DollarSettings.waiting_for_rate)
async def set_rate_finish(message: types.Message, state: FSMContext, **kwargs):
    try:
        # Fix: Precision Financial Operations (Decimal-based Cents)
        from decimal import Decimal, ROUND_HALF_UP
        new_rate_dec = Decimal(message.text.strip())
        new_rate_cents = int((new_rate_dec * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        await db_manager.set_setting("dollar_rate", str(new_rate_cents))
        await state.clear()
        await message.answer(f"✅ تم تحديث سعر الدولار إلى: <code>{new_rate_cents/100:,.2f} ل.س</code>")
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح.", )
