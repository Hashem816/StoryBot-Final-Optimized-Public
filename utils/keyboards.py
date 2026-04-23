from aiogram.types import KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config.settings import UserRole
from utils.translations import get_text

def get_main_menu(user_role: str = UserRole.USER, lang: str = "ar"):
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=get_text("btn_store", lang)), 
        KeyboardButton(text=get_text("btn_account", lang))
    )
    builder.row(
        KeyboardButton(text=get_text("btn_orders", lang)), 
        KeyboardButton(text=get_text("btn_balance", lang))
    )
    builder.row(
        KeyboardButton(text=get_text("btn_support", lang)),
        KeyboardButton(text="🌐 اللغة / Language")
    )
    
    is_staff = user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
    if is_staff:
        builder.row(KeyboardButton(text=get_text("btn_admin_panel", lang)))
        
    return builder.as_markup(resize_keyboard=True)

def get_admin_main_menu(user_role: str, lang: str = "ar"):
    builder = InlineKeyboardBuilder()
    # v2.3 REBORN prefixes
    builder.row(InlineKeyboardButton(text="📦 الطلبات", callback_data="adm_ords"))
    
    if user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR]:
        builder.row(InlineKeyboardButton(text="🛒 المنتجات", callback_data="adm_prods"))
        builder.row(InlineKeyboardButton(text="💳 طرق الدفع", callback_data="adm_paym"))
    
    if user_role == UserRole.SUPER_ADMIN:
        builder.row(InlineKeyboardButton(text="🔌 وضع التشغيل", callback_data="adm_mode"))
        builder.row(InlineKeyboardButton(text="💵 سعر الدولار", callback_data="adm_rate"))
        builder.row(InlineKeyboardButton(text="👥 المستخدمين", callback_data="adm_usrs"))
        builder.row(InlineKeyboardButton(text="🎟️ الكوبونات", callback_data="adm_coup"))
        builder.row(InlineKeyboardButton(text="📊 الإحصائيات", callback_data="adm_stats"))
        builder.row(InlineKeyboardButton(text="📢 إذاعة", callback_data="adm_bcst"))
        builder.row(InlineKeyboardButton(text="📋 السجل", callback_data="adm_audit"))
        
    return builder.as_markup()

def get_categories_keyboard(categories, is_admin=False):
    builder = InlineKeyboardBuilder()
    # prefix length: 2 chars + 1 underscore + id
    prefix = "ac_v_" if is_admin else "c_v_"
    for cat in categories:
        builder.row(InlineKeyboardButton(text=cat['name'], callback_data=f"{prefix}{cat['id']}"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ إضافة قسم", callback_data="ac_add"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="adm_main"))
    return builder.as_markup()

def get_products_keyboard(products, category_id, rate_cents, is_admin=False):
    builder = InlineKeyboardBuilder()
    # prefix length: 2 chars + 1 underscore + id
    prefix = "ap_v_" if is_admin else "p_v_"
    for prod in products:
        price_usd_cents = prod['price_usd']
        price_local_cents = (price_usd_cents * rate_cents) // 100
        text = f"{prod['name']} - {price_local_cents/100:,.0f} ل.س"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"{prefix}{prod['id']}"))
    
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ إضافة منتج", callback_data=f"ap_add_{category_id}"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="adm_prods"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="back_to_cats"))
    return builder.as_markup()

def get_admin_order_actions(order_id: int, status: str):
    builder = InlineKeyboardBuilder()
    if status == "PAID":
        builder.row(InlineKeyboardButton(text="✅ تأكيد الدفع", callback_data=f"ao_ap_{order_id}"))
        builder.row(InlineKeyboardButton(text="❌ رفض", callback_data=f"ao_rj_{order_id}"))
    elif status == "IN_PROGRESS":
        builder.row(InlineKeyboardButton(text="✅ إكمال", callback_data=f"ao_cp_{order_id}"))
    
    builder.row(InlineKeyboardButton(text="❌ إلغاء", callback_data=f"ao_cl_{order_id}"))
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="adm_ords"))
    return builder.as_markup()

def get_order_confirm_keyboard(product_id, lang: str = "ar"):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تأكيد الشراء", callback_data=f"cb_v_{product_id}"),
        InlineKeyboardButton(text="🎟️ كوبون", callback_data=f"uc_v_{product_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="back_to_cats"))
    return builder.as_markup()

def get_payment_methods_keyboard(methods, is_admin=False):
    builder = InlineKeyboardBuilder()
    # تم تغيير البادئة من ap_ إلى apm_ لمنع التداخل مع أزرار المنتجات (v2.3 REBORN)
    prefix = "apm_v_" if is_admin else "p_m_"
    for m in methods:
        builder.row(InlineKeyboardButton(text=m['name'], callback_data=f"{prefix}{m['id']}"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ إضافة طريقة دفع", callback_data="apm_add"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="adm_main"))
    return builder.as_markup()
