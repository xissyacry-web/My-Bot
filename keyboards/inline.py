"""Алиасы для обратной совместимости — всё переадресует в kb.py"""
from keyboards.kb import (
    admin_main, admin_main_kb,
    admin_back, admin_back_kb,
    admin_promos, admin_promos_kb,
    admin_users, admin_users_kb,
    broadcast_timing, broadcast_timing_kb,
    unban_action, unban_action_kb,
    banned_kb, to_main, replace_action, ibtn,
)

__all__ = [
    "admin_main", "admin_main_kb", "admin_back", "admin_back_kb",
    "admin_promos", "admin_promos_kb", "admin_users", "admin_users_kb",
    "broadcast_timing", "broadcast_timing_kb", "unban_action", "unban_action_kb",
    "banned_kb", "to_main", "replace_action", "ibtn",
]
