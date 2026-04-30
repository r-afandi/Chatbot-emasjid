"""
session_state_service.py
Menyimpan state sementara per user_id:
  - is_first_message : apakah ini pesan pertama user?
  - asked_fields     : field profil apa yang terakhir ditanyakan AI?

State ini in-memory (hilang saat server restart).
Untuk produksi, bisa diganti Redis / DB.
"""

from typing import Optional, Set

# { user_id: {"is_first": bool, "asked": set[str]} }
_session: dict = {}


def is_first_message(user_id: str) -> bool:
    return _session.get(user_id, {}).get("is_first", True)


def mark_not_first(user_id: str) -> None:
    if user_id not in _session:
        _session[user_id] = {}
    _session[user_id]["is_first"] = False


def get_asked_fields(user_id: str) -> Set[str]:
    return _session.get(user_id, {}).get("asked", set())


def set_asked_fields(user_id: str, fields: Set[str]) -> None:
    if user_id not in _session:
        _session[user_id] = {}
    _session[user_id]["asked"] = fields


def clear_asked_fields(user_id: str) -> None:
    if user_id in _session:
        _session[user_id]["asked"] = set()