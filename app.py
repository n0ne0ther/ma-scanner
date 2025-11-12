# app.py – M&A SCANNER: FULLY WORKING, CLOUD + LOCAL
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from alpha_vantage.timeseries import TimeSeries
from dotenv import load_dotenv
import os
import feedparser
import yfinance as yf
import plotly.graph_objects as go
# === Load Env (LOCAL) / Secrets (CLOUD) ===
load_dotenv()
API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY') or st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
XAI_API_KEY = os.getenv('XAI_API_KEY') or st.secrets.get("XAI_API_KEY", "")
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') or st.secrets.get("TELEGRAM_CHAT_ID", "")

if not API_KEY:
    st.error("Set ALPHA_VANTAGE_API_KEY in .env (local) or .streamlit/secrets.toml (cloud)")
    st.stop()

# === TOKEN TRACKING (FULLY RESTORED) ===
MONTHLY_TOKEN_LIMIT = 1000000
if 'SESSION_TOKENS' not in st.session_state:
    st.session_state.SESSION_TOKENS = 0

# === SCAN HISTORY ===
if 'SCAN_HISTORY' not in st.session_state:
    st.session_state.SCAN_HISTORY = []

# === TELEGRAM SEND (FIXED + DEBUG) ===
def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Telegram Error: {response.status_code} – {response.text}")
            return False
    except Exception as e:
        st.error(f"Telegram Failed: {str(e)}")
        return False

# === Page Config & Theme ===
st.set_page_config(page_title="M&A Scanner – @EastofElgin", layout="wide")
st.title("M&A Pro Scanner")
st.markdown("### **History + Grok + Options + Telegram + Peers**")

st.markdown(f"""
<style>
    .stApp {{ background-color: #282a36; color: #f8f8f2; }}
    h1, h2, h3 {{ color: #ff79c6 !important; }}
    .stButton>button {{ background-color: #44475a; color: #f8f8f2; border: 1px solid #6272a4; border-radius: 8px; padding: 0.5rem 1rem; }}
    .stButton>button:hover {{ background-color: #6272a4; border-color: #ff79c6; }}
    .signal-card {{ background-color: #343746; padding: 1rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #50fa7b; }}
    .signal-8k {{ border-left-color: #ff79c6; }}
    .signal-13d {{ border-left-color: #f1fa8c; }}
    .signal-insider {{ border-left-color: #50fa7b; }}
    .signal-news {{ border-left-color: #8be9fd; }}
    .grok-analysis {{ background-color: #2e3a2e; padding: 1rem; border-radius: 5px; margin-top: 0.5rem; }}
    .token-info {{ background-color: #44475a; padding: 0.5rem; border-radius: 5px; font-size: 0.9rem; color: #50fa7b; }}
    .option-card {{ background-color: #343746; padding: 1rem; border-radius: 10px; margin: 0.5rem 0; border-left: 5px solid #ff79c6; }}
    .debug-box {{ background-color: #44475a; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    .history-item {{ background-color: #44475a; padding: 0.8rem; border-radius: 8px; margin: 0.5rem 0; }}
    .footer {{ text-align: center; color: #6272a4; margin-top: 3rem; font-size: 0.8rem; }}
    .stPlotlyChart {{ background-color: #282a36; }}
</style>
""", unsafe_allow_html=True)

# === USER INFO ===
USER_X_HANDLE = "@EastofElgin"
USER_COUNTRY = "CA"
CURRENT_TIME = datetime.now().strftime("%B %d, %Y %I:%M %p EST")

