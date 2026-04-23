"""
نظام إدارة الطلبات - v2.3
التحسينات:
- استخدام order_service.finalize_order لجميع حالات الإغلاق (ضمان استرداد الرصيد)
- دعم الترجمة الكاملة
- إضافة سجل التدقيق عند تأكيد الدفع (UF-02)
"""

from aiogram import Router, F, types, Bot
from database.manager import db_manager
from services.order_service import OrderService as order_service
from utils.keyboards import get_admin_order_actions
from utils.translations import get_text, get_user_language
from config.settings import OrderStatus
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "adm_ords")
async def list_active_orders(callback: types.CallbackQuery, user: dict, **kwargs):
    lang = get_user_language(user)
    try:
        orders = await db_manager.get_active_orders(limit=20)
        if not orders:
            builder = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main")]])
            return await callback.message.edit_text("📭 لا توجد طلبات نشطة حالياً.", reply_markup=builder)

        builder = types.InlineKeyboardMarkup(inline_keyboard=[])
        for ord in orders:
            status_icon = "📸" if ord['status'] == OrderStatus.PAID else "⏳" if ord['status'] == OrderStatus.IN_PROGRESS else "👀"
            # M-09: حماية من None
            username = f"@{ord['username']}" if ord.get('username') else str(ord['telegram_id'])
            builder.inline_keyboard.append([
                types.InlineKeyboardButton(text=f"{status_icon} #{ord['id']} | {ord['name']} | {username}", callback_data=f"ao_v_{ord['id']}")
            ])
        builder.inline_keyboard.append([types.InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="adm_main")])
        
        await callback.message.edit_text("📦 <b>إدارة الطلبات النشطة:</b>", reply_markup=builder)
    except Exception as e:
        logger.error(f"Error in list_active_orders: {e}")
        await callback.answer("❌ حدث خطأ")

@router.callback_query(F.data.startswith("ao_v_"))
async def view_order_details(callback: types.CallbackQuery, **kwargs):
    order_id = int(callback.data.split("_")[2])
    order = await db_manager.get_order(order_id)
    if not order: return await callback.answer("❌ الطلب غير موجود")
        
    username = f"@{order['username']}" if order.get('username') else "لا يوجد"
    text = (
        f"📑 <b>تفاصيل الطلب #{order_id}</b>\n\n"
        f"👤 المستخدم: {username} (<code>{order['telegram_id']}</code>)\n"
        f"📦 المنتج: {order['product_name']}\n"
        f"🆔 معرف اللاعب: <code>{order['player_id']}</code>\n"
        f"💰 السعر: <b>{order['price_local']/100:,.0f} ل.س</b> ({order['price_usd']/100}$)\n"
        f"📍 الحالة: <code>{order['status']}</code>\n"
        f"📅 التاريخ: <code>{order['created_at']}</code>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_order_actions(order_id, order['status']))

@router.callback_query(F.data.startswith("ao_ap_"))
async def approve_payment(callback: types.CallbackQuery, bot: Bot, **kwargs):
    """
    NR-04: تأكيد الدفع بشكل ذري عبر الخدمة.
    """
    order_id = int(callback.data.split("_")[2])
    admin_id = callback.from_user.id
    
    success, msg = await order_service.approve_payment(order_id, admin_id)
    if not success:
        return await callback.answer(f"❌ {msg}", show_alert=True)

    await callback.answer("✅ تم تأكيد الإيصال.")
    
    order = await db_manager.get_order(order_id)
    user_data = await db_manager.get_user(order['telegram_id'])
    lang = get_user_language(user_data)
    msg_text = f"✅ تم تأكيد إيصال الدفع للطلب `#{order_id}`.\nجاري تنفيذ طلبك الآن..." if lang == "ar" else f"✅ Payment confirmed for order `#{order_id}`."
    await bot.send_message(order['telegram_id'], msg_text, )
    await list_active_orders(callback, user_data)

@router.callback_query(F.data.startswith("ao_rj_"))
async def reject_payment(callback: types.CallbackQuery, bot: Bot, **kwargs):
    order_id = int(callback.data.split("_")[2])
    admin_id = callback.from_user.id
    success, msg = await order_service.finalize_order(order_id=order_id, status=OrderStatus.FAILED, admin_id=admin_id, admin_notes="تم رفض الإيصال")
    if success:
        await callback.answer("❌ تم رفض الإيصال.")
        order = await db_manager.get_order(order_id)
        user_data = await db_manager.get_user(order['telegram_id'])
        lang = get_user_language(user_data)
        text = f"❌ تم رفض إيصال الدفع للطلب `#{order_id}`." if lang == "ar" else f"❌ Payment rejected for order `#{order_id}`."
        await bot.send_message(order['telegram_id'], text, )
    else: await callback.answer(f"❌ {msg}", show_alert=True)
    await list_active_orders(callback, {})

@router.callback_query(F.data.startswith("ao_cp_"))
async def complete_order(callback: types.CallbackQuery, bot: Bot, **kwargs):
    order_id = int(callback.data.split("_")[2])
    admin_id = callback.from_user.id
    success, msg = await order_service.finalize_order(order_id=order_id, status=OrderStatus.COMPLETED, admin_id=admin_id)
    if success:
        await callback.answer("✅ تم إكمال الطلب.")
        order = await db_manager.get_order(order_id)
        user_data = await db_manager.get_user(order['telegram_id'])
        lang = get_user_language(user_data)
        text = f"✅ تم تنفيذ طلبك `#{order_id}` بنجاح." if lang == "ar" else f"✅ Order `#{order_id}` completed."
        await bot.send_message(order['telegram_id'], text, )
    else: await callback.answer(f"❌ {msg}", show_alert=True)
    await list_active_orders(callback, {})

@router.callback_query(F.data.startswith("ao_cl_"))
async def cancel_order(callback: types.CallbackQuery, bot: Bot, **kwargs):
    order_id = int(callback.data.split("_")[2])
    admin_id = callback.from_user.id
    success, msg = await order_service.finalize_order(order_id=order_id, status=OrderStatus.CANCELED, admin_id=admin_id, admin_notes="إلغاء من المسؤول")
    if success:
        await callback.answer("❌ تم إلغاء الطلب.")
        order = await db_manager.get_order(order_id)
        user_data = await db_manager.get_user(order['telegram_id'])
        lang = get_user_language(user_data)
        text = f"❌ تم إلغاء طلبك `#{order_id}` وإرجاع الرصيد." if lang == "ar" else f"❌ Order `#{order_id}` canceled and balance refunded."
        await bot.send_message(order['telegram_id'], text, )
    else: await callback.answer(f"❌ {msg}", show_alert=True)
    await list_active_orders(callback, {})
