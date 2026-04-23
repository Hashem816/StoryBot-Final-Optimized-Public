import aiohttp
import asyncio
from decimal import Decimal, ROUND_HALF_UP
from config.settings import ITEM4GAMER_API_KEY, ITEM4GAMER_BASE_URL
from database.manager import db_manager
import logging

logger = logging.getLogger(__name__)

class Item4GamerClient:
    _session: aiohttp.ClientSession = None

    def __init__(self):
        self.base_url = ITEM4GAMER_BASE_URL

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """
        Fix: Singleton ClientSession for resource efficiency (L-03).
        """
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()

    async def is_enabled(self) -> bool:
        enabled = await db_manager.get_setting("item4gamer_enabled", "0")
        return enabled == "1"

    async def create_order(self, variation_id: str, player_id: str, user_id: int = None):
        if not await self.is_enabled():
            return {"success": False, "message": "API is currently disabled"}
        
        api_key = await db_manager.get_setting("item4gamer_api_key", ITEM4GAMER_API_KEY)
        if not api_key:
            return {"success": False, "message": "API Key not configured"}
            
        url = f"{self.base_url}/order/add-order"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        
        if user_id:
            user = await db_manager.get_user(user_id)
            if user:
                first_name = user.get('first_name') or "Store"
                last_name = user.get('last_name') or "User"
                customer_email = f"user_{user_id}@telegram.bot"
            else:
                first_name, last_name, customer_email = "Store", "User", "unknown@telegram.bot"
        else:
            first_name, last_name, customer_email = "Store", "User", "system@telegram.bot"
        
        payload = {
            "variation_id": str(variation_id),
            "quantity": 1,
            "customer": {
                "first_name": first_name,
                "last_name": last_name,
                "email": customer_email
            },
            "data": {
                "save_id": str(player_id)
            }
        }
        
        try:
            session = await self.get_session()
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                if response.status == 200 and data.get("status") == 200:
                    return {"success": True, "order_id": data.get("order_id")}
                return {"success": False, "message": data.get("message", "Unknown API Error")}
        except Exception as e:
            logger.error(f"API create_order error: {e}")
            return {"success": False, "message": str(e)}

    async def get_balance(self) -> int:
        """
        Fix: Precision Financial Operations (Cents-based balance) (L-01/L-04).
        Returns balance in cents (int).
        """
        api_key = await db_manager.get_setting("item4gamer_api_key", ITEM4GAMER_API_KEY)
        if not api_key: return 0
        
        url = f"{self.base_url}/order/get-balance"
        headers = {"api-key": api_key}
        try:
            session = await self.get_session()
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                if data.get("status") == 200:
                    raw_balance = data.get("balance", 0)
                    # Convert float/string balance to integer cents using Decimal
                    balance_cents = int((Decimal(str(raw_balance)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    return balance_cents
                return 0
        except Exception as e:
            logger.error(f"API get_balance error: {e}")
            return 0

api_client = Item4GamerClient()
