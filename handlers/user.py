"""
معالج المستخدم - v2.3
التحسينات:
- دعم الترجمة الكاملة لجميع الرسائل
- تحسين منطق الطلبات والكوبونات
- تحسين واجهة المستخدم (NL-01)
"""

from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from services.order_service import OrderService as order_service
from utils.keyboards import get_main_menu, get_categories_keyboard, get_products_keyboard, get_order_confirm_keyboard
from utils.translations import get_text, get_user_language
from utils.helpers import validate_player_id, clean_html
import logging

router = Router()
logger = logging.getLogger(__name__)

class OrderProcess(StatesGroup):
    waiting_for_player_id = State()
    confirming = State()
    waiting_for_coupon = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, user_role: str, user: dict):
    lang = get_user_language(user) or "ar"
    await message.answer(get_text("welcome", lang), reply_markup=get_main_menu(user_role, lang))

@router.message(F.text.in_(["🌐 اللغة / Language"]))
async def cmd_change_language(message: types.Message):
    from handlers.language import show_language_selection
    # محاكاة callback_query بسيطة لاستدعاء الدالة الموجودة
    class MockCallback:
        def __init__(self, message):
            self.message = message
    await show_language_selection(MockCallback(message))

@router.message(F.text.in_(["👤 حسابي", "👤 My Account"]))
async def show_account(message: types.Message, user: dict):
    if not user:
        return await message.answer("❌ خطأ في جلب بياناتك.")
    
    lang = get_user_language(user) or "ar"
    completed_orders = await db_manager.get_completed_orders_count(user['telegram_id'])
    
    # M-03: عرض بيانات الحساب بأمان
    name = user.get('first_name') or "غير محدد"
    username = f"@{user['username']}" if user.get('username') else "غير محدد"
    balance = user.get('balance', 0) / 100
    joined = user.get('created_at', "غير معروف")
    
    if lang == "ar":
        text = (
            f"👤 <b>بيانات حسابك</b>\n\n"
            f"🔹 الاسم: {name}\n"
            f"🔹 اليوزر: {username}\n"
            f"🔹 المعرف: <code>{user['telegram_id']}</code>\n"
            f"🔹 الرصيد: <b>{balance:.2f}$</b>\n"
            f"🔹 الطلبات المكتملة: {completed_orders}\n"
            f"🔹 تاريخ الانضمام: {joined}"
        )
    else:
        text = (
            f"👤 <b>Your Account</b>\n\n"
            f"🔹 Name: {name}\n"
            f"🔹 Username: {username}\n"
            f"🔹 ID: <code>{user['telegram_id']}</code>\n"
            f"🔹 Balance: <b>{balance:.2f}$</b>\n"
            f"🔹 Completed Orders: {completed_orders}\n"
            f"🔹 Joined: {joined}"
        )
    await message.answer(text)

@router.message(F.text.in_(["📦 طلباتي", "📦 My Orders"]))
async def show_my_orders(message: types.Message, user: dict):
    lang = get_user_language(user) or "ar"
    try:
        orders = await db_manager.get_user_orders(user['telegram_id'], limit=10)
        if not orders:
            msg = "📦 لا توجد طلبات بعد." if lang == "ar" else "📦 No orders yet."
            return await message.answer(msg)
        
        text = "📦 <b>آخر 10 طلبات لك:</b>\n\n" if lang == "ar" else "📦 <b>Your last 10 orders:</b>\n\n"
        for o in orders:
            status_icon = "✅" if o['status'] == "COMPLETED" else "⏳" if o['status'] in ["PAID", "IN_PROGRESS"] else "❌"
            text += f"{status_icon} #{o['id']} | {o['product_name']} | {o['status']}\n"
            
        await message.answer(text)
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        await message.answer("❌ حدث خطأ أثناء جلب الطلبات." if lang == "ar" else "❌ Error fetching orders.")

@router.message(F.text.in_(["❓ الدعم", "❓ Support"]))
async def show_support(message: types.Message, user: dict):
    lang = get_user_language(user) or "ar"
    try:
        support_msg = await db_manager.get_setting('support_message')
        if not support_msg:
            support_msg = "تواصل معنا عبر المعرف التالي: @Support" if lang == "ar" else "Contact us at: @Support"
        
        await message.answer(f"❓ <b>الدعم الفني</b>\n\n{support_msg}")
    except Exception as e:
        logger.error(f"Error fetching support: {e}")
        await message.answer("تواصل مع الإدارة للدعم." if lang == "ar" else "Contact admin for support.")

