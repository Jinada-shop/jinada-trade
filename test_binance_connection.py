"""
Файл: test_binance_connection.py
Проверка подключения к Binance разными способами.
"""

import asyncio
import socket

async def test_connection():
    print("=" * 50)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К BINANCE")
    print("=" * 50)
    
    # 1. Проверяем DNS
    print("\n1. DNS резолвинг:")
    try:
        ip = socket.gethostbyname("api.binance.com")
        print(f"   ✅ api.binance.com → {ip}")
    except Exception as e:
        print(f"   ❌ {e}")
    
    # 2. Проверяем через aiohttp
    print("\n2. Прямой HTTP запрос:")
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.binance.com/api/v3/ping") as resp:
                data = await resp.json()
                print(f"   ✅ Статус: {resp.status}, Ответ: {data}")
    except Exception as e:
        print(f"   ❌ {e}")
    
    # 3. Пробуем python-binance без API ключей
    print("\n3. python-binance (публичный доступ):")
    try:
        from binance import AsyncClient
        client = await AsyncClient.create()
        status = await client.get_system_status()
        print(f"   ✅ Статус Binance: {status}")
        await client.close_connection()
    except Exception as e:
        print(f"   ❌ {e}")
    
    # 4. Пробуем с API ключами
    print("\n4. python-binance (с API ключами):")
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        
        api_key = os.getenv("BINANCE_API_KEY")
        secret = os.getenv("BINANCE_SECRET_KEY")
        
        if api_key and secret:
            from binance import AsyncClient
            client = await AsyncClient.create(api_key=api_key, api_secret=secret)
            info = await client.get_account()
            print(f"   ✅ Подключён! Балансы загружены")
            await client.close_connection()
        else:
            print("   ⚠️ API ключи не найдены в .env")
    except Exception as e:
        print(f"   ❌ {e}")
    
    # 5. Проверяем через requests (синхронно)
    print("\n5. requests (синхронный):")
    try:
        import requests
        resp = requests.get("https://api.binance.com/api/v3/ping", timeout=10)
        print(f"   ✅ Статус: {resp.status_code}, Ответ: {resp.json()}")
    except Exception as e:
        print(f"   ❌ {e}")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    asyncio.run(test_connection())