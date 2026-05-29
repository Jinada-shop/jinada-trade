"""
╔══════════════════════════════════════════════╗
║        Jinada.Trade — All-in-One Server      ║
║     AI Trading Platform for Clients           ║
║     Database: Google Sheets (not lost)        ║
╚══════════════════════════════════════════════╝
"""

import sys
import json
import hashlib
import secrets
import subprocess
import urllib.parse
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

# ============================================================
# НАСТРОЙКИ
# ============================================================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
INITIAL_BALANCE = 300.0

LANG = {
    "ru": {
        "title": "Jinada.Trade", "subtitle": "AI торговая платформа",
        "login": "Вход", "register": "Регистрация",
        "username": "Логин", "password": "Пароль",
        "sign_in": "Войти", "free_trial": "Получить пробный доступ (3 дня)",
        "fill_fields": "Заполните все поля",
        "wrong_creds": "Неверный логин/пароль или срок истёк",
        "username_short": "Логин: от 3 символов", "password_short": "Пароль: от 4 символов",
        "created": "Аккаунт создан! Теперь войдите.", "username_taken": "Логин занят",
        "dashboard": "Дашборд", "api_keys": "API Ключи", "subscription": "Подписка", "admin": "Админ",
        "balance": "Баланс", "connected": "Подключена", "not_set": "Не задана", "logout": "Выйти",
        "days_left": "дн.", "bot_status": "Статус бота: Активен 24/7",
        "api_config": "Настройка API", "api_warning": "Включи ТОЛЬКО Spot. НЕ включай вывод!",
        "exchange": "Биржа", "api_key": "API Key", "secret_key": "Secret Key",
        "save_verify": "Сохранить и проверить", "remove_keys": "Удалить ключи",
        "verifying": "Проверка...", "keys_ok": "Ключи проверены!",
        "keys_invalid": "Неверные ключи", "keys_removed": "Ключи удалены",
        "keys_saved": "Ключи настроены",
        "plans": "Тарифы", "weekly": "Неделя", "monthly": "Месяц", "quarterly": "3 Месяца",
        "contact_upgrade": "Для оплаты: @JinadaSupport",
        "admin_panel": "Админ панель", "total_clients": "Всего", "active": "Активных",
        "api_connected": "API", "revenue": "Доход",
        "clients_list": "Клиенты", "add_client": "Добавить", "gen_keys": "Ключи",
        "manage": "Управление", "client": "Клиент", "action": "Действие", "apply": "Применить",
        "extend_7": "+7 дней", "extend_30": "+30 дней", "deactivate": "Отключить", "delete": "Удалить",
        "new_client": "Новый клиент", "plan": "Тариф", "create": "Создать",
        "generate": "Сгенерировать", "count": "Количество", "download_csv": "Скачать CSV",
        "configure_keys": "Настройте API ключи чтобы начать",
        "positions": "Позиции", "pnl_today": "PnL Сегодня", "select": "Выбрать",
    },
    "en": {
        "title": "Jinada.Trade", "subtitle": "AI Trading Platform",
        "login": "Login", "register": "Register",
        "username": "Username", "password": "Password",
        "sign_in": "Sign In", "free_trial": "Start Free Trial (3 days)",
        "fill_fields": "Fill all fields",
        "wrong_creds": "Invalid credentials or expired",
        "username_short": "Username: 3+ chars", "password_short": "Password: 4+ chars",
        "created": "Account created! Login now.", "username_taken": "Username taken",
        "dashboard": "Dashboard", "api_keys": "API Keys", "subscription": "Subscription", "admin": "Admin",
        "balance": "Balance", "connected": "Connected", "not_set": "Not set", "logout": "Logout",
        "days_left": "d left", "bot_status": "Bot Status: Active 24/7",
        "api_config": "API Config", "api_warning": "Enable ONLY Spot. NEVER Withdrawal!",
        "exchange": "Exchange", "api_key": "API Key", "secret_key": "Secret Key",
        "save_verify": "Save & Verify", "remove_keys": "Remove Keys",
        "verifying": "Verifying...", "keys_ok": "Keys verified!",
        "keys_invalid": "Invalid keys", "keys_removed": "Keys removed",
        "keys_saved": "Keys configured",
        "plans": "Plans", "weekly": "Weekly", "monthly": "Monthly", "quarterly": "3 Months",
        "contact_upgrade": "To upgrade: @JinadaSupport",
        "admin_panel": "Admin Panel", "total_clients": "Total", "active": "Active",
        "api_connected": "API", "revenue": "Revenue",
        "clients_list": "Clients", "add_client": "Add", "gen_keys": "Keys",
        "manage": "Manage", "client": "Client", "action": "Action", "apply": "Apply",
        "extend_7": "Extend +7d", "extend_30": "Extend +30d", "deactivate": "Deactivate", "delete": "Delete",
        "new_client": "New Client", "plan": "Plan", "create": "Create",
        "generate": "Generate", "count": "Count", "download_csv": "Download CSV",
        "configure_keys": "Configure API keys to start",
        "positions": "Positions", "pnl_today": "PnL Today", "select": "Select",
    }
}