@router.message(F.text.in_(["🛒 المتجر", "🛒 Store"]))
async def show_categories(message: types.Message, user: dict):
    lang = get_user_language(user)
    if await db_manager.has_open_order(user['telegram_id']):
        msg = "⚠️ لديك طلب قيد المعالجة، يرجى انتظاره أولاً." if lang == "ar" else "⚠️ You have a pending order, please wait for it."
        return await message.answer(msg)
    
    categories = await db_manager.get_categories()
    msg = "📁 اختر القسم:" if lang == "ar" else "📁 Select Category:"
    await message.answer(msg, reply_markup=get_categories_keyboard(categories))

@router.callback_query(F.data == "back_to_cats")
async def back_to_categories(callback: types.CallbackQuery, user: dict):
    lang = get_user_language(user)
    categories = await db_manager.get_categories()
    msg = "📁 اختر القسم:" if lang == "ar" else "📁 Select Category:"
    await callback.message.edit_text(msg, reply_markup=get_categories_keyboard(categories))

@router.callback_query(F.data.startswith("c_v_"))
async def show_products(callback: types.CallbackQuery, user: dict):
    lang = get_user_language(user)
    cat_id = int(callback.data.split("_")[2])
    products = await db_manager.get_products(category_id=cat_id)
    rate_cents = int(await db_manager.get_setting("dollar_rate", "1250000"))
    msg = "📦 اختر المنتج:" if lang == "ar" else "📦 Select Product:"
    await callback.message.edit_text(msg, reply_markup=get_products_keyboard(products, cat_id, rate_cents))

@router.callback_query(F.data.startswith("p_v_"))
async def product_details(callback: types.CallbackQuery, state: FSMContext, user: dict):
    prod_id = int(callback.data.split("_")[2])
    product = await db_manager.get_product(prod_id)
    if not product: return await callback.answer("❌ المنتج غير موجود", show_alert=True)
    
    lang = get_user_language(user)
    rate_cents = int(await db_manager.get_setting("dollar_rate", "1250000"))
    price_usd_cents = product['price_usd']
    price_local_cents = (price_usd_cents * rate_cents) // 100
    
    await state.update_data(selected_prod_id=prod_id)
    await state.set_state(OrderProcess.waiting_for_player_id)
    
    # M-05: التحقق من الحاجة لمعرف اللاعب
    requires_id = product.get('requires_player_id', 1) == 1
    
    if not requires_id:
        await state.update_data(player_id="N/A")
        # الانتقال مباشرة للتأكيد
        await state.set_state(OrderProcess.confirming)
        return await show_order_confirmation(callback.message, state, user, product, price_usd_cents, price_local_cents)

    if lang == "ar":
        text = (
            f"📝 <b>{product['name']}</b>\n\n"
            f"📄 {product['description']}\n\n"
            f"💰 السعر: {price_usd_cents/100:.2f}$\n"
            f"💵 السعر المحلي: {price_local_cents/100:,.0f} ل.س\n\n"
            f"🆔 أدخل معرف اللاعب (Player ID):"
        )
    else:
        text = (
            f"📝 <b>{product['name']}</b>\n\n"
            f"📄 {product['description']}\n\n"
            f"💰 Price: {price_usd_cents/100:.2f}$\n"
            f"💵 Local Price: {price_local_cents/100:,.0f} SYP\n\n"
            f"🆔 Enter Player ID:"
        )
    await callback.message.edit_text(text)

async def show_order_confirmation(message, state, user, product, price_usd_cents, price_local_cents):
    lang = get_user_language(user) or "ar"
    data = await state.get_data()
    player_id = data.get('player_id', 'N/A')
    
    if lang == "ar":
        text = (
            f"⚠️ <b>تأكيد الطلب</b>\n\n"
            f"📦 المنتج: {product['name']}\n"
            f"🆔 المعرف: <code>{player_id}</code>\n"
            f"💰 السعر: {price_local_cents/100:,.0f} ل.س ({price_usd_cents/100:.2f}$)\n\n"
            f"💰 رصيدك الحالي: {user['balance']/100:.2f}$"
        )
    else:
        text = (
            f"⚠️ <b>Order Confirmation</b>\n\n"
            f"📦 Product: {product['name']}\n"
            f"🆔 ID: <code>{player_id}</code>\n"
            f"💰 Price: {price_local_cents/100:,.0f} SYP ({price_usd_cents/100:.2f}$)\n\n"
            f"💰 Current Balance: {user['balance']/100:.2f}$"
        )
    
    if hasattr(message, 'edit_text'):
        await message.edit_text(text, reply_markup=get_order_confirm_keyboard(product['id']))
    else:
        await message.answer(text, reply_markup=get_order_confirm_keyboard(product['id']))

