"""
Comprehensive Lifecycle Test - v2.3 REBORN (Cents Edition)
This script tests the entire flow of the bot using the new integer-cents system.
"""

import asyncio
import os
import logging
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.manager import db_manager
from services.order_service import OrderService as order_service
from config.settings import OrderStatus, CouponType

# Configure logging
logging.basicConfig(level=logging.INFO)

async def run_test():
    print("🚀 Starting Comprehensive Lifecycle Test (Cents Edition)...")
    
    try:
        # 1. Initialize DB
        await db_manager.init_db()
        print("✅ Database initialized.")
        
        # 2. Create Test User
        test_user_id = 99999
        await db_manager.create_user(
            telegram_id=test_user_id,
            username="test_user",
            first_name="Test",
            last_name="User"
        )
        print(f"✅ Test user created: {test_user_id}")
        
        # 3. Create Test Category and Product
        async with db_manager.transaction() as db:
            await db.execute("INSERT OR IGNORE INTO categories (id, name) VALUES (1, 'Test Category')")
            await db.execute("""
                INSERT OR IGNORE INTO products (id, category_id, name, description, price_usd, type)
                VALUES (1, 1, 'Test Product', 'Description', 1000, 'MANUAL')
            """) # 1000 cents = 10.00$
        print("✅ Test category and product created (Price: 10.00$)")
        
        # 4. Test Deposit (Update Balance)
        print("⏳ Testing Deposit...")
        # Deposit 5000 cents = 50.00$
        success, new_balance = await db_manager.update_user_balance(
            user_id=test_user_id,
            amount=5000,
            log_type="DEPOSIT",
            reason="Test Deposit"
        )
        
        if success and new_balance == 5000:
            print(f"✅ Deposit successful. New balance: {new_balance/100:.2f}$")
        else:
            print(f"❌ Deposit failed. Result: {new_balance}")
            return
            
        # 5. Test Purchase (Create Order)
        print("⏳ Testing Purchase...")
        success, msg, order_id = await order_service.create_order(
            user_id=test_user_id,
            product_id=1,
            player_id="PLAYER123",
            payment_method_id=None # Use balance
        )
        
        if success:
            user = await db_manager.get_user(test_user_id)
            print(f"✅ Purchase successful. Order ID: #{order_id}. New balance: {user['balance']/100:.2f}$")
            if user['balance'] != 4000: # 5000 - 1000 = 4000
                print(f"❌ Balance mismatch! Expected 4000, got {user['balance']}")
                return
        else:
            print(f"❌ Purchase failed: {msg}")
            return
            
        # 6. Test Order Finalization (Success)
        print("⏳ Testing Order Finalization (Success)...")
        admin_id = 12345
        await db_manager.create_user(telegram_id=admin_id, username="admin", role="SUPER_ADMIN")
        
        success, msg = await order_service.finalize_order(
            order_id=order_id,
            status=OrderStatus.COMPLETED,
            admin_id=admin_id,
            admin_notes="Test completion"
        )
        if success:
            order = await db_manager.get_order(order_id)
            print(f"✅ Order #{order_id} completed successfully. Status: {order['status']}")
        else:
            print(f"❌ Order completion failed: {msg}")
            return
            
        # 7. Test Refund Lifecycle (Purchase -> Failure -> Refund)
        print("\n🔄 Testing Refund Lifecycle...")
        success, msg, order_id2 = await order_service.create_order(
            user_id=test_user_id,
            product_id=1,
            player_id="PLAYER456",
            payment_method_id=None
        )
        
        user_before = await db_manager.get_user(test_user_id)
        print(f"✅ Second order created: #{order_id2}. Balance: {user_before['balance']/100:.2f}$")
        
        success, msg = await order_service.finalize_order(
            order_id=order_id2,
            status=OrderStatus.FAILED,
            admin_id=admin_id,
            admin_notes="Test failure for refund"
        )
        
        if success:
            user_after = await db_manager.get_user(test_user_id)
            print(f"✅ Order #{order_id2} failed. Balance after refund: {user_after['balance']/100:.2f}$")
            if user_after['balance'] == user_before['balance'] + 1000:
                print("✅ Refund verified successfully!")
            else:
                print(f"❌ Refund failed! Expected {user_before['balance'] + 1000}, got {user_after['balance']}")
                return
        else:
            print(f"❌ Order failure/refund process failed: {msg}")
            return
            
        # 8. Test Coupon System
        print("\n🎟️ Testing Coupon System...")
        coupon_code = "TEST50"
        async with db_manager.transaction() as db:
            await db.execute("""
                INSERT OR IGNORE INTO coupons (code, type, value, max_uses, min_amount, is_active)
                VALUES (?, ?, 50, 10, 500, 1)
            """, (coupon_code, CouponType.PERCENT)) # 50% discount, min 5.00$
        
        is_valid, msg, discount = await db_manager.validate_coupon(coupon_code, test_user_id, 1000)
        if is_valid and discount == 500: # 50% of 1000 = 500
            print(f"✅ Coupon validation successful. Discount: {discount/100:.2f}$")
        else:
            print(f"❌ Coupon validation failed: {msg}, Discount: {discount}")
            return
            
        success, msg, order_id3 = await order_service.create_order(
            user_id=test_user_id,
            product_id=1,
            player_id="PLAYER_COUPON",
            payment_method_id=None,
            coupon_code=coupon_code
        )
        
        if success:
            order = await db_manager.get_order(order_id3)
            user = await db_manager.get_user(test_user_id)
            print(f"✅ Order with coupon created: #{order_id3}. Price USD: {order['price_usd']/100:.2f}$. New balance: {user['balance']/100:.2f}$")
            if order['price_usd'] == 500:
                print("✅ Coupon discount applied correctly to order price!")
            else:
                print(f"❌ Coupon discount mismatch! Expected 500, got {order['price_usd']}")
        else:
            print(f"❌ Order with coupon failed: {msg}")
            return
            
        print("\n✨ ALL TESTS PASSED 100%! ✨")
    
    except Exception as e:
        print(f"\n❌ Test crashed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close all connections in the pool
        await db_manager.close()
        print("🔌 Database connections closed.")

if __name__ == "__main__":
    if os.path.exists("test_story.db"):
        os.remove("test_story.db")
    os.environ["DB_PATH"] = "test_story.db"
    asyncio.run(run_test())