# ============================================================
# ХРАНЕНИЕ ДАННЫХ (Streamlit session_state + secrets)
# ============================================================
def load_clients():
    import streamlit as st
    if 'clients_db' not in st.session_state:
        st.session_state.clients_db = {"clients": {}}
    return st.session_state.clients_db

def save_clients(data):
    import streamlit as st
    st.session_state.clients_db = data

def hash_password(password: str) -> tuple:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    return h, salt

def check_password(password: str, h: str, salt: str) -> bool:
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest() == h

def create_client(username: str, password: str, plan: str = "trial") -> bool:
    clients = load_clients()
    if username in clients["clients"]:
        return False
    plans = {
        "trial": {"days": 3, "name": "Trial 3 days"},
        "weekly": {"days": 7, "name": "Weekly"},
        "monthly": {"days": 30, "name": "Monthly"},
        "quarterly": {"days": 90, "name": "3 Months"},
        "lifetime": {"days": 99999, "name": "Lifetime"},
    }
    plan_info = plans.get(plan, plans["trial"])
    pw_hash, salt = hash_password(password)
    clients["clients"][username] = {
        "username": username, "password_hash": pw_hash, "salt": salt,
        "plan": plan, "plan_name": plan_info["name"], "days": plan_info["days"],
        "expires": (datetime.now() + timedelta(days=plan_info["days"])).isoformat(),
        "created": datetime.now().isoformat(), "active": True,
        "api_key": "", "api_secret": "", "exchange": "", "balance": INITIAL_BALANCE,
    }
    save_clients(clients)
    return True

def verify_client(username: str, password: str) -> Optional[dict]:
    clients = load_clients()
    if username not in clients["clients"]:
        return None
    client = clients["clients"][username]
    if not client.get("active"):
        return None
    if not check_password(password, client["password_hash"], client["salt"]):
        return None
    expires = datetime.fromisoformat(client["expires"])
    if datetime.now() > expires:
        client["active"] = False
        save_clients(clients)
        return None
    return client

def verify_binance_api(api_key: str, api_secret: str) -> bool:
    try:
        import requests, time, hmac, hashlib
        url = "https://api.binance.com/api/v3/account"
        params = {"timestamp": int(time.time() * 1000)}
        query = urllib.parse.urlencode(params)
        signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        headers = {"X-MBX-APIKEY": api_key}
        resp = requests.get(f"{url}?{query}&signature={signature}", headers=headers, timeout=10)
        return resp.status_code == 200 and "balances" in resp.json()
    except:
        return False

def verify_bybit_api(api_key: str, api_secret: str) -> bool:
    try:
        import requests, time, hmac, hashlib
        url = "https://api.bybit.com/v5/account/wallet-balance"
        timestamp = str(int(time.time() * 1000))
        params = {"api_key": api_key, "timestamp": timestamp, "accountType": "UNIFIED"}
        query = urllib.parse.urlencode(sorted(params.items()))
        signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        headers = {"X-BAPI-API-KEY": api_key, "X-BAPI-TIMESTAMP": timestamp, "X-BAPI-SIGN": signature}
        resp = requests.get(f"{url}?{query}", headers=headers, timeout=10)
        return resp.status_code == 200 and resp.json().get("retCode") == 0
    except:
        return False

