"""
Order Service Layer - طبقة خدمات الطلبات (v2.3)
التحسينات:
- دعم نظام السنتات (INTEGER) للدقة المالية المليارية
- التحقق من المخزون والسعر وطريقة الدفع وحالة المتجر
- إنشاء طلب آمن مع Transactions (Atomic Operations) باستخدام Connection Pooling
- توحيد منطق إنهاء الطلبات (finalize_order) لضمان استرداد الرصيد وتسجيل التدقيق
"""

import logging
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from database.manager import db_manager
from config.settings import OrderStatus, ProductType, StoreMode

logger = logging.getLogger(__name__)

class OrderValidationError(Exception):
    """استثناء مخصص لأخطاء التحقق من الطلبات"""
    pass

class OrderService:
    """خدمة إدارة الطلبات"""
    
    @staticmethod
    async def validate_order(
        user_id: int,
        product_id: int,
        player_id: str,
        payment_method_id: Optional[int] = None,
        db_conn = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        التحقق من صلاحية الطلب قبل إنشائه (دعم نظام السنتات)
        """
        try:
            # استخدام الاتصال الممرر أو الاتصال العام للقراءة
            db = db_conn or await db_manager.connect()
            
            # 1. التحقق من المستخدم
            async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
            if not user:
                return False, "المستخدم غير موجود", None
            
            if user['is_blocked']:
                return False, "حسابك محظور. يرجى التواصل مع الدعم.", None
            
            # 2. التحقق من المنتج
            async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
                product = await cursor.fetchone()
            if not product:
                return False, "المنتج غير موجود", None
            
            if not product['is_active']:
                return False, "المنتج غير متاح حالياً", None
            
            if product['type'] == ProductType.DISABLED:
                return False, "المنتج معطل", None
            
            # 3. التحقق من حالة المتجر
            async with db.execute("SELECT value FROM settings WHERE key = ?", ('store_mode',)) as cursor:
                row = await cursor.fetchone()
                store_mode = row['value'] if row else StoreMode.MANUAL
            
            async with db.execute("SELECT value FROM settings WHERE key = ?", ('emergency_stop',)) as cursor:
                row = await cursor.fetchone()
                emergency_stop = row['value'] if row else '0'
            
            if emergency_stop == '1' or store_mode == StoreMode.EMERGENCY:
                return False, "⚠️ عذراً، المتجر في وضع الطوارئ حالياً لحماية العمليات. يرجى المحاولة لاحقاً.", None
            
            if store_mode == StoreMode.MAINTENANCE:
                return False, "🛠 عذراً، المتجر في وضع الصيانة حالياً للتحديث. سنعود للعمل قريباً!", None
            
            # 4. التحقق من وجود طلب مفتوح
            async with db.execute("SELECT 1 FROM orders WHERE user_id = ? AND status IN (?, ?, ?, ?)", 
                                 (user_id, OrderStatus.NEW, OrderStatus.PAID, OrderStatus.IN_PROGRESS, "PENDING_PAYMENT")) as cursor:
                has_open = await cursor.fetchone() is not None
                
            if has_open:
                return False, "لديك طلب قيد المعالجة. يرجى انتظار إتمامه أولاً.", None
            
            # 5. التحقق من طريقة الدفع (إذا كانت محددة)
            if payment_method_id:
                async with db.execute("SELECT * FROM payment_methods WHERE id = ?", (payment_method_id,)) as cursor:
                    payment_method = await cursor.fetchone()
                if not payment_method:
                    return False, "طريقة الدفع غير موجودة", None
                
                if not payment_method['is_active']:
                    return False, "طريقة الدفع غير نشطة", None
            
            # 6. حساب السعر (بالسنتات)
            async with db.execute("SELECT value FROM settings WHERE key = ?", ('dollar_rate',)) as cursor:
                row = await cursor.fetchone()
                dollar_rate_cents = int(row['value'] if row else '1250000')
                
            price_usd_cents = product['price_usd']
            price_local_cents = (price_usd_cents * dollar_rate_cents) // 100
            
            # 7. التحقق من الرصيد (إذا كان الدفع من الرصيد)
            if payment_method_id is None:  # الدفع من الرصيد
                if user['balance'] < price_usd_cents:
                    needed = (price_usd_cents - user['balance']) / 100
                    current = user['balance'] / 100
                    return False, f"رصيدك غير كافٍ. تحتاج إلى {needed:.2f}$ إضافية. رصيدك الحالي {current:.2f}$", None
            
            # 8. التحقق من معرف اللاعب (M-05)
            requires_id = product.get('requires_player_id', 1) == 1
            if requires_id and (not player_id or len(player_id.strip()) == 0 or player_id == "N/A"):
                return False, "يرجى إدخال معرف اللاعب", None
            
            # إعداد بيانات الطلب
            order_data = {
                'user_id': user_id,
                'product_id': product_id,
                'product': dict(product),
                'player_id': player_id.strip(),
                'price_usd': price_usd_cents,
                'price_local': price_local_cents,
                'exchange_rate': dollar_rate_cents,
                'payment_method_id': payment_method_id,
                'execution_type': product['type']
            }
            
            return True, "الطلب صالح", order_data
            
        except Exception as e:
            logger.error(f"Error validating order: {e}", exc_info=True)
            return False, f"خطأ في التحقق من الطلب: {str(e)}", None
    
    @staticmethod
    async def create_order(
        user_id: int,
        product_id: int,
        player_id: str,
        payment_method_id: Optional[int] = None,
        coupon_code: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        إنشاء طلب جديد (NR-01: استخدام transaction context manager)
        """
        try:
            async with db_manager.transaction() as db:
                # 1. التحقق من صلاحية الطلب
                is_valid, message, order_data = await OrderService.validate_order(
                    user_id, product_id, player_id, payment_method_id, db_conn=db
                )
                
                if not is_valid:
                    return False, message, None
                
                # 2. تطبيق الكوبون
                discount_amount_cents = 0
                final_price_usd_cents = order_data['price_usd']
                
                if coupon_code:
                    # Fixed C-01: Removed double call to validate_coupon
                    # M-06: إضافة try/except مستقل حول كتلة الكوبون
                    try:
                        is_valid_coupon, coupon_msg, discount_cents = await db_manager.validate_coupon(
                            coupon_code, user_id, final_price_usd_cents, db_conn=db
                        )
                        
                        if is_valid_coupon:
                            discount_amount_cents = discount_cents
                            final_price_usd_cents = max(0, final_price_usd_cents - discount_cents)
                            min_price_allowed = 50 
                            if final_price_usd_cents < min_price_allowed and order_data['price_usd'] >= min_price_allowed:
                                final_price_usd_cents = min_price_allowed
                        else:
                            # إذا كان الكوبون غير صالح، نوقف العملية ونخبر المستخدم (تحسين M-06)
                            return False, f"الكوبون غير صالح: {coupon_msg}", None
                    except Exception as coupon_err:
                        logger.error(f"Coupon validation error: {coupon_err}")
                        return False, "حدث خطأ أثناء التحقق من الكوبون.", None
                
                # 3. تحديد حالة الطلب الأولية
                initial_status = OrderStatus.PAID if payment_method_id is None else OrderStatus.PENDING_PAYMENT
                
                # 4. إنشاء الطلب
                final_price_local_cents = (final_price_usd_cents * order_data['exchange_rate']) // 100
                metadata_json = json.dumps(metadata) if metadata else None
                
                cursor = await db.execute("""
                    INSERT INTO orders (
                        user_id, product_id, player_id, 
                        price_usd, price_local, exchange_rate,
                        status, payment_method_id, execution_type, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, product_id, order_data['player_id'],
                    final_price_usd_cents, final_price_local_cents, order_data['exchange_rate'],
                    initial_status, payment_method_id, order_data['execution_type'], metadata_json
                ))
                
                order_id = cursor.lastrowid
                
                # خصم الرصيد
                if payment_method_id is None:
                    success, result = await db_manager.update_user_balance(
                        user_id=user_id, amount=-final_price_usd_cents, log_type="PURCHASE",
                        reason=f"شراء منتج: {order_data['product']['name']}", order_id=order_id,
                        commit=False, db_conn=db
                    )
                    if not success: raise Exception(f"فشل خصم الرصيد: {result}")
                
                # تسجيل الكوبون
                if coupon_code and discount_amount_cents > 0:
                    await db_manager.use_coupon(coupon_code, user_id, order_id, discount_amount_cents, commit=False, db_conn=db)
                
                # تسجيل في trust_logs
                await db.execute("""
                    INSERT INTO trust_logs (order_id, user_id, action_text, execution_type)
                    VALUES (?, ?, ?, ?)
                """, (order_id, user_id, f"إنشاء طلب جديد #{order_id}", order_data['execution_type']))
                
                return True, "تم إنشاء الطلب بنجاح", order_id
                
        except Exception as e:
            logger.error(f"Error in create_order: {e}", exc_info=True)
            return False, f"خطأ في إنشاء الطلب: {str(e)}", None
    
    @staticmethod
    async def finalize_order(
        order_id: int,
        status: str,
        admin_id: Optional[int] = None,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        إنهاء الطلب (NR-01: استخدام transaction context manager)
        """
        if admin_id is None:
            return False, "خطأ: يجب تحديد معرف المسؤول (admin_id) لإنهاء الطلب."

        try:
            async with db_manager.transaction() as db:
                # جلب الطلب داخل المعاملة
                async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
                    order = await cursor.fetchone()
                if not order: return False, "الطلب غير موجود"
                
                if status not in [OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELED]:
                    return False, "حالة غير صالحة"
                
                if order['status'] in [OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELED]:
                    return False, f"الطلب منتهي مسبقاً بحالة: {order['status']}"

                # 1. تحديث حالة الطلب (NR-05: COALESCE handled in manager)
                await db_manager.update_order_status(
                    order_id, status, admin_notes=admin_notes, operator_id=admin_id, commit=False, db_conn=db
                )
                
                # 2. إرجاع الرصيد عند الفشل/الإلغاء
                if status in [OrderStatus.FAILED, OrderStatus.CANCELED]:
                    if order['payment_method_id'] is None:
                        # Fixed C-02: Refund full price including coupon discount if applicable
                        # We fetch the original product price to ensure full refund
                        async with db.execute("SELECT price_usd FROM products WHERE id = ?", (order['product_id'],)) as cursor:
                            product = await cursor.fetchone()
                            original_price = product['price_usd'] if product else order['price_usd']
                        
                        success, result = await db_manager.update_user_balance(
                            user_id=order['user_id'], amount=original_price, log_type="REFUND",
                            reason=f"إرجاع رصيد للطلب #{order_id}: {admin_notes or 'فشل الطلب'}",
                            order_id=order_id, admin_id=admin_id, commit=False, db_conn=db
                        )
                        if not success: raise Exception(f"فشل إرجاع الرصيد: {result}")
                
                # 3. تسجيل التدقيق
                await db_manager.log_admin_action(
                    admin_id=admin_id, action=f"FINALIZE_ORDER_{status}", target_type="ORDER",
                    target_id=order_id, details=f"Status changed to {status}. Notes: {admin_notes}",
                    commit=False, db_conn=db
                )
                
                return True, "تم إنهاء الطلب بنجاح"
                
        except Exception as e:
            logger.error(f"Error in finalize_order: {e}", exc_info=True)
            return False, f"خطأ في إنهاء الطلب: {str(e)}"

    @staticmethod
    async def approve_payment(order_id: int, admin_id: int) -> Tuple[bool, str]:
        """
        NR-04: تأكيد الدفع بشكل ذري مع فحص الحالة.
        """
        try:
            async with db_manager.transaction() as db:
                async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
                    order = await cursor.fetchone()
                if not order: return False, "الطلب غير موجود"
                
                if order['status'] != OrderStatus.PENDING_PAYMENT:
                    return False, f"لا يمكن تأكيد الدفع لطلب بحالة: {order['status']}"
                
                # تحديث الحالة
                await db_manager.update_order_status(
                    order_id, OrderStatus.IN_PROGRESS, operator_id=admin_id, commit=False, db_conn=db
                )
                
                # تسجيل التدقيق
                await db_manager.log_admin_action(
                    admin_id=admin_id, action="APPROVE_PAYMENT", target_type="ORDER",
                    target_id=order_id, details=f"Approved payment for order #{order_id}",
                    commit=False, db_conn=db
                )
                
                return True, "تم تأكيد الدفع بنجاح"
        except Exception as e:
            logger.error(f"Error in approve_payment: {e}")
            return False, f"خطأ: {str(e)}"