@router.message(OrderProcess.waiting_for_player_id)
async def process_player_id(message: types.Message, state: FSMContext, user: dict):
    lang = get_user_language(user) or "ar"
    player_id = message.text.strip()
    
    # Fixed S-02: Input Validation for Player ID
    if not validate_player_id(player_id):
        msg = "⚠️ معرف اللاعب غير صالح. يرج Maryland إدخال معرف صحيح (أرقام وحروف فقط)." if lang == "ar" else "⚠️ Invalid Player ID. Please enter a valid ID (alphanumeric only)."
        return await message.answer(msg)
    
    data = await state.get_data()
    product = await db_manager.get_product(data['selected_prod_id'])
    rate_cents = int(await db_manager.get_setting("dollar_rate", "1250000"))
    price_usd_cents = product['price_usd']
    price_local_cents = (price_usd_cents * rate_cents) // 100
    
    await state.update_data(player_id=player_id)
    await state.set_state(OrderProcess.confirming)
    await show_order_confirmation(message, state, user, product, price_usd_cents, price_local_cents)

@router.callback_query(F.data.startswith("cb_v_"))
async def confirm_purchase(callback: types.CallbackQuery, state: FSMContext, user: dict, bot: Bot):
    lang = get_user_language(user)
    data = await state.get_data()
    product_id = int(callback.data.split("_")[2])
    player_id = data['player_id']
    
    success, msg, order_id = await order_service.create_order(user_id=user['telegram_id'], product_id=product_id, player_id=player_id)
    if success:
        text = f"✅ تم إنشاء الطلب بنجاح!\n📦 رقم الطلب: <b>#{order_id}</b>\n⏳ جاري التنفيذ..." if lang == "ar" else f"✅ Order created successfully!\n📦 Order ID: <b>#{order_id}</b>\n⏳ Processing..."
        await callback.message.edit_text(text)
        
        # Fixed L-05/P-01: Admin Notification for new orders with pre-fetched data
        from utils.notifications import notification_service
        product = await db_manager.get_product(product_id)
        order_data = {
            'product_name': product['name'] if product else 'Unknown',
            'username': f"@{user['username']}" if user.get('username') else 'N/A'
        }
        await notification_service.notify_admins_new_order(order_id, user['telegram_id'], product_id, bot, order_data=order_data)
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)
    await state.clear()

@router.callback_query(F.data.startswith("uc_v_"))
async def use_coupon_start(callback: types.CallbackQuery, state: FSMContext, user: dict):
    lang = get_user_language(user)
    await state.set_state(OrderProcess.waiting_for_coupon)
    # Fix: Unified HTML Parse Mode
    await callback.message.edit_text(get_text("coupon_prompt", lang))

@router.message(OrderProcess.waiting_for_coupon)
async def process_coupon(message: types.Message, state: FSMContext, user: dict):
    lang = get_user_language(user) or "ar"
    coupon_code = message.text.strip().upper()
    data = await state.get_data()
    
    # M-06: فحص مسبق للكوبون قبل الدخول في الـ transaction
    coupon = await db_manager.get_coupon(coupon_code)
    if not coupon:
        msg = "❌ الكوبون غير صالح." if lang == "ar" else "❌ Invalid coupon."
        return await message.answer(msg)

    success, msg, order_id = await order_service.create_order(
        user_id=user['telegram_id'],
        product_id=data['selected_prod_id'],
        player_id=data['player_id'],
        coupon_code=coupon_code
    )
    
    if success:
        text = f"✅ {get_text('coupon_applied', lang, discount='')}\n📦 رقم الطلب: <code>#{order_id}</code>\n⏳ جاري التنفيذ..." if lang == "ar" else f"✅ Coupon applied!\n📦 Order ID: <code>#{order_id}</code>\n⏳ Processing..."
        await message.answer(text)
        await state.clear()
    else:
        retry_msg = f"❌ {msg}\n\nيرجى المحاولة مرة أخرى أو كتابة 'إلغاء' للعودة." if lang == "ar" else f"❌ {msg}\n\nPlease try again or type 'cancel' to go back."
        await message.answer(retry_msg)
