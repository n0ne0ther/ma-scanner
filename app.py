# app.py – M&A SCANNER: GROK TOKENS FULLY RESTORED + ALL FEATURES
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

# === Load Env ===
load_dotenv()
API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
XAI_API_KEY = os.getenv('XAI_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not API_KEY:
    st.error("Set ALPHA_VANTAGE_API_KEY in .env file")
    st.stop()
if not XAI_API_KEY:
    st.warning("Set XAI_API_KEY in .env for Grok AI analysis")
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    st.warning("Set TELEGRAM_TOKEN & TELEGRAM_CHAT_ID in .env for alerts")

ts = TimeSeries(key=API_KEY, output_format='pandas')

# === TOKEN TRACKING (FULLY RESTORED) ===
MONTHLY_TOKEN_LIMIT = 1000000
if 'SESSION_TOKENS' not in st.session_state:
    st.session_state.SESSION_TOKENS = 0

# === SCAN HISTORY ===
if 'SCAN_HISTORY' not in st.session_state:
    st.session_state.SCAN_HISTORY = []

# === TELEGRAM SEND ===
def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, data=payload, timeout=10)
    except: pass

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
    .signal-insider {{ border-left-color: #50fa7b
