# تعريف أوامر إنشاء الجداول لقاعدة بيانات SQLite v2.3 - Ultimate Production
# تم التحويل من REAL إلى INTEGER (نظام السنتات) لضمان الدقة المالية
# تمت إضافة قيود CHECK لضمان عدم وجود قيم سالبة
# تمت إضافة حقل metadata للطلبات لتخزين تفاصيل إضافية

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    balance INTEGER DEFAULT 0 CHECK(balance >= 0), -- القيمة بالسنتات (100 = 1.00 دولار)
    role TEXT DEFAULT 'USER', -- SUPER_ADMIN, OPERATOR, SUPPORT, USER
    is_blocked INTEGER DEFAULT 0,
    daily_order_limit INTEGER DEFAULT 10,
    internal_notes TEXT,
    is_active INTEGER DEFAULT 1,
    language TEXT DEFAULT 'ar', -- ar, en
    currency TEXT DEFAULT 'USD', -- USD, SYP
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_USERS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_users_search 
ON users(telegram_id, username, first_name, last_name);
"""

CREATE_CATEGORIES_TABLE = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);
"""

CREATE_PROVIDERS_TABLE = """
CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT,
    base_url TEXT,
    is_active INTEGER DEFAULT 1
);
"""

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER,
    provider_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    price_usd INTEGER NOT NULL CHECK(price_usd >= 0), -- السعر بالسنتات
    type TEXT DEFAULT 'MANUAL', -- AUTOMATIC, MANUAL, DISABLED
    variation_id TEXT, 
    is_active INTEGER DEFAULT 1,
    requires_player_id INTEGER DEFAULT 1, -- M-05: 1 = يحتاج ID، 0 = لا يحتاج
    FOREIGN KEY(category_id) REFERENCES categories(id),
    FOREIGN KEY(provider_id) REFERENCES providers(id)
);
"""

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    player_id TEXT,
    price_usd INTEGER CHECK(price_usd >= 0), -- السعر بالسنتات وقت الطلب
    price_local INTEGER CHECK(price_local >= 0), -- السعر بالعملة المحلية وقت الطلب
    exchange_rate INTEGER CHECK(exchange_rate > 0), -- سعر الصرف (مضروب بـ 100 لتجنب الكسور، مثال: 1250000 تعني 12500.00)
    status TEXT DEFAULT 'NEW', -- NEW, PENDING_PAYMENT, PAID, PENDING_REVIEW, IN_PROGRESS, COMPLETED, FAILED, CANCELED
    payment_method_id INTEGER,
    payment_receipt_file_id TEXT, -- صورة الإيصال
    execution_type TEXT DEFAULT 'MANUAL',
    admin_notes TEXT,
    metadata TEXT, -- لتخزين تفاصيل إضافية (JSON: IP, Port, User, Pass, etc.)
    operator_id INTEGER, -- من قام بتأكيد الطلب
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, -- M-06: يتم تحديثه عبر Trigger أو يدوياً في الكود
    FOREIGN KEY(user_id) REFERENCES users(telegram_id),
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(payment_method_id) REFERENCES payment_methods(id)
);
"""

CREATE_FINANCIAL_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS financial_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    order_id INTEGER,
    type TEXT, -- DEPOSIT, WITHDRAWAL, REFUND, PURCHASE, EXCHANGE_CHANGE, ADMIN_ADJUST
    amount INTEGER NOT NULL,
    balance_before INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    admin_id INTEGER,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
);
"""

CREATE_TRUST_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS trust_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    user_id INTEGER,
    action_text TEXT,
    execution_type TEXT, 
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
);
"""

CREATE_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

CREATE_PAYMENT_METHODS_TABLE = """
CREATE TABLE IF NOT EXISTS payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    deleted_at DATETIME DEFAULT NULL
);
"""

CREATE_COUPONS_TABLE = """
CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL, -- PERCENT, FIXED (H-01)
    value INTEGER NOT NULL CHECK(value >= 0), -- القيمة بالسنتات أو كنسبة مئوية
    max_uses INTEGER DEFAULT 1,
    used_count INTEGER DEFAULT 0,
    min_amount INTEGER DEFAULT 0 CHECK(min_amount >= 0),
    is_active INTEGER DEFAULT 1,
    expires_at DATETIME,
    created_by INTEGER,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES users(telegram_id)
);
"""

CREATE_COUPON_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS coupon_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    order_id INTEGER,
    discount_amount INTEGER CHECK(discount_amount >= 0),
    used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coupon_id, user_id), -- H-05: منع استخدام الكوبون أكثر من مرة لنفس المستخدم
    FOREIGN KEY(coupon_id) REFERENCES coupons(id),
    FOREIGN KEY(user_id) REFERENCES users(telegram_id),
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
"""

CREATE_AUDIT_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT, -- USER, ORDER, PRODUCT, COUPON, SETTING
    target_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(admin_id) REFERENCES users(telegram_id)
);
"""

CREATE_BROADCAST_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS broadcast_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    message_text TEXT,
    target_count INTEGER,
    success_count INTEGER,
    fail_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(admin_id) REFERENCES users(telegram_id)
);
"""

CREATE_RATE_LIMITS_TABLE = """
CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    window_start DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
);
"""

CREATE_ADMIN_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS admin_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    session_token TEXT UNIQUE,
    is_active INTEGER DEFAULT 1,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(admin_id) REFERENCES users(telegram_id)
);
"""

# الإعدادات الافتراضية للنظام المطور
DEFAULT_SETTINGS = [
    ('store_mode', 'MANUAL'), # AUTO, MANUAL, MAINTENANCE, EMERGENCY
    ('dollar_rate', '1250000'), # سعر الصرف الافتراضي بالسنتات (12500.00)
    ('auto_update_rate', '0'),
    ('global_daily_limit', '10'),
    ('emergency_stop', '0'),
    ('maintenance_message', '🛠 المتجر في حالة صيانة حالياً، سنعود قريباً.'),
    ('support_message', 'تواصل معنا عبر المعرف التالي: @Support'),
    ('admin_password', ''),  # كلمة سر لوحة الأدمن (فارغة = معطلة)
    ('require_admin_password', '0'),  # 0 = معطل, 1 = مفعل
    ('default_language', 'ar'),  # اللغة الافتراضية
]
