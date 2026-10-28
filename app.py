"""
GLOBAL CLOSING DECIMAL ENGINE (KOSPI | TAIEX | DAX)
- Standalone multi-index decimal prediction dashboard.
- Strict Hard-Lock based on local exchange cut-offs converted to IST.
- Mathematical bands (+/-7) strictly preserved.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime

st.set_page_config(
    page_title="Global Closing Decimal Engine",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)

# -------------------------------------------------------------
# INDICES SPECIFICATIONS & TIMINGS (IST MAPPED)
# -------------------------------------------------------------
INDICES = {
    "KOSPI (South Korea)": {
        "ticker": "^KS11",
        "tz": "Asia/Seoul",
        "close_ist_str": "12:00 PM IST",
        "cuts": {
            "15m": {"hour": 11, "minute": 45, "label": "11:45 AM IST (15m Early)"},
            "5m":  {"hour": 11, "minute": 55, "label": "11:55 AM IST (5m Trend)"},
            "2m":  {"hour": 11, "minute": 58, "label": "11:58 AM IST (2m Precision)"}
        }
    },
    "TAIEX (Taiwan)": {
        "ticker": "^TWII",
        "tz": "Asia/Taipei",
        "close_ist_str": "11:00 AM IST",
        "cuts": {
            "15m": {"hour": 10, "minute": 45, "label": "10:45 AM IST (15m Early)"},
            "5m":  {"hour": 10, "minute": 55, "label": "10:55 AM IST (5m Trend)"},
            "2m":  {"hour": 10, "minute": 58, "label": "10:58 AM IST (2m Precision)"}
        }
    },
    "DAX (Germany)": {
        "ticker": "^GDAXI",
        "tz": "Europe/Berlin",
        "close_ist_str": "09:00 PM / 09:30 PM IST",
        "cuts": {
            "15m": {"hour": 20, "minute": 45, "label": "08:45 PM IST (15m Early)"},
            "5m":  {"hour": 20, "minute": 55, "label": "08:55 PM IST (5m Trend)"},
            "2m":  {"hour": 20, "minute": 58, "label": "08:58 PM IST (2m Precision)"}
        }
    }
}

# -------------------------------------------------------------
# MATH UTILITIES
# -------------------------------------------------------------
def extract_dec(price: float) -> int:
    return int(f"{price:.2f}".split(".")[1])

def get_band(center_dec: int, half_size: int = 7) -> set:
    half_size = int(round(half_size))
    return {(center_dec + k) % 100 for k in range(-half_size, half_size + 1)}

# -------------------------------------------------------------
# DATA FETCHER (CONVERTED STRICTLY TO IST)
# -------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def fetch_index_data(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        df = t.history(period="5d", interval="1m")
        if df.empty:
            return None
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(IST)
        else:
            df.index = df.index.tz_convert(IST)

        last_date = df.index[-1].date()
        df_today = df[df.index.date == last_date].copy()
        return df_today
    except Exception:
        return None

def compute_strict_cutoff(df, cut_h, cut_m, vwap_bars=15):
    # Strict Boolean Time Mask in IST
    mask = (df.index.hour < cut_h) | ((df.index.hour == cut_h) & (df.index.minute <= cut_m))
    df_cut = df[mask]
    if df_cut.empty:
        df_cut = df

    bar = df_cut.iloc[-1]
    p_cut = float(bar["Close"])
    dec_cut = extract_dec(p_cut)
    ts_cut = df_cut.index[-1]

    # Progressive VWAP
    vwap_win = df_cut.tail(vwap_bars)
    typ_p = (vwap_win["High"] + vwap_win["Low"] + vwap_win["Close"]) / 3.0
    vol = vwap_win["Volume"]
    vwap_val = (typ_p * vol).sum() / vol.sum() if vol.sum() > 0 else typ_p.mean()
    dec_vwap = extract_dec(vwap_val)

    b_price = get_band(dec_cut, 7)
    b_vwap = get_band(dec_vwap, 7)
    combined = sorted(list(b_price.union(b_vwap)))
    prime = sorted(list(b_price.intersection(b_vwap)))

    return {
        "price": p_cut,
        "dec_price": dec_cut,
        "vwap": vwap_val,
        "dec_vwap": dec_vwap,
        "combined": combined,
        "prime": prime,
        "timestamp": ts_cut
    }

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
st.sidebar.title("🌐 ग्लोबल इंडेक्स इंजन")
selected_name = st.sidebar.selectbox("इंडेक्स चुनें:", list(INDICES.keys()))
cfg = INDICES[selected_name]

if st.sidebar.button("🔄 डेटा रिफ्रेश करें"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write(f"**टिकर:** `{cfg['ticker']}`")
st.sidebar.write(f"**क्लोजिंग समय:** `{cfg['close_ist_str']}`")
st.sidebar.write(f"**वर्तमान IST समय:** `{now_ist.strftime('%H:%M:%S')}`")

# -------------------------------------------------------------
# MAIN APP BODY
# -------------------------------------------------------------
st.title(f"📊 {selected_name} — क्लोजिंग डेसिमल इंजन")
st.caption(f"आधिकारिक क्लोजिंग: {cfg['close_ist_str']} | हार्ड लॉक फ़्रीज़ तकनीक (±7 बैंड)")

df_market = fetch_index_data(cfg["ticker"])
if df_market is None or df_market.empty:
    st.error(f"डेटा लोड नहीं हो सका। कृपया जांचें कि क्या आज {selected_name} का बाज़ार अवकाश है।")
    st.stop()

# Compute all 3 cuts
c15 = cfg["cuts"]["15m"]
c5  = cfg["cuts"]["5m"]
c2  = cfg["cuts"]["2m"]

res_15 = compute_strict_cutoff(df_market, c15["hour"], c15["minute"], 15)
res_5  = compute_strict_cutoff(df_market, c5["hour"],  c5["minute"],  15)
res_2  = compute_strict_cutoff(df_market, c2["hour"],  c2["minute"],  15)

# Lock Status Checks
is_lock_15 = (now_ist.hour > c15["hour"]) or (now_ist.hour == c15["hour"] and now_ist.minute >= c15["minute"])
is_lock_5  = (now_ist.hour > c5["hour"])  or (now_ist.hour == c5["hour"]  and now_ist.minute >= c5["minute"])
is_lock_2  = (now_ist.hour > c2["hour"])  or (now_ist.hour == c2["hour"]  and now_ist.minute >= c2["minute"])

# High Conviction Overlap (5m & 2m common)
core_overlap = sorted(list(set(res_5["combined"]).intersection(set(res_2["combined"]))))

# -------------------------------------------------------------
# TOP: HIGH CONVICTION OVERLAP
# -------------------------------------------------------------
st.subheader("💎 HIGH CONVICTION CORE (5m और 2m में कॉमन अंक)")
if core_overlap:
    chips = " ".join([
        f"<span style='background-color:#0f172a;color:#38bdf8;padding:8px 14px;border-radius:6px;font-size:18px;font-weight:bold;margin:3px;display:inline-block;'>.{x:02d}</span>"
        for x in core_overlap
    ])
    st.markdown(chips, unsafe_allow_html=True)
    st.caption(f"कुल {len(core_overlap)} अंक जो दोनों सटीक बास्केट्स में कॉमन हैं।")
else:
    st.info("कोई कॉमन अंक नहीं मिला।")

st.markdown("---")

# -------------------------------------------------------------
# THREE CUT-OFF COLUMNS
# -------------------------------------------------------------
col1, col2, col3 = st.columns(3)

# 15m Cut
with col1:
    st.subheader("🟢 15-Min Early Cut")
    st.caption(c15["label"])
    if is_lock_15:
        st.success(f"🔒 **फ़्रीज़/लॉक है** ({res_15['timestamp'].strftime('%H:%M')} IST)")
    else:
        st.warning("⏳ समय का इंतज़ार...")

    m1, m2 = st.columns(2)
    m1.metric("कट भाव", f"{res_15['price']:,.2f}")
    m2.metric("दशमलव", f".{res_15['dec_price']:02d}")

    st.write(f"• VWAP: **.{res_15['dec_vwap']:02d}** ({res_15['vwap']:,.2f})")
    st.write(f"• बास्केट साइज़: **{len(res_15['combined'])} nos**")
    st.markdown("**📋 पूरी बास्केट:**")
    st.write(", ".join([f".{x:02d}" for x in res_15["combined"]]))

# 5m Cut
with col2:
    st.subheader("🔵 5-Min Trend Cut")
    st.caption(c5["label"])
    if is_lock_5:
        st.success(f"🔒 **फ़्रीज़/लॉक है** ({res_5['timestamp'].strftime('%H:%M')} IST)")
    else:
        st.warning("⏳ समय का इंतज़ार...")

    m1, m2 = st.columns(2)
    m1.metric("कट भाव", f"{res_5['price']:,.2f}")
    m2.metric("दशमलव", f".{res_5['dec_price']:02d}")

    st.write(f"• VWAP: **.{res_5['dec_vwap']:02d}** ({res_5['vwap']:,.2f})")
    st.write(f"• बास्केट साइज़: **{len(res_5['combined'])} nos**")
    st.markdown("**📋 पूरी बास्केट:**")
    st.write(", ".join([f".{x:02d}" for x in res_5["combined"]]))

# 2m Cut
with col3:
    st.subheader("🟠 2-Min Precision Cut")
    st.caption(c2["label"])
    if is_lock_2:
        st.success(f"🔒 **फ़्रीज़/लॉक है** ({res_2['timestamp'].strftime('%H:%M')} IST)")
    else:
        st.warning("⏳ समय का इंतज़ार...")

    m1, m2 = st.columns(2)
    m1.metric("कट भाव", f"{res_2['price']:,.2f}")
    m2.metric("दशमलव", f".{res_2['dec_price']:02d}")

    st.write(f"• VWAP: **.{res_2['dec_vwap']:02d}** ({res_2['vwap']:,.2f})")
    st.write(f"• बास्केट साइज़: **{len(res_2['combined'])} nos**")
    st.markdown("**📋 पूरी बास्केट:**")
    st.write(", ".join([f".{x:02d}" for x in res_2["combined"]]))
