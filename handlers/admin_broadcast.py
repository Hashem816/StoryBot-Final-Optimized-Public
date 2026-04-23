"""
نظام البث الجماعي - v2.3
التحسينات:
- دعم البادئات الجديدة (adm_bcst)
- دعم الترجمة الكاملة
"""

import asyncio
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.translations import get_text, get_user_language

logger = logging.getLogger(__name__)
router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirming = State()

@router.callback_query(F.data == "adm_bcst")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext, user: dict, **kwargs):
    lang = get_user_language(user)
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.message.edit_text(
        get_text("broadcast_start", lang),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_main")]])
    )

@router.message(BroadcastStates.waiting_for_message)
async def confirm_broadcast(message: types.Message, state: FSMContext, user: dict):
    lang = get_user_language(user)
    await state.update_data(broadcast_msg_id=message.message_id, from_chat_id=message.chat.id, message_text=message.text or "[media]")
    await state.set_state(BroadcastStates.confirming)
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=get_text("btn_confirm", lang), callback_data="adm_bcst_confirm")],
        [types.InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="adm_main")]
    ])
    
    await message.answer(get_text("broadcast_confirm", lang), reply_markup=builder)

@router.callback_query(F.data == "adm_bcst_confirm", BroadcastStates.confirming)
async def execute_broadcast(callback: types.CallbackQuery, state: FSMContext, bot: Bot, user: dict):
    lang = get_user_language(user)
    data = await state.get_data()
    msg_id = data.get('broadcast_msg_id')
    from_chat = data.get('from_chat_id')
    message_text = data.get('message_text', '')
    
    if not msg_id or not from_chat:
        return await callback.answer("❌ حدث خطأ")

    users = await db_manager.get_active_users()
    await callback.message.edit_text(get_text("broadcast_started", lang, count=len(users)))
    
    success_count = 0
    fail_count = 0
    batch_size = 20
    
    for i in range(0, len(users), batch_size):
        batch = users[i:i+batch_size]
        for user_id in batch:
            try:
                await bot.copy_message(chat_id=user_id, from_chat_id=from_chat, message_id=msg_id)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                fail_count += 1
                if "flood" in str(e).lower(): await asyncio.sleep(1)
        
        if i + batch_size < len(users):
            try: await callback.message.edit_text(f"⏳ جاري البث... {i+batch_size}/{len(users)}\n✅ نجح: {success_count} | ❌ فشل: {fail_count}")
            except: pass
    
    await db_manager.save_broadcast(admin_id=callback.from_user.id, message_text=message_text[:200], target_count=len(users), success_count=success_count, fail_count=fail_count)
    await db_manager.log_admin_action(admin_id=callback.from_user.id, action="BROADCAST_SENT", details=f"بث جماعي: {success_count}/{len(users)}")
    
    await callback.message.answer(get_text("broadcast_complete", lang, success=success_count, fail=fail_count))
    await state.clear()
