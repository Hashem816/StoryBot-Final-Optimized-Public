"""
Analytics Service - نظام الإحصائيات المحسّن (v2.3)
التحسينات:
- دعم نظام السنتات (INTEGER) في جميع الحسابات المالية
- إحصائيات شاملة للطلبات والإيرادات والمستخدمين
- نظام التسوية المالية (Financial Reconciliation) لمنع التسريب المالي
- Fixed H-02: Optimized queries to prevent N+1 and reduce DB load
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from database.manager import db_manager
from config.settings import OrderStatus
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    """خدمة الإحصائيات والتحليلات"""
    
    @staticmethod
    async def get_dashboard_stats() -> Dict[str, Any]:
        """
        إحصائيات لوحة التحكم الرئيسية (دعم نظام السنتات)
        Fixed H-02: Combined multiple queries into fewer, more efficient ones.
        """
        try:
            async with db_manager.get_db() as db:
                stats = {}
                
                # 1. إحصائيات المستخدمين المجمعة
                async with db.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as blocked,
                        SUM(CASE WHEN date(created_at) = date('now') THEN 1 ELSE 0 END) as today,
                        SUM(CASE WHEN created_at >= date('now', '-7 days') THEN 1 ELSE 0 END) as week,
                        COALESCE(SUM(balance), 0) as total_balance
                    FROM users
                """) as cursor:
                    row = await cursor.fetchone()
                    stats['total_users'] = row['total']
                    stats['blocked_users'] = row['blocked'] or 0
                    stats['new_users_today'] = row['today'] or 0
                    stats['new_users_week'] = row['week'] or 0
                    stats['total_balance_cents'] = row['total_balance']
                    stats['total_balance'] = stats['total_balance_cents'] / 100
                
                # 2. إحصائيات الطلبات المجمعة
                async with db.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as in_progress,
                        SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN date(created_at) = date('now') THEN 1 ELSE 0 END) as today,
                        SUM(CASE WHEN created_at >= date('now', '-7 days') THEN 1 ELSE 0 END) as week,
                        SUM(CASE WHEN execution_type = 'MANUAL' THEN 1 ELSE 0 END) as manual,
                        SUM(CASE WHEN execution_type = 'AUTOMATIC' THEN 1 ELSE 0 END) as auto
                    FROM orders
                """, (OrderStatus.COMPLETED, OrderStatus.IN_PROGRESS, OrderStatus.FAILED)) as cursor:
                    row = await cursor.fetchone()
                    stats['total_orders'] = row['total']
                    stats['completed_orders'] = row['completed'] or 0
                    stats['pending_orders'] = row['in_progress'] or 0
                    stats['failed_orders'] = row['failed'] or 0
                    stats['orders_today'] = row['today'] or 0
                    stats['orders_week'] = row['week'] or 0
                    stats['manual_orders'] = row['manual'] or 0
                    stats['auto_orders'] = row['auto'] or 0
                
                # 3. إحصائيات الإيرادات المجمعة
                async with db.execute("""
                    SELECT 
                        SUM(CASE WHEN status = ? THEN price_usd ELSE 0 END) as total_rev,
                        SUM(CASE WHEN status = ? AND date(created_at) = date('now') THEN price_usd ELSE 0 END) as today_rev,
                        SUM(CASE WHEN status = ? AND created_at >= date('now', '-7 days') THEN price_usd ELSE 0 END) as week_rev,
                        SUM(CASE WHEN status = ? AND created_at >= date('now', '-30 days') THEN price_usd ELSE 0 END) as month_rev,
                        AVG(CASE WHEN status = ? THEN price_usd ELSE NULL END) as avg_val
                    FROM orders
                """, (OrderStatus.COMPLETED, OrderStatus.COMPLETED, OrderStatus.COMPLETED, OrderStatus.COMPLETED, OrderStatus.COMPLETED)) as cursor:
                    row = await cursor.fetchone()
                    stats['total_revenue_cents'] = row['total_rev'] or 0
                    stats['total_revenue'] = stats['total_revenue_cents'] / 100
                    stats['revenue_today_cents'] = row['today_rev'] or 0
                    stats['revenue_today'] = stats['revenue_today_cents'] / 100
                    stats['revenue_week'] = (row['week_rev'] or 0) / 100
                    stats['revenue_month'] = (row['month_rev'] or 0) / 100
                    stats['avg_order_value'] = (row['avg_val'] or 0) / 100
                
                # 4. إحصائيات الشحن
                async with db.execute("""
                    SELECT 
                        COUNT(*) as count,
                        SUM(amount) as total,
                        SUM(CASE WHEN date(created_at) = date('now') THEN amount ELSE 0 END) as today
                    FROM financial_logs 
                    WHERE type = 'DEPOSIT'
                """) as cursor:
                    row = await cursor.fetchone()
                    stats['total_deposits'] = row['count'] or 0
                    stats['total_deposit_amount'] = (row['total'] or 0) / 100
                    stats['deposits_today'] = (row['today'] or 0) / 100

                # 5. نظام التسوية المالية
                async with db.execute("""
                    SELECT 
                        (SELECT COALESCE(SUM(amount), 0) FROM financial_logs) as total_logs,
                        (SELECT COALESCE(SUM(balance), 0) FROM users) as current_total_balance
                """) as cursor:
                    recon = await cursor.fetchone()
                    stats['reconciliation_diff'] = (recon['total_logs'] - recon['current_total_balance']) / 100
                    stats['is_financial_healthy'] = abs(stats['reconciliation_diff']) < 0.01

                # معدلات النجاح
                if stats['total_orders'] > 0:
                    stats['success_rate'] = (stats['completed_orders'] / stats['total_orders']) * 100
                else:
                    stats['success_rate'] = 0
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}", exc_info=True)
            return {}
    
    @staticmethod
    async def get_top_products(limit: int = 5) -> List[Dict[str, Any]]:
        """أكثر المنتجات مبيعاً"""
        try:
            async with db_manager.get_db() as db:
                async with db.execute("""
                    SELECT p.name, COUNT(o.id) as order_count, SUM(o.price_usd) as total_revenue
                    FROM orders o
                    JOIN products p ON o.product_id = p.id
                    WHERE o.status = ?
                    GROUP BY o.product_id
                    ORDER BY order_count DESC
                    LIMIT ?
                """, (OrderStatus.COMPLETED, limit)) as cursor:
                    return [
                        {
                            'name': row['name'],
                            'order_count': row['order_count'],
                            'total_revenue': row['total_revenue'] / 100
                        } for row in await cursor.fetchall()
                    ]
        except Exception as e:
            logger.error(f"Error getting top products: {e}")
            return []

    @staticmethod
    async def get_user_activity() -> Dict[str, Any]:
        """نشاط المستخدمين"""
        try:
            async with db_manager.get_db() as db:
                activity = {}
                async with db.execute("SELECT COUNT(DISTINCT user_id) FROM orders WHERE created_at >= date('now', '-30 days')") as cursor:
                    activity['active_users_month'] = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT (CAST(COUNT(id) AS FLOAT) / (SELECT 1 + COUNT(id) FROM users)) FROM orders") as cursor:
                    activity['avg_orders_per_user'] = round((await cursor.fetchone())[0] or 0, 2)
                    
                return activity
        except Exception as e:
            logger.error(f"Error getting user activity: {e}")
            return {}

    @staticmethod
    async def get_orders_by_status() -> Dict[str, int]:
        """إحصائيات الطلبات حسب الحالة"""
        try:
            async with db_manager.get_db() as db:
                async with db.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM orders 
                    GROUP BY status
                """) as cursor:
                    results = await cursor.fetchall()
                    return {row['status']: row['count'] for row in results}
        except Exception as e:
            logger.error(f"Error getting orders by status: {e}")
            return {}

    @staticmethod
    async def get_financial_audit_report() -> Dict[str, Any]:
        """
        تقرير تدقيق مالي شامل لكشف أي "تسريب" أو أخطاء برمجية في الحسابات
        """
        try:
            async with db_manager.get_db() as db:
                report = {}
                
                async with db.execute("""
                    SELECT 
                        SUM(CASE WHEN type = 'DEPOSIT' THEN amount ELSE 0 END) as deposits,
                        SUM(CASE WHEN type = 'PURCHASE' THEN amount ELSE 0 END) as purchases,
                        SUM(CASE WHEN type = 'REFUND' THEN amount ELSE 0 END) as refunds,
                        SUM(amount) as total_logs
                    FROM financial_logs
                """) as cursor:
                    row = await cursor.fetchone()
                    report['total_deposits'] = (row['deposits'] or 0) / 100
                    report['total_purchases'] = abs(row['purchases'] or 0) / 100
                    report['total_refunds'] = (row['refunds'] or 0) / 100
                    report['expected_balance_from_logs'] = (row['total_logs'] or 0) / 100
                    
                async with db.execute("SELECT COALESCE(SUM(balance), 0) FROM users") as cursor:
                    report['actual_users_balance'] = (await cursor.fetchone())[0] / 100
                    
                report['leakage'] = report['expected_balance_from_logs'] - report['actual_users_balance']
                report['status'] = "HEALTHY" if abs(report['leakage']) < 0.01 else "WARNING"
                
                return report
        except Exception as e:
            logger.error(f"Error in financial audit: {e}")
            return {'status': 'ERROR', 'message': str(e)}

# إنشاء instance واحد
analytics_service = AnalyticsService()
