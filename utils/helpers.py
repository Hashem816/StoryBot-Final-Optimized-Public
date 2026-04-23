"""
Helpers Utility - أدوات مساعدة (v2.3)
التحسينات:
- إضافة نظام التحقق من المدخلات (Input Validation)
- دوال مساعدة لتنسيق المبالغ المالية
"""

import re
from typing import Optional

def validate_player_id(player_id: str) -> bool:
    """
    التحقق من صحة معرف اللاعب (S-02)
    يمنع النصوص الفارغة، الرموز الغريبة، أو النصوص الطويلة جداً.
    """
    if not player_id:
        return False
    
    player_id = player_id.strip()
    if not player_id or player_id.upper() == "N/A":
        return False
    
    # يسمح بالأرقام، الحروف، والشرطات، بطول بين 3 و 50 حرفاً
    pattern = r'^[a-zA-Z0-9\-_:]{3,50}$'
    return bool(re.match(pattern, player_id))

def format_currency(amount_cents: int, currency: str = "$") -> str:
    """
    Fix: Centralized currency formatting with thousands separator (F-03).
    """
    return f"{amount_cents / 100:,.2f}{currency}"

def clean_html(text: str) -> str:
    """تنظيف النص من وسوم HTML لمنع التلاعب بالواجهة"""
    if not text:
        return ""
    return text.replace("<", "&lt;").replace(">", "&gt;")