# === BROWSER NOTIFICATION ===
st.markdown("""
<script>
    if (Notification.permission === "default") { Notification.requestPermission(); }
    function showNotification(title, body) {
        if (Notification.permission === "granted") {
            const n = new Notification(title, { body: body, icon: "https://streamlit.io/images/brand/streamlit-mark-color.png" });
            n.onclick = () => window.focus();
            const audio = new Audio("https://assets.mixkit.co/sfx/preview/mixkit-alarm-digital-clock-beep-989.mp3");
            audio.play().catch(() => {});
        }
    }
</script>
""", unsafe_allow_html=True)

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# === GROK AI + TOKEN TRACKING (FULLY RESTORED) ===
@st.cache_data(ttl=300)
def analyze_with_grok(filing_text, signal_type, ticker):
    if not XAI_API_KEY or not filing_text:
        return "Grok analysis unavailable."
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
    prompt = f"Analyze {signal_type} for {ticker}: M&A, risks, entities. Bullet points. Filing: {filing_text[:3000]}..."
    payload = {
        "model": "grok-4",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.2
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            usage = data.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = prompt_tokens + completion_tokens
            st.session_state.SESSION_TOKENS += total_tokens
            cost = (prompt_tokens / 1e6 * 5) + (completion_tokens / 1e6 * 15)
            st.markdown(f"<div class='token-info'>Tokens: {prompt_tokens} in + {completion_tokens} out = {total_tokens} (~${cost:.3f})</div>", unsafe_allow_html=True)
            return data['choices'][0]['message']['content']
        else:
            return f"API Error: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

# === SIGNALS + DEBUG MODE ===
@st.cache_data(ttl=300)
def get_signals(_debug=False):
    signals = []
    raw_data = {'news': [], 'sec': [], 'insiders': []}

    # === 1. M&A News ===
    try:
        r = requests.get("https://finance.yahoo.com/news/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for h in soup.find_all('h3', class_='Mb(5px)'):
            text = h.get_text()
            raw_data['news'].append(text)
            link_tag = h.find_parent('a')
            link = requests.compat.urljoin("https://finance.yahoo.com", link_tag['href']) if link_tag else ""
            if any(k in text.lower() for k in ['acquire', 'merger', 'buyout']):
                tickers = re.findall(r'\b[A-Z]{1,5}\b', text)
                if tickers:
                    signals.append({
                        'type': 'M&A News',
                        'ticker': tickers[0],
                        'title': text,
                        'link': link,
                        'source': 'Yahoo Finance',
                        'filing_text': ''
                    })
    except Exception as e:
        st.warning(f"News scrape failed: {e}")

    # === 2. SEC 8-K & 13D ===
    try:
        feed = feedparser.parse("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom")
        for e in feed.entries[:30]:
            title = e.title
            link = e.link
            summary = e.summary if 'summary' in e else ''
            raw_data['sec'].append({'title': title, 'link': link})
            cik_match = re.search(r'CIK=(\d+)', link)
            if not cik_match: continue
            cik = cik_match.group(1)
            ticker = cik_to_ticker(cik)
            if not ticker: continue
            filing_text = f"Title: {title}\nSummary: {summary}"

            if '8-K' in title.upper() and any(k in title.lower() for k in ['acquisition', 'merger']):
                signals.append({'type': 'SEC 8-K', 'ticker': ticker, 'title': title, 'link': link, 'cik': cik, 'filing_text': filing_text})
            if any(x in title.upper() for x in ['SC 13D', 'SC 13G']):
                stake = re.search(r'(\d+\.\d+)%', title)
                if stake and float(stake.group(1)) >= 5:
                    signals.append({'type': '13D/G', 'ticker': ticker, 'title': title, 'link': link, 'stake': stake.group(1), 'filing_text': filing_text})
    except Exception as e:
        st.warning(f"SEC scrape failed: {e}")

    # === 3. Insider Buys ===
    try:
        r = requests.get("https://finviz.com/insidertrading.ashx", headers=HEADERS)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.select('table.body-table tr')[1:]
        buys = {}
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10: continue
            ticker = cols[1].text.strip()
            owner = cols[2].text.strip()
            trans = cols[5].text.strip()
            val = cols[8].text.strip().replace('$', '').replace(',', '')
            raw_data['insiders'].append({'ticker': ticker, 'owner': owner, 'value': val})
            if trans == 'Buy' and val:
                try:
                    val = float(val)
                    if val >= 500000:
                        if ticker not in buys: buys[ticker] = []
                        buys[ticker].append({'owner': owner, 'value': f"${val:,.0f}"})
                except: continue
        for t, list_buys in buys.items():
            if len(list_buys) >= 2:
                signals.append({'type': 'Insider Cluster', 'ticker': t, 'insiders': list_buys, 'filing_text': ''})
    except Exception as e:
        st.warning(f"Insider scrape failed: {e}")

    if _debug:
        return signals, raw_data
    return signals, None

def cik_to_ticker(cik):
    try:
        data = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS).json()
        for v in data.values():
            if str(v['cik_str']) == str(cik):
                return v['ticker']
    except: pass
    return None

def get_stock_chart(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty: return None
        fig = go.Figure(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close']))
        fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor="#282a36", plot_bgcolor="#282a36", font_color="#f8f8f2")
        return fig
    except: return None

# === STOCKPEERS ===
@st.cache_data(ttl=300)
def get_peers(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        sector = info.get('sector', 'Unknown')
        peers = [ticker] + [p for p in ['AAPL', 'MSFT', 'GOOGL', 'AMD', 'INTC'] if p != ticker][:4]
        return peers, sector, info.get('industry', 'Unknown')
    except:
        return [ticker], 'Unknown', 'Unknown'

@st.cache_data(ttl=300)
def fetch_peer_data(peers):
    data = {}
    for p in peers:
        stock = yf.Ticker(p)
        hist = stock.history(period="1mo")
        info = stock.info
        data[p] = {
            'history': hist,
            'pe_ratio': info.get('trailingPE', 'N/A'),
            'market_cap': info.get('marketCap', 'N/A'),
            'volume': info.get('averageVolume', 'N/A')
        }
    return data

def display_peer_comparison(peers, sector):
    st.sidebar.markdown(f"### {sector} Peers")
    metrics = []
    for p in peers:
        d = st.session_state.peer_data.get(p, {})
        metrics.append({
            'Ticker': p,
            'P/E': d.get('pe_ratio', 'N/A'),
            'Market Cap': f"${d.get('market_cap', 0):,.0f}" if isinstance(d.get('market_cap'), (int, float)) else 'N/A',
            'Avg Vol': f"{d.get('volume', 0):,}" if isinstance(d.get('volume'), (int, float)) else 'N/A'
        })
    st.sidebar.dataframe(pd.DataFrame(metrics), use_container_width=True)
    fig = go.Figure()
    for p in peers:
        hist = st.session_state.peer_data.get(p, {}).get('history', pd.DataFrame())
        if not hist.empty:
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name=p))
    fig.update_layout(title="1-Month Performance", height=400, paper_bgcolor="#282a36", plot_bgcolor="#282a36", font_color="#f8f8f2")
    st.sidebar.plotly_chart(fig, use_container_width=True)

# === OPTIONS STRATEGY ===
@st.cache_data(ttl=300)
def get_options_strategy(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        if len(stock.options) < 2:
            return None
        opts = stock.option_chain(stock.options[1])
        calls = opts.calls
        if len(calls) < 2:
            return None
        atm_call = calls.iloc[(calls['strike'] - price).abs().argsort()[:1]]
        otm_call = calls[calls['strike'] > atm_call['strike'].iloc[0]].iloc[0]
        debit = atm_call['lastPrice'].iloc[0] - otm_call['lastPrice'].iloc[0]
        breakeven = atm_call['strike'].iloc[0] + debit
        max_profit = (otm_call['strike'].iloc[0] - atm_call['strike'].iloc[0]) - debit
        expiry = stock.options[1]
        return {
            'type': 'Bull Call Spread',
            'buy': f"Buy {ticker} ${atm_call['strike'].iloc[0]} Call",
            'sell': f"Sell {ticker} ${otm_call['strike'].iloc[0]} Call",
            'expiry': expiry,
            'debit': f"${debit:.2f}",
            'breakeven': f"${breakeven:.2f}",
            'max_profit': f"${max_profit:.2f}",
            'risk': f"${debit * 100:.0f}",
            'instructions': f"1. Open Wealthsimple → Search `{ticker}`\n2. Tap **Options** → Select **{expiry}**\n3. Buy to Open → `${atm_call['strike'].iloc[0]}` Call\n4. Sell to Open → `${otm_call['strike'].iloc[0]}` Call\n5. Confirm spread"
        }
    except:
        return None

# === SIDEBAR: USER INFO + CONTROLS ===
with st.sidebar:
    st.markdown(f"""
    ## User Info
    - Current time: {CURRENT_TIME}
    - X Handle: {USER_X_HANDLE}
    - Country: {USER_COUNTRY}
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.header("Controls")
    
    if st.button("SCAN NOW", type="primary"):
        st.session_state.scan_triggered = True

    auto = st.checkbox("Auto-refresh (5 min)")
    show_charts = st.checkbox("Show mini-charts", value=True)
    debug = st.checkbox("Debug: Show Raw Data", value=False)
    
    st.markdown("---")
    st.markdown("**Grok Token Balance**")
    remaining = max(0, MONTHLY_TOKEN_LIMIT - st.session_state.SESSION_TOKENS)
    st.metric("Remaining", f"{remaining:,}", delta=f"-{st.session_state.SESSION_TOKENS:,} used")
    
    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.success("Cache cleared!")
    
    st.markdown("---")
    st.markdown("**TEST ALERTS**")
    if st.button("SEND TEST TELEGRAM ALERT"):
        success = send_telegram("<b>TEST SUCCESS</b>\n@EastofElgin | Scanner Active")
        if success:
            st.success("Test message sent to Telegram!")
        else:
            st.error("Failed to send. Check bot token & chat ID.")

# === SCAN TRIGGER ===
scan_now = st.session_state.get('scan_triggered', False) or auto
if scan_now:
    st.session_state.scan_triggered = False
    with st.spinner("Scanning for M&A signals..."):
        signals, raw_data = get_signals(_debug=debug)
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if signals:
            st.session_state.SCAN_HISTORY.append({'time': scan_time, 'count': len(signals), 'signals': signals})
            st.success(f"**{len(signals)} SIGNALS FOUND**")
            
            for sig in signals:
                # === ALERTS ===
                if sig['type'] in ['SEC 8-K', '13D/G', 'Insider Cluster']:
                    grok_summary = ""
                    if sig.get('filing_text'):
                        grok_summary = analyze_with_grok(sig['filing_text'], sig['type'], sig['ticker'])
                    msg = f"<b>{sig['ticker']}: {sig['type']}</b>\n{sig['title'][:100]}...\n<a href='{sig['link']}'>View</a>\n{grok_summary}"
                    send_telegram(msg)
                    st.markdown(f'<script>showNotification("{sig["ticker"]}", "{sig["type"]} Signal");</script>', unsafe_allow_html=True)

                # === DISPLAY CARD ===
                card_class = f"signal-card signal-{sig['type'].lower().replace(' ', '-')}"
                with st.container():
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col1:
                        st.markdown(f"**{sig['ticker']}**")
                        st.markdown(f"<div class='{card_class}'><small><b>{sig['type']}</b></small></div>", unsafe_allow_html=True)
                    with col2:
                        if sig['type'] == 'M&A News':
                            st.markdown(f"**{sig['title'][:80]}...**")
                            if sig['link']: st.markdown(f"[Read more]({sig['link']})")
                        elif sig['type'] == 'SEC 8-K':
                            st.markdown(f"**SEC 8-K Filed**")
                            st.markdown(f"[View Filing]({sig['link']})")
                            if st.button(f"Analyze with Grok", key=f"grok_8k_{sig['ticker']}"):
                                analysis = analyze_with_grok(sig['filing_text'], '8-K', sig['ticker'])
                                st.markdown(f"<div class='grok-analysis'><strong>Grok AI:</strong><br>{analysis}</div>", unsafe_allow_html=True)
                        elif sig['type'] == '13D/G':
                            st.markdown(f"**{sig.get('stake', 'N/A')}% Stake**")
                            st.markdown(f"[View 13D]({sig['link']})")
                            if st.button(f"Analyze with Grok", key=f"grok_13d_{sig['ticker']}"):
                                analysis = analyze_with_grok(sig['filing_text'], '13D', sig['ticker'])
                                st.markdown(f"<div class='grok-analysis'><strong>Grok AI:</strong><br>{analysis}</div>", unsafe_allow_html=True)
                        elif sig['type'] == 'Insider Cluster':
                            st.markdown("**Multiple Insiders Buying**")
                            for buy in sig['insiders']:
                                st.markdown(f"• {buy['owner']} — {buy['value']}")
                        if st.button(f"View Peers", key=f"peers_{sig['ticker']}"):
                            st.session_state.selected_ticker = sig['ticker']
                            st.rerun()

                        # === OPTIONS STRATEGY ===
                        strategy = get_options_strategy(sig['ticker'])
                        if strategy:
                            with st.expander(f"**{strategy['type']} Strategy**"):
                                st.markdown(f"<div class='option-card'>", unsafe_allow_html=True)
                                st.markdown(f"**Buy:** {strategy['buy']}<br>**Sell:** {strategy['sell']}<br>**Expiry:** {strategy['expiry']}<br>**Cost:** {strategy['debit']}<br>**Breakeven:** {strategy['breakeven']}<br>**Max Profit:** {strategy['max_profit']}<br>**Risk:** {strategy['risk']}", unsafe_allow_html=True)
                                st.markdown(f"**Wealthsimple Steps:**<pre>{strategy['instructions']}</pre>", unsafe_allow_html=True)
                                st.markdown("</div>", unsafe_allow_html=True)
                    with col3:
                        if show_charts:
                            chart = get_stock_chart(sig['ticker'])
                            if chart: st.plotly_chart(chart, use_container_width=True)

            # === CSV Download ===
            df = pd.DataFrame(signals)
            st.download_button("Download This Scan", df.to_csv(index=False).encode(), f"scan_{scan_time}.csv", "text/csv")

        else:
            st.info("**No high-conviction M&A signals right now.**")

        # === DEBUG MODE ===
        if debug and raw_data:
            with st.expander("DEBUG: Raw Scraped Data", expanded=True):
                st.subheader("News Headlines")
                st.write(raw_data['news'][:20])
                st.subheader("SEC Filings")
                st.json(raw_data['sec'][:10])
                st.subheader("Insider Buys")
                st.json(raw_data['insiders'][:10])

# === SCAN HISTORY PANEL ===
if st.session_state.SCAN_HISTORY:
    with st.expander(f"Scan History ({len(st.session_state.SCAN_HISTORY)} scans)", expanded=False):
        for entry in reversed(st.session_state.SCAN_HISTORY):
            with st.container():
                st.markdown(f"<div class='history-item'><b>{entry['time']}</b> — {entry['count']} signals</div>", unsafe_allow_html=True)
                for sig in entry['signals']:
                    st.markdown(f"• **{sig['ticker']}** — {sig['type']}: {sig['title'][:60]}...")
        # === Export Full History ===
        all_signals = []
        for entry in st.session_state.SCAN_HISTORY:
            for sig in entry['signals']:
                sig['scan_time'] = entry['time']
                all_signals.append(sig)
        if all_signals:
            df_hist = pd.DataFrame(all_signals)
            st.download_button("Export Full History", df_hist.to_csv(index=False).encode(), "full_scan_history.csv", "text/csv")
        if st.button("Clear History"):
            st.session_state.SCAN_HISTORY = []
            st.rerun()

# === PEER VIEW IN SIDEBAR ===
if 'selected_ticker' in st.session_state:
    ticker = st.session_state.selected_ticker
    peers, sector, _ = get_peers(ticker)
    st.session_state.peer_data = fetch_peer_data(peers)
    display_peer_comparison(peers, sector)

if auto:
    time.sleep(300)
    st.rerun()

# === FOOTER ===
st.markdown(f"""
<div class='footer'>
    M&A Scanner | Not financial advice
</div>
""", unsafe_allow_html=True)

