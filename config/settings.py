import os
from dotenv import load_dotenv
from pathlib import Path

# تحميل متغيرات البيئة من ملف .env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# إعدادات البوت الأساسية (دعم قائمة الأدمن لضمان عدم فقدان الوصول)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # التحقق من وجود التوكن (H-06)
    raise ValueError("CRITICAL: BOT_TOKEN environment variable is not set! Please check your .env file.")

# تحويل ADMIN_IDS إلى قائمة من الأرقام
admin_ids_str = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 0

# إعدادات قاعدة البيانات (تأمين المسار)
BASE_DIR = Path(__file__).resolve().parent.parent
# استخدام مسار مطلق لضمان عدم حذف قاعدة البيانات عند إعادة التشغيل في بعض البيئات
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "store_v2.db"))
DATABASE_PATH = DB_PATH

# أوضاع المتجر العالمية (v2.3)
class StoreMode:
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY" # وضع الطوارئ لحماية العمليات المالية

# رتب المستخدمين
class UserRole:
    SUPER_ADMIN = "SUPER_ADMIN"
    OPERATOR = "OPERATOR"
    SUPPORT = "SUPPORT"
    USER = "USER"

# دورة حياة الطلب الكاملة
class OrderStatus:
    NEW = "NEW"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

# أنواع المنتجات
class ProductType:
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    DISABLED = "DISABLED"

# أنواع الكوبونات (H-01)
class CouponType:
    PERCENT = "PERCENT"
    FIXED = "FIXED"

# إعدادات APIs الخارجية (اختيارية - v2.3 REBORN)
ITEM4GAMER_API_KEY = os.getenv("ITEM4GAMER_API_KEY", "")
ITEM4GAMER_BASE_URL = os.getenv("ITEM4GAMER_BASE_URL", "https://api.item4gamer.com/v1")
