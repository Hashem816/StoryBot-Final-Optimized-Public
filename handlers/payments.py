from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_payment_methods_keyboard
import logging
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

class PaymentMethodStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_desc = State()

@router.callback_query(F.data == "adm_paym")
async def admin_payment_methods_main(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    
    try:
        methods = await db_manager.get_payment_methods(only_active=False)
        await callback.message.edit_text(
            "💳 <b>إدارة طرق الدفع</b>\n\nاختر طريقة لتعديلها أو أضف واحدة جديدة:", 
            reply_markup=get_payment_methods_keyboard(methods, is_admin=True)
        )
    except Exception as e:
        logger.error(f"Error in admin_payment_methods_main: {e}")
        await callback.answer("❌ حدث خطأ")

@router.callback_query(F.data == "apm_add")
async def admin_add_pay_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    if not is_operator: return
    await state.set_state(PaymentMethodStates.waiting_for_name)
    await callback.message.edit_text("💳 <b>أدخل اسم طريقة الدفع الجديدة:</b>")

@router.message(PaymentMethodStates.waiting_for_name)
async def admin_add_pay_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(PaymentMethodStates.waiting_for_desc)
    await message.answer("📝 <b>أدخل تعليمات الدفع:</b>")

@router.message(PaymentMethodStates.waiting_for_desc)
async def admin_add_pay_finish(message: types.Message, state: FSMContext, is_operator: bool):
    if not is_operator: return
    data = await state.get_data()
    try:
        # Fix: Audit Logging for Payment Methods (S-01)
        async with db_manager.transaction() as db:
            await db_manager.add_payment_method(data['name'], message.text.strip(), db_conn=db, commit=False)
            await db_manager.log_admin_action(
                admin_id=message.from_user.id,
                action="ADD_PAYMENT_METHOD",
                target_type="SETTING",
                details=f"Added payment method: {data['name']}",
                db_conn=db,
                commit=False
            )
        await state.clear()
        await message.answer(f"✅ تم إضافة طريقة الدفع: <b>{data['name']}</b>")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ فشل الإضافة")

@router.callback_query(F.data.startswith("ap_del_"))
async def admin_delete_pay_execute(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    method_id = int(callback.data.split("_")[2])
    try:
        # Fix: Audit Logging for Payment Methods (S-01)
        async with db_manager.transaction() as db:
            await db_manager.soft_delete_payment_method(method_id, db_conn=db, commit=False)
            await db_manager.log_admin_action(
                admin_id=callback.from_user.id,
                action="DELETE_PAYMENT_METHOD",
                target_type="SETTING",
                target_id=method_id,
                details=f"Soft deleted payment method ID: {method_id}",
                db_conn=db,
                commit=False
            )
        await callback.answer("✅ تم الحذف (Soft Delete)")
        await admin_payment_methods_main(callback, is_operator)
    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.answer("❌ فشل الحذف")
