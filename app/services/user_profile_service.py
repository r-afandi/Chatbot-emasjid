import json
import os
import time
from datetime import datetime
from typing import Optional
from app.models.schemas import UserProfile

PROFILE_PATH = "uploads/user_profiles.json"

def _load_all() -> dict:
    """
    Load profil dari file JSON.
    Jika file corrupted, backup dan return {}.
    """
    if not os.path.exists(PROFILE_PATH):
        print(f"⚠️  {PROFILE_PATH} tidak ada")
        return {}
    
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ Loaded profiles from {PROFILE_PATH}")
            return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON corrupted: {e}")
        print(f"   Line {e.lineno}, Column {e.colno}")
        
        # ── Backup file corrupted ──
        timestamp = int(time.time())
        backup_path = f"{PROFILE_PATH}.backup_{timestamp}"
        try:
            import shutil
            shutil.copy(PROFILE_PATH, backup_path)
            print(f"📦 Backup: {backup_path}")
        except Exception as e2:
            print(f"⚠️  Backup failed: {e2}")
        
        # ── Reset file ──
        try:
            os.remove(PROFILE_PATH)
            print(f"🔄 Deleted corrupted file: {PROFILE_PATH}")
        except Exception as e3:
            print(f"⚠️  Delete failed: {e3}")
        
        return {}
    except Exception as e:
        print(f"❌ Error loading profiles: {e}")
        return {}


def _save_all(data: dict):
    """
    Simpan profil ke file JSON dengan error handling.
    """
    try:
        os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(data)} profiles to {PROFILE_PATH}")
    except Exception as e:
        print(f"❌ Error saving profiles: {e}")


def get_user_profile(user_id: str) -> Optional[UserProfile]:
    """Ambil profil user"""
    try:
        data = _load_all()
        user = data.get(str(user_id))
        if not user:
            print(f"⚠️  No profile for user {user_id}")
            return None
        profile = UserProfile(**user)
        print(f"✅ Got profile for {user_id}")
        return profile
    except Exception as e:
        print(f"❌ Error getting profile for {user_id}: {e}")
        return None


def save_user_profile(user_id: str, profile: UserProfile):
    """Simpan profil user"""
    try:
        data = _load_all()
        profile.updated_at = datetime.now()
        data[str(user_id)] = {
            k: str(v) if isinstance(v, datetime) else v
            for k, v in profile.dict().items()
            if v is not None
        }
        _save_all(data)
        print(f"✅ Saved profile for {user_id}")
    except Exception as e:
        print(f"❌ Error saving profile for {user_id}: {e}")