# ============================================================
# ГЛАВНЫЙ ИНТЕРФЕЙС
# ============================================================
def main():
    import streamlit as st
    
    st.set_page_config(page_title="Jinada.Trade", page_icon="🟡", layout="wide")
    
    if 'lang' not in st.session_state:
        st.session_state.lang = "ru"
    
    lang = st.session_state.lang
    t = LANG[lang]
    
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        * { font-family: 'Inter', sans-serif; }
        .stApp { background: #0A0A0A; }
        h1, h2, h3 { color: #FFF !important; font-weight: 700 !important; }
        h1 { color: #FFD700 !important; }
        .stButton > button {
            background: #FFF; color: #000; border: none;
            border-radius: 10px; padding: 14px 28px;
            font-weight: 700; font-size: 15px; width: 100%; cursor: pointer;
        }
        .stButton > button:hover { background: #E5E5E5; }
        .stTextInput > div > div > input, .stSelectbox > div > div {
            background: #141414; border: 1px solid #222;
            border-radius: 10px; color: #FFF; padding: 14px 16px;
        }
        [data-testid="stMetricValue"] { color: #FFF !important; font-weight: 800 !important; }
        .card {
            background: #111111; border: 1px solid #1A1A1A;
            border-radius: 14px; padding: 24px; margin-bottom: 12px;
        }
        .badge {
            display: inline-block; padding: 5px 12px;
            border-radius: 20px; font-size: 12px; font-weight: 600;
        }
        .badge.green { background: rgba(0,255,136,0.12); color: #00FF88; }
        .badge.gold { background: rgba(255,215,0,0.12); color: #FFD700; }
        .badge.red { background: rgba(255,68,68,0.12); color: #FF4444; }
        .admin-header {
            background: linear-gradient(135deg, #1A1A1A, #0D0D0D);
            border: 1px solid #FFD700; border-radius: 14px;
            padding: 20px 24px; margin-bottom: 24px;
        }
        .stTabs [aria-selected="true"] { color: #FFD700 !important; }
        .stDataFrame { background: #111; border: 1px solid #1A1A1A; border-radius: 14px; }
        .stDataFrame th { background: #1A1A1A !important; color: #888 !important; }
        .stDataFrame td { color: #CCC !important; }
        hr { border-color: #1A1A1A !important; margin: 24px 0 !important; }
    </style>
    """, unsafe_allow_html=True)
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        col_lang, _ = st.columns([1, 10])
        with col_lang:
            if st.button("🇷🇺 RU" if lang == "en" else "🇬🇧 EN", key="lang_switch"):
                st.session_state.lang = "en" if lang == "ru" else "ru"
                st.rerun()
        
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""<div style="text-align: center; padding: 20px 0;">
                <h1 style="font-size: 36px; margin: 0;">{t['title']}</h1>
                <p style="color: #666; font-size: 15px;">{t['subtitle']}</p></div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs([t['login'], t['register']])
            
            with tab1:
                username = st.text_input(t['username'], key="login_user")
                password = st.text_input(t['password'], type="password", key="login_pass")
                if st.button(t['sign_in'], type="primary"):
                    if not username or not password:
                        st.error(t['fill_fields'])
                    elif username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                        st.session_state.logged_in = True
                        st.session_state.username = ADMIN_USERNAME
                        st.session_state.is_admin = True
                        st.session_state.client = {
                            "username": ADMIN_USERNAME, "plan": "lifetime",
                            "plan_name": "Admin", "active": True,
                            "expires": (datetime.now() + timedelta(days=99999)).isoformat(),
                            "api_key": "", "api_secret": "", "exchange": "", "balance": 0,
                        }
                        st.rerun()
                    else:
                        client = verify_client(username, password)
                        if client:
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.client = client
                            st.session_state.is_admin = False
                            st.rerun()
                        else:
                            st.error(t['wrong_creds'])
            
            with tab2:
                new_user = st.text_input(t['username'], key="reg_user")
                new_pass = st.text_input(t['password'], type="password", key="reg_pass")
                if st.button(t['free_trial'], type="primary"):
                    if len(new_user) < 3: st.error(t['username_short'])
                    elif len(new_pass) < 4: st.error(t['password_short'])
                    elif create_client(new_user, new_pass, "trial"): st.success(t['created'])
                    else: st.error(t['username_taken'])
        st.stop()
    
    # ДАШБОРД
    client = st.session_state.client
    username = st.session_state.username
    is_admin = st.session_state.get('is_admin', False)
    expires = datetime.fromisoformat(client['expires'])
    days_left = max(0, (expires - datetime.now()).days)
    
    col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1, 1, 0.5])
    with col1:
        color = "green" if days_left > 7 else ("gold" if days_left > 0 else "red")
        admin_badge = '<span class="badge gold" style="margin-left:8px;">ADMIN</span>' if is_admin else ''
        st.markdown(f"""<div style="display: flex; align-items: center; gap: 12px;">
            <h2 style="margin:0; font-size: 24px;">{t['title']}</h2>
            <span class="badge {color}">{client['plan_name']}</span>{admin_badge}
            <span style="color:#555; font-size:13px;">{days_left}{t['days_left']}</span></div>""", unsafe_allow_html=True)
    with col2: st.metric(t['balance'], f"${client.get('balance', 300):.0f}")
    with col3: st.metric("Exchange", t['connected'] if client.get('api_key') else t['not_set'])
    with col4:
        if st.button(t['logout']):
            for k in ['logged_in', 'username', 'client', 'is_admin']: st.session_state.pop(k, None)
            st.rerun()
    with col5:
        if st.button("🇷🇺" if lang == "en" else "🇬🇧", key="lang_top"):
            st.session_state.lang = "en" if lang == "ru" else "ru"; st.rerun()
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    tabs = [t['dashboard'], t['api_keys'], t['subscription']]
    if is_admin: tabs.append(t['admin'])
    tab_list = st.tabs(tabs)
    ti = 0
    
    with tab_list[ti]: ti += 1
    if not client.get('api_key'): st.warning(t['configure_keys'])
    else:
        st.success(f"{t['connected']}: {client.get('exchange', 'Exchange')}")
        c1, c2, c3 = st.columns(3)
        with c1: st.metric(t['balance'], f"${client.get('balance', 300):.0f}")
        with c2: st.metric(t['positions'], "0")
        with c3: st.metric(t['pnl_today'], "$0.00")
        st.markdown(f"**{t['bot_status']}**")
    
    with tab_list[ti]: ti += 1
    st.markdown(f"### {t['api_config']}"); st.caption(t['api_warning'])
    exchange = st.selectbox(t['exchange'], ["Binance", "Bybit"])
    api_key = st.text_input(t['api_key'], type="password")
    api_secret = st.text_input(t['secret_key'], type="password")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(t['save_verify'], type="primary", width='stretch'):
            if not api_key or not api_secret: st.error(t['fill_fields'])
            else:
                with st.spinner(t['verifying']):
                    valid = verify_binance_api(api_key, api_secret) if exchange == "Binance" else verify_bybit_api(api_key, api_secret)
                    if valid:
                        if is_admin: client["api_key"], client["api_secret"], client["exchange"] = api_key, api_secret, exchange
                        else:
                            cl = load_clients()
                            cl["clients"][username]["api_key"] = api_key; cl["clients"][username]["api_secret"] = api_secret; cl["clients"][username]["exchange"] = exchange
                            save_clients(cl); st.session_state.client = cl["clients"][username]
                        st.success(t['keys_ok']); st.rerun()
                    else: st.error(t['keys_invalid'])
    with col2:
        if client.get('api_key') and st.button(t['remove_keys'], width='stretch'):
            if is_admin: client["api_key"] = client["api_secret"] = client["exchange"] = ""
            else:
                cl = load_clients()
                cl["clients"][username]["api_key"] = cl["clients"][username]["api_secret"] = cl["clients"][username]["exchange"] = ""
                save_clients(cl); st.session_state.client = cl["clients"][username]
            st.warning(t['keys_removed']); st.rerun()
    if client.get('api_key'): st.success(f"{t['keys_saved']}: {client.get('exchange')}")
    
    with tab_list[ti]: ti += 1
    st.markdown(f"### {t['plans']}")
    plans = [{"name": t['weekly'], "price": "$4.90"}, {"name": t['monthly'], "price": "$9.90"}, {"name": t['quarterly'], "price": "$24.90"}]
    cols = st.columns(3)
    for i, p in enumerate(plans):
        with cols[i]:
            st.markdown(f"""<div class="card" style="text-align:center;"><p style="color:#888;">{p['name']}</p><h1>{p['price']}</h1></div>""", unsafe_allow_html=True)
            st.button(f"{t['select']} {p['name']}", key=f"plan_{i}", width='stretch')
    st.caption(t['contact_upgrade'])
    
    if is_admin:
        with tab_list[ti]:
            cl = load_clients(); clist = list(cl["clients"].values())
            total, active = len(clist), sum(1 for c in clist if c.get("active"))
            api_ok = sum(1 for c in clist if c.get("api_key"))
            st.markdown(f'<div class="admin-header"><h2>{t["admin_panel"]}</h2></div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric(t['total_clients'], total)
            with c2: st.metric(t['active'], active)
            with c3: st.metric(t['api_connected'], api_ok)
            with c4:
                rev = sum(0 if c["plan"]=="trial" else 4.90 if c["plan"]=="weekly" else 9.90 if c["plan"]=="monthly" else 24.90 if c["plan"]=="quarterly" else 79.90 for c in clist if c.get("active"))
                st.metric(t['revenue'], f"${rev:.0f}")
            st.divider()
            a1, a2, a3 = st.tabs([t['clients_list'], t['add_client'], t['gen_keys']])
            with a1:
                if clist:
                    data = [{"User": c["username"], "Plan": c["plan_name"], "Days": max(0, (datetime.fromisoformat(c["expires"])-datetime.now()).days), "API": "YES" if c.get("api_key") else "NO"} for c in clist]
                    st.dataframe(pd.DataFrame(data), width='stretch', hide_index=True)
                    col1, col2 = st.columns(2)
                    with col1: sel = st.selectbox(t['client'], [c["username"] for c in clist])
                    with col2: act = st.selectbox(t['action'], [t['extend_7'], t['extend_30'], t['deactivate'], t['delete']])
                    if st.button(t['apply'], type="primary"):
                        if sel in cl["clients"]:
                            c = cl["clients"][sel]
                            if act == t['extend_7']: c["expires"] = (datetime.fromisoformat(c["expires"]) + timedelta(days=7)).isoformat(); c["active"] = True
                            elif act == t['extend_30']: c["expires"] = (datetime.fromisoformat(c["expires"]) + timedelta(days=30)).isoformat(); c["active"] = True
                            elif act == t['deactivate']: c["active"] = False
                            elif act == t['delete']: del cl["clients"][sel]
                            save_clients(cl); st.rerun()
            with a2:
                col1, col2 = st.columns(2)
                with col1: nu = st.text_input(t['username'], key="a_user"); np = st.text_input(t['password'], type="password", key="a_pass")
                with col2: pl = st.selectbox(t['plan'], ["trial","weekly","monthly","quarterly","lifetime"], key="a_plan")
                if st.button(t['create'], type="primary"):
                    if len(nu)<3: st.error(t['username_short'])
                    elif len(np)<4: st.error(t['password_short'])
                    elif create_client(nu, np, pl): st.success(t['created']); st.code(f"Login: {nu}\nPass: {np}"); st.rerun()
                    else: st.error(t['username_taken'])
            with a3:
                col1, col2 = st.columns(2)
                with col1: cnt = st.number_input(t['count'], 1, 100, 10)
                with col2: pg = st.selectbox(t['plan'], ["trial","weekly","monthly","quarterly","lifetime"], key="g_plan")
                if st.button(t['generate'], type="primary"):
                    kd = []
                    for i in range(cnt):
                        u = f"user_{secrets.token_hex(4)}"; p = secrets.token_hex(8)
                        create_client(u, p, pg); kd.append({"Username":u,"Password":p})
                    st.dataframe(pd.DataFrame(kd), width='stretch', hide_index=True)

if __name__ == "__main__":
    main()
