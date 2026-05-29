"""
Файл: license_manager.py — Система лицензионных ключей
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

class LicenseManager:
    """
    Управление лицензиями Jinada.Trade
    
    Три типа ключей:
    - trial: 3 дня бесплатно
    - monthly: 30 дней
    - lifetime: навсегда
    """
    
    def __init__(self):
        self.keys_file = Path("licenses.json")
        self.active_license_file = Path("active_license.json")
        self._load_keys()
    
    def _load_keys(self):
        """Загрузка базы ключей"""
        if self.keys_file.exists():
            self.keys_db = json.loads(self.keys_file.read_text())
        else:
            self.keys_db = {"keys": {}, "used_by": {}}
            self._save_keys()
    
    def _save_keys(self):
        """Сохранение базы ключей"""
        self.keys_file.write_text(json.dumps(self.keys_db, indent=2))
    
    def generate_key(self, plan: str = "monthly", user: str = "") -> str:
        """
        Сгенерировать новый ключ
        
        Args:
            plan: trial / monthly / lifetime
            user: имя пользователя (опционально)
        
        Returns:
            str: лицензионный ключ
        """
        # Генерируем уникальный ключ
        secret = f"JINADA-{uuid.uuid4()}-{plan}-{datetime.now().isoformat()}"
        license_key = "JINADA-" + hashlib.sha256(secret.encode()).hexdigest()[:16].upper()
        
        # Настройки плана
        plans = {
            "trial": {"days": 3, "name": "Пробный (3 дня)"},
            "monthly": {"days": 30, "name": "Месячный"},
            "lifetime": {"days": 99999, "name": "Навсегда"},
        }
        
        plan_info = plans.get(plan, plans["monthly"])
        
        # Сохраняем ключ
        self.keys_db["keys"][license_key] = {
            "plan": plan,
            "name": plan_info["name"],
            "days": plan_info["days"],
            "created": datetime.now().isoformat(),
            "created_for": user,
            "used": False,
            "active": True
        }
        self._save_keys()
        
        return license_key
    
    def generate_batch(self, plan: str = "trial", count: int = 10) -> list:
        """Сгенерировать пачку ключей"""
        keys = []
        for i in range(count):
            key = self.generate_key(plan, f"batch_{i+1}")
            keys.append(key)
        return keys
    
    def activate_key(self, license_key: str, device_id: str = "") -> Dict:
        """
        Активировать ключ на устройстве
        
        Returns:
            dict: статус активации
        """
        if license_key not in self.keys_db["keys"]:
            return {"success": False, "error": "Ключ не найден"}
        
        key_data = self.keys_db["keys"][license_key]
        
        if not key_data["active"]:
            return {"success": False, "error": "Ключ отключён"}
        
        if key_data["used"] and key_data.get("device_id") != device_id:
            return {"success": False, "error": "Ключ уже используется на другом устройстве"}
        
        # Активируем
        expires = datetime.now() + timedelta(days=key_data["days"])
        
        key_data["used"] = True
        key_data["activated_at"] = datetime.now().isoformat()
        key_data["expires_at"] = expires.isoformat()
        key_data["device_id"] = device_id
        
        self.keys_db["used_by"][device_id] = license_key
        self._save_keys()
        
        # Сохраняем локально
        self.save_active_license(license_key, expires)
        
        return {
            "success": True,
            "plan": key_data["plan"],
            "name": key_data["name"],
            "expires": expires.isoformat(),
            "days_left": key_data["days"]
        }
    
    def check_license(self, device_id: str = "") -> Dict:
        """
        Проверить активную лицензию
        
        Returns:
            dict: статус лицензии
        """
        # Проверяем локальный файл
        if self.active_license_file.exists():
            try:
                active = json.loads(self.active_license_file.read_text())
                
                license_key = active.get("key")
                expires = datetime.fromisoformat(active.get("expires", "2000-01-01"))
                
                # Проверяем не истекла ли
                if datetime.now() < expires:
                    # Проверяем в базе
                    if license_key in self.keys_db["keys"]:
                        key_data = self.keys_db["keys"][license_key]
                        if key_data["active"]:
                            days_left = (expires - datetime.now()).days
                            return {
                                "active": True,
                                "key": license_key,
                                "plan": key_data["plan"],
                                "name": key_data["name"],
                                "expires": expires.isoformat(),
                                "days_left": max(0, days_left)
                            }
            except Exception:
                pass
        
        # Проверяем есть ли пробный период
        trial_file = Path("trial_activated")
        if not trial_file.exists():
            # Активируем пробный период
            trial_file.write_text(datetime.now().isoformat())
            expires = datetime.now() + timedelta(days=3)
            
            return {
                "active": True,
                "key": "TRIAL",
                "plan": "trial",
                "name": "Пробный период (3 дня)",
                "expires": expires.isoformat(),
                "days_left": 3
            }
        else:
            # Проверяем пробный период
            try:
                trial_start = datetime.fromisoformat(trial_file.read_text().strip())
                trial_expires = trial_start + timedelta(days=3)
                
                if datetime.now() < trial_expires:
                    days_left = (trial_expires - datetime.now()).days
                    return {
                        "active": True,
                        "key": "TRIAL",
                        "plan": "trial",
                        "name": "Пробный период (3 дня)",
                        "expires": trial_expires.isoformat(),
                        "days_left": max(0, days_left)
                    }
            except Exception:
                pass
        
        return {"active": False, "error": "Лицензия не найдена или истекла"}
    
    def save_active_license(self, license_key: str, expires: datetime):
        """Сохранить активную лицензию локально"""
        data = {
            "key": license_key,
            "expires": expires.isoformat(),
            "activated": datetime.now().isoformat()
        }
        self.active_license_file.write_text(json.dumps(data, indent=2))
    
    def deactivate_key(self, license_key: str) -> bool:
        """Отключить ключ"""
        if license_key in self.keys_db["keys"]:
            self.keys_db["keys"][license_key]["active"] = False
            self._save_keys()
            return True
        return False
    
    def list_keys(self) -> list:
        """Список всех ключей"""
        keys_list = []
        for key, data in self.keys_db["keys"].items():
            keys_list.append({
                "key": key,
                "plan": data["plan"],
                "name": data["name"],
                "created": data["created"],
                "used": data["used"],
                "active": data["active"],
                "created_for": data.get("created_for", "")
            })
        return keys_list
    
    def revoke_device(self, device_id: str) -> bool:
        """Отозвать лицензию с устройства"""
        if device_id in self.keys_db["used_by"]:
            license_key = self.keys_db["used_by"][device_id]
            del self.keys_db["used_by"][device_id]
            
            if license_key in self.keys_db["keys"]:
                self.keys_db["keys"][license_key]["used"] = False
                self.keys_db["keys"][license_key]["device_id"] = ""
            
            self._save_keys()
            
            # Удаляем локальный файл
            if self.active_license_file.exists():
                self.active_license_file.unlink()
            
            return True
        return False


# ============================================================
# КОНСОЛЬНЫЙ ИНТЕРФЕЙС ДЛЯ УПРАВЛЕНИЯ КЛЮЧАМИ
# ============================================================
if __name__ == "__main__":
    lm = LicenseManager()
    
    while True:
        print("\n" + "=" * 50)
        print("  Jinada.Trade — Управление лицензиями")
        print("=" * 50)
        print("\n1. Сгенерировать ключ")
        print("2. Сгенерировать 10 пробных ключей")
        print("3. Показать все ключи")
        print("4. Отключить ключ")
        print("5. Проверить лицензию")
        print("6. Выход")
        
        choice = input("\nВыбери действие: ").strip()
        
        if choice == "1":
            print("\nТип ключа:")
            print("1. Пробный (3 дня)")
            print("2. Месячный (30 дней)")
            print("3. Навсегда")
            plan_choice = input("Выбери тип (1-3): ").strip()
            
            plans = {"1": "trial", "2": "monthly", "3": "lifetime"}
            plan = plans.get(plan_choice, "trial")
            
            user = input("Для кого (имя/ник): ").strip()
            
            key = lm.generate_key(plan, user)
            print(f"\n✅ Ключ создан: {key}")
            print(f"   Тип: {plan}")
            print(f"   Для: {user}")
        
        elif choice == "2":
            keys = lm.generate_batch("trial", 10)
            print("\n✅ 10 пробных ключей создано:\n")
            for i, k in enumerate(keys, 1):
                print(f"   {i}. {k}")
        
        elif choice == "3":
            keys = lm.list_keys()
            print(f"\nВсего ключей: {len(keys)}\n")
            for k in keys:
                status = "🟢" if k['active'] else "🔴"
                used = "✓" if k['used'] else "✗"
                print(f"   {status} {k['key']} | {k['name']} | Для: {k['created_for']} | Исп: {used}")
        
        elif choice == "4":
            key = input("Введи ключ для отключения: ").strip()
            if lm.deactivate_key(key):
                print(f"✅ Ключ {key} отключён")
            else:
                print("❌ Ключ не найден")
        
        elif choice == "5":
            status = lm.check_license()
            if status['active']:
                print(f"\n✅ Лицензия активна")
                print(f"   Тип: {status['name']}")
                print(f"   Дней осталось: {status['days_left']}")
                print(f"   Истекает: {status['expires'][:10]}")
            else:
                print(f"\n❌ {status.get('error', 'Лицензия не активна')}")
        
        elif choice == "6":
            print("\n👋 Пока!")
            break