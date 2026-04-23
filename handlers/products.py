from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_categories_keyboard, get_products_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

class ProductWizard(StatesGroup):
    waiting_for_cat_name = State()
    waiting_for_prod_name = State()
    waiting_for_prod_desc = State()
    waiting_for_prod_price = State()
    waiting_for_prod_id_req = State()
    waiting_for_prod_type = State()

@router.callback_query(F.data == "adm_prods")
async def admin_products_main(event: types.CallbackQuery | types.Message, is_operator: bool):
    """دعم الاستدعاء من Message و CallbackQuery (v2.3 REBORN)"""
    if not is_operator: return
    
    try:
        categories = await db_manager.get_categories(only_active=False)
        text = "🛒 <b>إدارة الأقسام والمنتجات</b>\n\nاختر قسماً لعرض منتجاته أو إدارتها:"
        reply_markup = get_categories_keyboard(categories, is_admin=True)
        
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in admin_products_main: {e}")
        if isinstance(event, types.CallbackQuery): await event.answer("❌ حدث خطأ")

@router.callback_query(F.data == "ac_add")
async def admin_cat_add_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    if not is_operator: return
    await state.set_state(ProductWizard.waiting_for_cat_name)
    await callback.message.edit_text("📂 *أدخل اسم القسم الجديد:*", 
                                     reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data="adm_prods")]]),
                                     parse_mode="Markdown")

@router.message(ProductWizard.waiting_for_cat_name)
async def admin_cat_add_finish(message: types.Message, state: FSMContext, is_operator: bool):
    if not is_operator: return
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        return await message.answer("⚠️ اسم القسم غير صالح.", parse_mode="Markdown")

    try:
        async with db_manager.transaction() as db:
            await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await state.clear()
        await message.answer(f"✅ تم إضافة القسم: `{name}`", parse_mode="Markdown")
        await admin_products_main(message, is_operator)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ فشل إضافة القسم.", parse_mode="Markdown")

@router.callback_query(F.data.startswith("ac_v_"))
async def admin_cat_view(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    cat_id = int(callback.data.split("_")[2])
    products = await db_manager.get_products(category_id=cat_id, only_active=False)
    rate_cents = int(await db_manager.get_setting("dollar_rate", "1250000"))
    
    await callback.message.edit_text(
        f"📦 *منتجات القسم:*", 
        reply_markup=get_products_keyboard(products, cat_id, rate_cents, is_admin=True), 
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("ap_add_"))
async def admin_prod_add_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    if not is_operator: return
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(cat_id=cat_id)
    await state.set_state(ProductWizard.waiting_for_prod_name)
    await callback.message.edit_text("📦 *أدخل اسم المنتج الجديد:*", parse_mode="Markdown")

@router.message(ProductWizard.waiting_for_prod_name)
async def admin_prod_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductWizard.waiting_for_prod_desc)
    await message.answer("📝 *أدخل وصف المنتج:*", parse_mode="Markdown")

@router.message(ProductWizard.waiting_for_prod_desc)
async def admin_prod_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text.strip())
    await state.set_state(ProductWizard.waiting_for_prod_price)
    await message.answer("💰 *أدخل سعر المنتج بالدولار (مثلاً: 5.50):*", parse_mode="Markdown")

@router.message(ProductWizard.waiting_for_prod_price)
async def admin_prod_price(message: types.Message, state: FSMContext):
    try:
        price_float = float(message.text.strip().replace('$', ''))
        price_cents = int(round(price_float * 100))
        await state.update_data(price_cents=price_cents)
        
        await state.set_state(ProductWizard.waiting_for_prod_id_req)
        builder = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ نعم", callback_data="ap_req_1"),
             types.InlineKeyboardButton(text="❌ لا", callback_data="ap_req_0")]
        ])
        await message.answer("🆔 <b>هل يحتاج هذا المنتج معرف لاعب؟</b>", reply_markup=builder)
    except ValueError:
        await message.answer("⚠️ يرجى إدخال سعر صحيح.")

@router.callback_query(ProductWizard.waiting_for_prod_id_req, F.data.startswith("ap_req_"))
async def admin_prod_id_req(callback: types.CallbackQuery, state: FSMContext):
    req_val = int(callback.data.split("_")[2])
    await state.update_data(requires_player_id=req_val)
    
    await state.set_state(ProductWizard.waiting_for_prod_type)
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🤖 تلقائي (API)", callback_data="ap_t_AUTO")],
        [types.InlineKeyboardButton(text="👤 يدوي", callback_data="ap_t_MANUAL")],
        [types.InlineKeyboardButton(text="❌ إلغاء", callback_data="adm_prods")]
    ])
    await callback.message.edit_text("⚙️ <b>اختر نوع تنفيذ المنتج:</b>", reply_markup=builder)

@router.callback_query(F.data.startswith("ap_t_"))
async def admin_prod_type_select(callback: types.CallbackQuery, state: FSMContext):
    prod_type = callback.data.split("_")[2]
    await state.update_data(type=prod_type)
    await finish_product_creation(callback, state)

async def finish_product_creation(event, state: FSMContext):
    data = await state.get_data()
    try:
        async with db_manager.transaction() as db:
            await db.execute("""
                INSERT INTO products (category_id, name, description, price_usd, type, requires_player_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data['cat_id'], data['name'], data['desc'], data['price_cents'], data.get('type', 'MANUAL'), data.get('requires_player_id', 1)))
        await state.clear()
        msg = f"✅ تم إضافة المنتج: <b>{data['name']}</b>"
        if isinstance(event, types.CallbackQuery): await event.message.answer(msg)
        else: await event.answer(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        await event.answer("❌ فشل الحفظ", parse_mode="Markdown")
