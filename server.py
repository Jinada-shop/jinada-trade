"""
Jinada.Trade — Multi-Client Server
Один сервер обслуживает всех клиентов
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import sys
import json
import hashlib
import secrets
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config import config
from database import get_db, init_database

# ============================================================
# УПРАВЛЕНИЕ КЛИЕНТАМИ
# ============================================================
CLIENTS_FILE = Path("clients.json")

def load_clients():
    if CLIENTS_FILE.exists():
        return json.loads(CLIENTS_FILE.read_text())
    return {"clients": {}}

def save_clients(data):
    CLIENTS_FILE.write_text(json.dumps(data, indent=2))

def create_client(username: str, password: str, plan: str = "trial"):
    """Создать нового клиента"""
    clients = load_clients()
    
    # Хешируем пароль
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    # План
    plans = {
        "trial": {"days": 3, "name": "Пробный"},
        "monthly": {"days": 30, "name": "Месячный"},
        "lifetime": {"days": 99999, "name": "Навсегда"},
    }
    
    plan_info = plans.get(plan, plans["trial"])
    expires = datetime.now() + timedelta(days=plan_info["days"])
    
    clients["clients"][username] = {
        "username": username,
        "password_hash": password_hash,
        "salt": salt,
        "plan": plan,
        "plan_name": plan_info["name"],
        "expires": expires.isoformat(),
        "created": datetime.now().isoformat(),
        "active": True,
        "api_key": "",
        "api_secret": "",
        "exchange": "",
        "balance": config.INITIAL_BALANCE,
        "trades": []
    }
    
    save_clients(clients)
    return True

def verify_client(username: str, password: str):
    """Проверить логин/пароль"""
    clients = load_clients()
    
    if username not in clients["clients"]:
        return None
    
    client = clients["clients"][username]
    
    if not client["active"]:
        return None
    
    # Проверка пароля
    password_hash = hashlib.sha256(f"{password}{client['salt']}".encode()).hexdigest()
    if password_hash != client["password_hash"]:
        return None
    
    # Проверка срока
    expires = datetime.fromisoformat(client["expires"])
    if datetime.now() > expires:
        client["active"] = False
        save_clients(clients)
        return None
    
    return client

def update_client_api(username: str, api_key: str, api_secret: str, exchange: str):
    """Обновить API ключи клиента"""
    clients = load_clients()
    if username in clients["clients"]:
        clients["clients"][username]["api_key"] = api_key
        clients["clients"][username]["api_secret"] = api_secret
        clients["clients"][username]["exchange"] = exchange
        save_clients(clients)
        return True
    return False

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================
init_database()

st.set_page_config(
    page_title="Jinada.Trade | AI Trading",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: #0D0D0D; }
    [data-testid="stSidebar"] { background: #111111; border-right: 1px solid #222; }
    h1 { color: #FFF !important; font-weight: 700 !important; }
    h2 { color: #FFF !important; font-weight: 600 !important; }
    h3 { color: #AAA !important; font-weight: 500 !important; }
    
    .stButton > button {
        background: #FFF;
        color: #000;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 14px;
        transition: all 0.2s;
        width: 100%;
    }
    .stButton > button:hover {
        background: #E5E5E5;
        transform: translateY(-1px);
    }
    
    .stTextInput > div > div > input {
        background: #141414;
        border: 1px solid #222;
        border-radius: 8px;
        color: #FFF;
        padding: 12px;
    }
    
    [data-testid="stMetricValue"] {
        color: #FFF !important;
        font-size: 28px !important;
        font-weight: 700 !important;
    }
    
    .card {
        background: #141414;
        border: 1px solid #222;
        border-radius: 12px;
        padding: 20px;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
    }
    .badge.green { background: rgba(0,255,136,0.1); color: #00FF88; }
    .badge.red { background: rgba(255,68,68,0.1); color: #FF4444; }
    .badge.gold { background: rgba(255,215,0,0.1); color: #FFD700; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# СЕССИЯ
# ============================================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'client_data' not in st.session_state:
    st.session_state.client_data = None

# ============================================================
# СТРАНИЦА ЛОГИНА
# ============================================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align: center;">
            <h1 style="font-size: 36px;">Jinada.Trade</h1>
            <p style="color: #888;">AI Trading Platform</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Вход", "Регистрация"])
        
        with tab1:
            username = st.text_input("Логин", placeholder="username")
            password = st.text_input("Пароль", type="password", placeholder="••••••")
            
            if st.button("Войти", type="primary"):
                client = verify_client(username, password)
                if client:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.client_data = client
                    st.rerun()
                else:
                    st.error("Неверный логин/пароль или срок истёк")
        
        with tab2:
            new_username = st.text_input("Придумай логин", placeholder="username", key="reg_user")
            new_password = st.text_input("Придумай пароль", type="password", placeholder="••••••", key="reg_pass")
            
            if st.button("Зарегистрироваться (пробный 3 дня)", type="primary"):
                if len(new_username) < 3:
                    st.error("Логин должен быть от 3 символов")
                elif len(new_password) < 4:
                    st.error("Пароль должен быть от 4 символов")
                else:
                    clients = load_clients()
                    if new_username in clients["clients"]:
                        st.error("Такой логин уже занят")
                    else:
                        create_client(new_username, new_password, "trial")
                        st.success("✅ Аккаунт создан! Теперь войди.")
    
    st.stop()

# ============================================================
# ДАШБОРД КЛИЕНТА
# ============================================================
client = st.session_state.client_data
username = st.session_state.username

# Верхняя панель
col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

with col1:
    expires = datetime.fromisoformat(client['expires'])
    days_left = (expires - datetime.now()).days
    status_color = "green" if days_left > 7 else ("gold" if days_left > 0 else "red")
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px;">
        <h2 style="margin: 0;">Jinada.Trade</h2>
        <span class="badge {status_color}">{client['plan_name']}</span>
        <span style="color: #666; font-size: 13px;">{days_left} дн. осталось</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.metric("Баланс", f"${client.get('balance', 300):.0f}")

with col3:
    st.metric("Сделок сегодня", "—")

with col4:
    if st.button("Выйти"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.client_data = None
        st.rerun()

st.markdown("<hr style='border-color: #222;'>", unsafe_allow_html=True)

# Вкладки
tab1, tab2, tab3 = st.tabs(["📊 Дашборд", "🔑 API Ключи", "⚙️ Настройки"])

with tab1:
    st.markdown("### 📊 Торговый дашборд")
    
    # Проверка API ключей
    if not client.get('api_key'):
        st.warning("⚠️ Добавь API-ключи биржи во вкладке 'API Ключи' чтобы начать торговлю")
    else:
        st.success(f"✅ Подключена биржа: {client.get('exchange', 'Binance').upper()}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("Баланс биржи", f"${client.get('balance', 300):.0f}")
            st.caption(f"Биржа: {client.get('exchange', '-')}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("Открыто позиций", "0")
            st.caption("Активные сделки")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.metric("PnL сегодня", "$0.00")
            st.caption("Прибыль/убыток")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Заглушка графика
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### График баланса")
        
        dates = pd.date_range(start=datetime.now()-timedelta(days=7), periods=7, freq='D')
        balances = [300, 302, 305, 301, 308, 312, 315]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=balances,
            mode='lines',
            line=dict(color='#FFF', width=2),
            fill='tozeroy',
            fillcolor='rgba(255,255,255,0.03)'
        ))
        fig.update_layout(
            template='plotly_dark',
            height=350,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, color='#666'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#666')
        )
        st.plotly_chart(fig, config={'displayModeBar': False}, width='stretch')
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown("### 🔑 API Ключи биржи")
    st.caption("Ключи нужны ТОЛЬКО для торговли. Право на вывод НЕ включать!")
    
    exchange = st.selectbox("Биржа", ["Binance", "Bybit"])
    api_key = st.text_input("API Key", type="password", placeholder="Вставь API Key")
    api_secret = st.text_input("Secret Key", type="password", placeholder="Вставь Secret Key")
    
    if st.button("💾 Сохранить ключи", type="primary"):
        update_client_api(username, api_key, api_secret, exchange)
        st.success("✅ Ключи сохранены! Бот начнёт торговлю.")
        st.rerun()
    
    st.markdown("---")
    st.markdown("""
    **Как получить API ключи:**
    1. Зайди в настройки биржи
    2. Создай новый API ключ
    3. Включи **ТОЛЬКО Spot Trading**
    4. **НЕ включай** Withdrawal (вывод средств)
    5. Скопируй ключи сюда
    """)

with tab3:
    st.markdown("### ⚙️ Настройки торговли")
    
    risk = st.slider("Риск на сделку (%)", 0.5, 5.0, 1.5, 0.1)
    max_pos = st.selectbox("Максимум позиций", [1, 2, 3], index=1)
    
    strategies = st.multiselect(
        "Стратегии",
        ["Scalping", "Trend", "Counter-Trend", "Grid"],
        default=["Scalping", "Counter-Trend"]
    )
    
    st.markdown("---")
    
    st.markdown("### 💳 Продлить подписку")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**1 месяц**")
        st.markdown("## 9.90$")
        st.button("Выбрать", key="plan1")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**3 месяца**")
        st.markdown("## 24.90$")
        st.caption("Скидка 16%")
        st.button("Выбрать", key="plan3")
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**12 месяцев**")
        st.markdown("## 79.90$")
        st.caption("Скидка 33%")
        st.button("Выбрать", key="plan12")
        st.markdown('</div>', unsafe_allow_html=True)

# Футер
st.markdown("<br><hr style='border-color: #222;'>", unsafe_allow_html=True)
st.markdown(f"""
<div style="display: flex; justify-content: space-between; color: #444; font-size: 12px;">
    <span>Jinada.Trade v4.0</span>
    <span>{username} | {client['plan_name']}</span>
    <span>{datetime.now().strftime('%d.%m.%Y %H:%M')}</span>
</div>
""", unsafe_allow_html=True)