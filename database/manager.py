"""
Database Manager - Ultimate Production Edition (v2.3 REBORN)
- Optimized for High Concurrency with Transactions
- Precision Financial Operations (Strict Decimal-based Cents)
- Robust Error Handling and Atomic Operations
"""

import aiosqlite
import asyncio
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)

try:
    from .models import *
except ImportError:
    from database.models import *

from config.settings import DB_PATH, OrderStatus, CouponType

class DatabaseManager:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self._pool = asyncio.Queue()
        self._pool_size = pool_size
        self._initialized = False
        self._lock = asyncio.Lock()
        
    async def _create_connection(self):
        conn = await aiosqlite.connect(self.db_path, timeout=60)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def connect(self):
        """
        Fixed H-01: Simple Connection Pooling to avoid Database Locks.
        """
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    for _ in range(self._pool_size):
                        conn = await self._create_connection()
                        self._pool.put_nowait(conn)
                    self._initialized = True
        
        # Get a connection from the pool
        conn = await self._pool.get()
        return conn

    async def release(self, conn):
        """Releases a connection back to the pool."""
        self._pool.put_nowait(conn)

    async def close(self):
        """Closes all connections in the pool."""
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
        self._initialized = False

    @asynccontextmanager
    async def get_db(self):
        """Context manager for simple pool-based connections."""
        conn = await self.connect()
        try:
            yield conn
        finally:
            await self.release(conn)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Provides a dedicated connection for a transaction to solve NR-01.
        Usage: async with db_manager.transaction() as db: ...
        """
        # Transactions always use a fresh connection to ensure isolation
        conn = await self._create_connection()
        try:
            await conn.execute("BEGIN")
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await conn.close()

    async def init_db(self):
        db = await self.connect()
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_USERS_INDEX)
        await db.execute(CREATE_CATEGORIES_TABLE)
        await db.execute(CREATE_PROVIDERS_TABLE)
        await db.execute(CREATE_PRODUCTS_TABLE)
        await db.execute(CREATE_ORDERS_TABLE)
        await db.execute(CREATE_FINANCIAL_LOGS_TABLE)
        await db.execute(CREATE_TRUST_LOGS_TABLE)
        await db.execute(CREATE_SETTINGS_TABLE)
        await db.execute(CREATE_PAYMENT_METHODS_TABLE)
        await db.execute(CREATE_COUPONS_TABLE)
        await db.execute(CREATE_COUPON_USAGE_TABLE)
        await db.execute(CREATE_AUDIT_LOGS_TABLE)
        await db.execute(CREATE_BROADCAST_HISTORY_TABLE)
        await db.execute(CREATE_RATE_LIMITS_TABLE)
        await db.execute(CREATE_ADMIN_SESSIONS_TABLE)
        
        # Fixed H-03: Adding missing indexes for performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_fin_logs_user_type ON financial_logs(user_id, type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_fin_logs_created ON financial_logs(created_at)")
        
        # M-05: التحقق من وجود حقل requires_player_id
        async with db.execute("PRAGMA table_info(products)") as cursor:
            columns = [row['name'] for row in await cursor.fetchall()]
            if 'requires_player_id' not in columns:
                await db.execute("ALTER TABLE products ADD COLUMN requires_player_id INTEGER DEFAULT 1")
        
        for key, val in DEFAULT_SETTINGS:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        
        await db.commit()

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, first_name: str = None, last_name: str = None, role: str = 'USER', language: str = 'ar'):
        db = await self.connect()
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name, role, language) VALUES (?, ?, ?, ?, ?, ?)",
            (telegram_id, username, first_name, last_name, role, language)
        )
        await db.commit()

    async def update_user_language(self, user_id: int, language: str):
        db = await self.connect()
        await db.execute("UPDATE users SET language = ? WHERE telegram_id = ?", (language, user_id))
        await db.commit()

    async def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("""
            SELECT o.*, p.name as product_name 
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            WHERE o.user_id = ? 
            ORDER BY o.created_at DESC LIMIT ?
        """, (user_id, limit)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def get_completed_orders_count(self, user_id: int) -> int:
        db = await self.connect()
        async with db.execute("SELECT COUNT(*) as count FROM orders WHERE user_id = ? AND status = ?", (user_id, OrderStatus.COMPLETED)) as cursor:
            row = await cursor.fetchone()
            return row['count'] if row else 0

    async def get_active_users(self) -> List[int]:
        db = await self.connect()
        async with db.execute("SELECT telegram_id FROM users WHERE is_active = 1") as cursor:
            return [row['telegram_id'] for row in await cursor.fetchall()]

    async def save_broadcast(self, admin_id: int, message_text: str, target_count: int, success_count: int, fail_count: int):
        # Fixed C-04: Corrected SQL columns/values count (5 columns, 5 values)
        db = await self.connect()
        await db.execute("""
            INSERT INTO broadcast_history (admin_id, message_text, target_count, success_count, fail_count)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_id, message_text, target_count, success_count, fail_count))
        await db.commit()

    async def get_audit_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("""
            SELECT l.*, u.username as admin_name 
            FROM audit_logs l 
            LEFT JOIN users u ON l.admin_id = u.telegram_id 
            ORDER BY l.created_at DESC LIMIT ?
        """, (limit,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def add_payment_method(self, name: str, description: str = None, db_conn=None, commit: bool = True):
        db = db_conn or await self.connect()
        await db.execute("INSERT INTO payment_methods (name, description) VALUES (?, ?)", (name, description))
        if commit:
            await db.commit()

    async def soft_delete_payment_method(self, method_id: int, db_conn=None, commit: bool = True):
        db = db_conn or await self.connect()
        await db.execute("UPDATE payment_methods SET deleted_at = CURRENT_TIMESTAMP, is_active = 0 WHERE id = ?", (method_id,))
        if commit:
            await db.commit()

    async def update_user_balance(self, user_id: int, amount: Any, log_type: str, reason: str = None, admin_id: int = None, order_id: int = None, commit: bool = True, db_conn=None) -> tuple[bool, Any]:
        try:
            if not isinstance(amount, Decimal):
                amount_cents = int(Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            else:
                amount_cents = int(amount)

            db = db_conn or await self.connect()
            async with db.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
                if not user: return False, "User not found"
                
                balance_before = user['balance']
                balance_after = balance_before + amount_cents
                if balance_after < 0: return False, "Insufficient balance"
                
                await db.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (balance_after, user_id))
                await db.execute("""
                    INSERT INTO financial_logs (user_id, order_id, type, amount, balance_before, balance_after, admin_id, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, order_id, log_type, amount_cents, balance_before, balance_after, admin_id, reason))
                
                if commit:
                    await db.commit()
                return True, balance_after
        except Exception as e:
            if commit and not db_conn and db:
                await db.rollback()
            logger.error(f"Balance update error: {e}")
            return False, str(e)

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_products(self, category_id: int = None, only_active: bool = True) -> List[Dict[str, Any]]:
        db = await self.connect()
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        if category_id:
            query += " AND category_id = ?"
            params.append(category_id)
        if only_active:
            query += " AND is_active = 1"
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def get_categories(self, only_active: bool = True) -> List[Dict[str, Any]]:
        db = await self.connect()
        query = "SELECT * FROM categories"
        if only_active: query += " WHERE is_active = 1"
        async with db.execute(query) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    # NR-08: Removed old create_order to prevent unsafe usage. Use OrderService instead.

    async def has_open_order(self, user_id: int) -> bool:
        db = await self.connect()
        async with db.execute("SELECT 1 FROM orders WHERE user_id = ? AND status IN (?, ?, ?, ?)", 
                             (user_id, OrderStatus.NEW, OrderStatus.PAID, OrderStatus.IN_PROGRESS, "PENDING_PAYMENT")) as cursor:
            return await cursor.fetchone() is not None

    async def update_order_status(self, order_id: int, status: str, admin_notes: str = None, execution_type: str = None, operator_id: int = None, commit: bool = True, db_conn=None):
        """
        NR-05: Use COALESCE to preserve execution_type if not provided.
        """
        db = db_conn or await self.connect()
        await db.execute("""
            UPDATE orders 
            SET status = ?, admin_notes = ?, execution_type = COALESCE(?, execution_type), operator_id = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (status, admin_notes, execution_type, operator_id, order_id))
        if commit:
            await db.commit()

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("""
            SELECT o.*, p.name as product_name, u.username, u.telegram_id
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.telegram_id
            WHERE o.id = ?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_active_orders(self, limit: int = 20) -> List[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("""
            SELECT o.*, p.name, u.username 
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            JOIN users u ON o.user_id = u.telegram_id 
            WHERE o.status IN (?, ?, ?) 
            ORDER BY o.created_at DESC LIMIT ?
        """, (OrderStatus.NEW, OrderStatus.PAID, OrderStatus.IN_PROGRESS, limit)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def get_setting(self, key: str, default: Any = None) -> Any:
        db = await self.connect()
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row['value'] if row else default

    async def set_setting(self, key: str, value: str):
        db = await self.connect()
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

    async def get_payment_methods(self, only_active: bool = True) -> List[Dict[str, Any]]:
        db = await self.connect()
        query = "SELECT * FROM payment_methods WHERE deleted_at IS NULL"
        if only_active: query += " AND is_active = 1"
        async with db.execute(query) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def get_payment_method(self, method_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM payment_methods WHERE id = ?", (method_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def log_admin_action(self, admin_id: int, action: str, target_type: str = None, target_id: int = None, details: str = None, commit: bool = True, db_conn=None):
        db = db_conn or await self.connect()
        await db.execute("INSERT INTO audit_logs (admin_id, action, target_type, target_id, details) VALUES (?, ?, ?, ?, ?)", 
                         (admin_id, action, target_type, target_id, details))
        if commit:
            await db.commit()

    # --- Coupon Management ---

    async def create_coupon(self, code: str, type: str, value: int, max_uses: int, min_amount: int, expires_at: str = None, created_by: int = None):
        db = await self.connect()
        await db.execute("""
            INSERT INTO coupons (code, type, value, max_uses, min_amount, expires_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code.upper(), type, value, max_uses, min_amount, expires_at, created_by))
        await db.commit()

    async def get_coupon(self, code: str) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM coupons WHERE code = ? AND is_active = 1", (code.upper(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_coupons(self) -> List[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM coupons ORDER BY created_at DESC") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def delete_coupon(self, coupon_id: int):
        db = await self.connect()
        await db.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        await db.commit()

    async def validate_coupon(self, code: str, user_id: int, order_amount: int, db_conn=None) -> tuple[bool, str, int]:
        """
        NR-07: Removed fallback "PERCENTAGE".
        """
        db = db_conn or await self.connect()
        async with db.execute("SELECT * FROM coupons WHERE code = ? AND is_active = 1", (code.upper(),)) as cursor:
            coupon = await cursor.fetchone()
            
        if not coupon:
            return False, "الكوبون غير موجود", 0
        if not coupon['is_active']:
            return False, "الكوبون معطل حالياً", 0
        
        # Fixed C-03: Check coupon expiration date
        if coupon['expires_at']:
            try:
                expiry = datetime.fromisoformat(coupon['expires_at'])
                if datetime.now() > expiry:
                    return False, "انتهت صلاحية الكوبون (تاريخ منتهي)", 0
            except Exception as e:
                logger.error(f"Error parsing coupon expiry: {e}")

        if coupon['used_count'] >= coupon['max_uses']:
            return False, "انتهت صلاحية الكوبون (وصل للحد الأقصى)", 0
        if order_amount < coupon['min_amount']:
            return False, f"الحد الأدنى لاستخدام الكوبون هو {coupon['min_amount']/100:.2f}$", 0
        
        # التحقق من الاستخدام المسبق
        async with db.execute("SELECT 1 FROM coupon_usage WHERE coupon_id = ? AND user_id = ?", (coupon['id'], user_id)) as cursor:
            if await cursor.fetchone():
                return False, "لقد استخدمت هذا الكوبون مسبقاً", 0

        # حساب الخصم
        discount_cents = 0
        if coupon['type'] == CouponType.FIXED:
            discount_cents = coupon['value']
        elif coupon['type'] == CouponType.PERCENT:
            # coupon['value'] is percentage (e.g., 50 for 50%)
            discount_cents = (order_amount * coupon['value']) // 100
            
        return True, "كوبون صالح", discount_cents

    async def use_coupon(self, code: str, user_id: int, order_id: int, discount_amount: int, commit: bool = True, db_conn=None):
        db = db_conn or await self.connect()
        async with db.execute("SELECT id FROM coupons WHERE code = ?", (code.upper(),)) as cursor:
            coupon = await cursor.fetchone()
            if not coupon: return False
            
            coupon_id = coupon['id']
            await db.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = ?", (coupon_id,))
            await db.execute("INSERT INTO coupon_usage (coupon_id, user_id, order_id, discount_amount) VALUES (?, ?, ?, ?)",
                             (coupon_id, user_id, order_id, discount_amount))
            if commit:
                await db.commit()
            return True

    async def close(self):
        """Closes the shared database connection."""
        if self._db:
            await self._db.close()
            self._db = None

db_manager = DatabaseManager(DB_PATH)
