"""
Jinada.Trade — Админ-панель управления клиентами
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from server import load_clients, save_clients, create_client

CLIENTS_FILE = Path("clients.json")

def list_clients():
    clients = load_clients()
    print("\n" + "=" * 60)
    print("  Jinada.Trade — Список клиентов")
    print("=" * 60)
    
    for username, data in clients["clients"].items():
        expires = datetime.fromisoformat(data["expires"])
        days_left = (expires - datetime.now()).days
        status = "🟢" if data["active"] and days_left > 0 else "🔴"
        print(f"\n  {status} {username}")
        print(f"     План: {data['plan_name']}")
        print(f"     Дней: {max(0, days_left)}")
        print(f"     Биржа: {data.get('exchange', 'Не подключена')}")
        print(f"     API: {'✓' if data.get('api_key') else '✗'}")

def add_client():
    print("\n" + "=" * 60)
    print("  Добавить клиента")
    print("=" * 60)
    
    username = input("\nЛогин: ").strip()
    password = input("Пароль: ").strip()
    
    print("\nПлан:")
    print("1. Пробный (3 дня)")
    print("2. Месячный (30 дней)")
    print("3. Навсегда")
    plan_choice = input("Выбери (1-3): ").strip()
    
    plans = {"1": "trial", "2": "monthly", "3": "lifetime"}
    plan = plans.get(plan_choice, "trial")
    
    if create_client(username, password, plan):
        print(f"\n✅ Клиент {username} создан!")
        print(f"   Логин: {username}")
        print(f"   Пароль: {password}")
        print(f"   План: {plan}")
        print(f"   Отправь клиенту ссылку: http://ТВОЙ_IP:8501")
    else:
        print("\n❌ Ошибка создания")

def extend_client():
    username = input("\nЛогин клиента: ").strip()
    days = int(input("Добавить дней: ").strip())
    
    clients = load_clients()
    if username in clients["clients"]:
        current = datetime.fromisoformat(clients["clients"][username]["expires"])
        new_expires = current + timedelta(days=days)
        clients["clients"][username]["expires"] = new_expires.isoformat()
        clients["clients"][username]["active"] = True
        save_clients(clients)
        print(f"✅ Продлено до {new_expires.strftime('%d.%m.%Y')}")
    else:
        print("❌ Клиент не найден")

def deactivate_client():
    username = input("\nЛогин клиента: ").strip()
    clients = load_clients()
    if username in clients["clients"]:
        clients["clients"][username]["active"] = False
        save_clients(clients)
        print(f"✅ {username} отключён")
    else:
        print("❌ Клиент не найден")

if __name__ == "__main__":
    while True:
        print("\n" + "=" * 50)
        print("  Jinada.Trade — Админ-панель")
        print("=" * 50)
        print("\n1. Список клиентов")
        print("2. Добавить клиента")
        print("3. Продлить подписку")
        print("4. Отключить клиента")
        print("5. Выход")
        
        choice = input("\nВыбери действие: ").strip()
        
        if choice == "1":
            list_clients()
        elif choice == "2":
            add_client()
        elif choice == "3":
            extend_client()
        elif choice == "4":
            deactivate_client()
        elif choice == "5":
            break