# app.py – M&A SCANNER: CLOUD-OPTIMIZED
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import feedparser
import yfinance as yf
import plotly.graph_objects as go

# === SECRETS (CLOUD) ===
API_KEY = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
XAI_API_KEY = st.secrets.get("XAI_API_KEY", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

if not API_KEY:
    st.error("Add ALPHA_VANTAGE_API_KEY in secrets")
    st.stop()

# === TOKEN TRACKING ===
if 'SESSION_TOKENS' not in st.session_state:
    st.session_state.SESSION_TOKENS = 0

# === TELEGRAM ===
def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                     data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

# === THEME ===
st.set_page_config(page_title="M&A Scanner – @EastofElgin", layout="wide")
st.title("M&A Pro Scanner – @EastofElgin")
st.markdown("### **Grok + Options + Telegram + History**")

st.markdown("""
<style>
    .stApp { background-color: #282a36; color: #f8f8f2; }
    h1, h2, h3 { color: #ff79c6 !important; }
    .stButton>button { background-color: #44475a; color: #f8f8f2; border: 1px solid #6272a4; border-radius: 8px; }
    .stButton>button:hover { background-color: #6272a4; border-color: #ff79c6; }
    .signal-card { background-color: #343746; padding: 1rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #50fa7b; }
    .footer { text-align: center; color: #6272a4; margin-top: 3rem; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# === USER INFO ===
USER_X_HANDLE = "@EastofElgin"
USER_COUNTRY = "CA"
CURRENT_TIME = datetime.now().strftime("%B %d, %Y %I:%M %p EST")

st.sidebar.markdown(f"""
## User Info
- Current time: {CURRENT_TIME}
- X Handle: {USER_X_HANDLE}
- Country: {USER_COUNTRY}
""", unsafe_allow_html=True)

# === CONTROLS ===
if st.sidebar.button("SCAN NOW", type="primary"):
    st.session_state.scan_triggered = True

auto = st.sidebar.checkbox("Auto-refresh (5 min)")
show_charts = st.sidebar.checkbox("Show mini-charts", value=True)

# === GROK AI ===
@st.cache_data(ttl=300)
def analyze_with_grok(text, signal_type, ticker):
    if not XAI_API_KEY:
        return "Grok unavailable."
    try:
        r = requests.post("https://api.x.ai/v1/chat/completions",
                         json={
                             "model": "grok-4",
                             "messages": [{"role": "user", "content": f"Analyze {signal_type} for {ticker}: {text[:2000]}"}],
                             "max_tokens": 400
                         },
                         headers={"Authorization": f"Bearer {XAI_API_KEY}"}, timeout=30)
        if r.status_code == 200:
            data = r.json()
            total = data['usage']['total_tokens']
            st.session_state.SESSION_TOKENS += total
            return data['choices'][0]['message']['content']
    except: pass
    return "Analysis failed."

# === SIGNALS ===
@st.cache_data(ttl=300)
def get_signals():
    signals = []
    HEADERS = {'User-Agent': 'Mozilla/5.0'}

    # M&A News
    try:
        r = requests.get("https://finance.yahoo.com/news/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for h in soup.find_all('h3', class_='Mb(5px)')[:10]:
            text = h.get_text()
            if any(k in text.lower() for k in ['acquire', 'merger', 'buyout']):
                tickers = re.findall(r'\b[A-Z]{1,5}\b', text)
                if tickers:
                    signals.append({'type': 'M&A News', 'ticker': tickers[0], 'title': text})
    except: pass

    # SEC 8-K
    try:
        feed = feedparser.parse("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-k&count=40&output=atom")
        for e in feed.entries[:10]:
            title = e.title
            if any(k in title.lower() for k in ['acquisition', 'merger']):
                cik = re.search(r'CIK=(\d+)', e.link)
                if cik:
                    ticker = cik_to_ticker(cik.group(1))
                    if ticker:
                        signals.append({'type': 'SEC 8-K', 'ticker': ticker, 'title': title, 'link': e.link})
    except: pass

    return signals

def cik_to_ticker(cik):
    try:
        data = requests.get("https://www.sec.gov/files/company_tickers.json").json()
        for v in data.values():
            if str(v['cik_str']) == str(cik):
                return v['ticker']
    except: pass
    return None

# === OPTIONS STRATEGY ===
@st.cache_data(ttl=300)
def get_options_strategy(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        opts = stock.option_chain(stock.options[1])
        calls = opts.calls
        atm = calls.iloc[(calls['strike'] - price).abs().argsort()[:1]]
        otm = calls[calls['strike'] > atm['strike'].iloc[0]].iloc[0]
        debit = atm['lastPrice'].iloc[0] - otm['lastPrice'].iloc[0]
        return {
            'buy': f"Buy ${atm['strike'].iloc[0]} Call",
            'sell': f"Sell ${otm['strike'].iloc[0]} Call",
            'debit': f"${debit:.2f}",
            'breakeven': f"${atm['strike'].iloc[0] + debit:.2f}"
        }
    except: return None

# === SCAN ===
if st.session_state.get('scan_triggered', False) or auto:
    st.session_state.scan_triggered = False
    with st.spinner("Scanning..."):
        signals = get_signals()
        if signals:
            st.success(f"**{len(signals)} SIGNALS**")
            for s in signals:
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.markdown(f"**{s['ticker']}**")
                with col2:
                    st.markdown(f"**{s['type']}**: {s['title'][:100]}...")
                    if 'link' in s:
                        st.markdown(f"[View]({s['link']})")
                    if st.button("Grok", key=f"grok_{s['ticker']}"):
                        analysis = analyze_with_grok(s['title'], s['type'], s['ticker'])
                        st.markdown(f"<div style='background:#2e3a2e;padding:1rem;border-radius:5px;'>{analysis}</div>", unsafe_allow_html=True)
                    strategy = get_options_strategy(s['ticker'])
                    if strategy:
                        with st.expander("Options Strategy"):
                            st.markdown(f"**Buy:** {strategy['buy']}<br>**Sell:** {strategy['sell']}<br>**Cost:** {strategy['debit']}<br>**Breakeven:** {strategy['breakeven']}")
        else:
            st.info("No signals.")

st.markdown("<div class='footer'>M&A Scanner | Not advice</div>", unsafe_allow_html=True)
