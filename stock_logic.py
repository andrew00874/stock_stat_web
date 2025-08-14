# stock_logic.py

import pandas as pd
import re
import yfinance as yf
from io import StringIO
import datetime
import calendar
from functools import lru_cache
import time

#
# --- 여기서부터 ---
# `stock_stat.py` 파일의 모든 함수를 복사해서 붙여넣습니다.
# 단, 아래 GUI 관련 함수들은 제외합니다.
#
# 제외할 함수:
# - show_report_window
# - update_expiry_dates
# - show_report
# - create_gui
# - if __name__ == "__main__": 블록
#

@lru_cache(maxsize=32)
def get_expiry_dates(ticker):
    """옵션 만기일 목록을 가져옵니다."""
    max_retries = 3
    retry_delay = 2  # 초 단위
    
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            options = stock.options
            
            if not options:
                print(f"{ticker}의 옵션 데이터가 없습니다.")
                return []
                
            return sorted(options)  # 날짜순으로 정렬
            
        except Exception as e:
            # yfinance에서 발생하는 "Too Many Requests"는 다른 방식으로 처리될 수 있으므로, 일반적인 오류 처리를 강화합니다.
            if "Too Many Requests" in str(e) and attempt < max_retries - 1:
                print(f"API 요청 제한에 도달했습니다. {retry_delay}초 후 재시도합니다... (시도 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # 대기 시간을 2배로 증가
                continue
            print(f"만기일 가져오기 오류: {e}")
            return []
    
    return []

def extract_expiry_date(contract_name):
    """
    yfinance의 contractSymbol에서 만기일을 추출합니다.
    Bytes 타입으로 들어올 경우를 대비해 디코딩을 추가합니다.
    """
    # 만약 contract_name이 바이트(bytes) 타입이면, 문자열(string)로 변환(decode)합니다.
    if isinstance(contract_name, bytes):
        contract_name = contract_name.decode('utf-8')

    match = re.search(r"(\d{6})", contract_name)
    if match:
        expiry_date_raw = match.group(1)
        return f"20{expiry_date_raw[:2]}-{expiry_date_raw[2:4]}-{expiry_date_raw[4:]}"
    return "N/A"

@lru_cache(maxsize=32)
def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")["Close"].iloc[-1]
        return round(price, 2)
    except Exception as e:
        print(f"현재가 가져오기 오류: {e}")
        return "N/A"
    
def get_oi_range(df, threshold=0.85):
    """거래량 기반 레인지 계산"""
    if df.empty or df["openInterest"].sum() == 0:
        return 0, 0
        
    df_sorted = df.sort_values("strike")
    df_sorted["OI_Cumsum"] = df_sorted["openInterest"].cumsum()
    total_oi = df_sorted["openInterest"].sum()
    
    if total_oi == 0:
        return df_sorted["strike"].min(), df_sorted["strike"].max()
        
    df_filtered = df_sorted[df_sorted["OI_Cumsum"] <= total_oi * threshold]
    
    if df_filtered.empty:
        return df_sorted["strike"].min(), df_sorted["strike"].max()
        
    return df_filtered["strike"].min(), df_filtered["strike"].max()

def get_box_range_weighted(df, current_price, strike_distance_limit=0.25):
    """가중치 기반 박스권 계산"""
    if df.empty:
        return None
        
    lower = current_price * (1 - strike_distance_limit)
    upper = current_price * (1 + strike_distance_limit)
    df_filtered = df[df["strike"].between(lower, upper)].copy()
    
    if df_filtered.empty or df_filtered["openInterest"].sum() == 0:
        return None

    df_filtered["WeightedScore"] = df_filtered["openInterest"] * 0.3 + df_filtered["volume"] * 0.7
    
    if df_filtered["WeightedScore"].max() == 0:
        return None
        
    best_strike = df_filtered.loc[df_filtered["WeightedScore"].idxmax(), "strike"]
    
    return best_strike

def clean_numeric_columns(df, columns):
    """숫자형 칼럼 정리를 위한 헬퍼 함수"""
    # yfinance는 대부분의 데이터를 숫자형으로 잘 제공하므로, 불필요한 변환 대신 타입 검증 및 채우기 위주로 변경
    for col in columns:
        if col in df.columns:
            # yfinance는 volume, openInterest 등 이미 숫자형으로 제공
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def parse_options_data(call_df, put_df, ticker):
    """옵션 데이터 파싱 및 분석"""
    if call_df is None or put_df is None:
        return "❌ 유효한 옵션 데이터를 가져오지 못했습니다."
    if "strike" not in call_df.columns or "strike" not in put_df.columns:
        return "⚠️ 해당 만기일에 옵션 데이터(콜/풋)가 존재하지 않습니다."
    
    # yfinance에서 사용하는 칼럼명으로 변경
    yf_cols = {
        "Volume": "volume", "Open Interest": "openInterest", "Strike": "strike",
        "Implied Volatility": "impliedVolatility", "Last Price": "lastPrice",
        "Bid": "bid", "Ask": "ask", "Change": "change", "Contract Name": "contractSymbol"
    }

    # 데이터 전처리
    # ★★ 여기가 핵심적인 수정사항입니다! ★★
    # 데이터프레임의 contractSymbol 열을 강제로 문자열 타입으로 변환합니다.
    for df in [call_df, put_df]:
        if yf_cols["Contract Name"] in df.columns:
            df[yf_cols["Contract Name"]] = df[yf_cols["Contract Name"]].astype(str)
        # 숫자형 칼럼 정리
        for col_name in yf_cols.values():
             if col_name in df.columns and col_name != yf_cols["Contract Name"]:
                 df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)

    for df in [call_df, put_df]:
        df["Bid-Ask Spread"] = abs(df[yf_cols["Ask"]] - df[yf_cols["Bid"]])

    try:
        expiry_date = extract_expiry_date(call_df.iloc[0][yf_cols["Contract Name"]])
    except (IndexError, KeyError):
        expiry_date = "N/A"
        
    current_price = get_current_price(ticker)
    if current_price == "N/A":
        current_price = call_df[yf_cols["Strike"]].median()
    current_price = float(current_price)
    
    total_call_volume = call_df[yf_cols["Volume"]].sum()
    total_put_volume = put_df[yf_cols["Volume"]].sum()
    put_call_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else float('inf')
    
    if call_df.empty or put_df.empty or call_df[yf_cols["Volume"]].max() == 0 or put_df[yf_cols["Volume"]].max() == 0:
        return "❌ 데이터가 충분하지 않습니다. 다른 만기일을 선택해보세요."
    
    most_traded_call_row = call_df.loc[call_df[yf_cols["Volume"]].idxmax()]
    most_traded_put_row = put_df.loc[put_df[yf_cols["Volume"]].idxmax()]
    most_traded_call_strike = most_traded_call_row[yf_cols["Strike"]]
    most_traded_put_strike = most_traded_put_row[yf_cols["Strike"]]
    most_traded_call_oi = most_traded_call_row[yf_cols["Open Interest"]]
    most_traded_put_oi = most_traded_put_row[yf_cols["Open Interest"]]
    most_traded_call_volume = most_traded_call_row[yf_cols["Volume"]]
    most_traded_put_volume = most_traded_put_row[yf_cols["Volume"]]
    
    highest_change_call = call_df.loc[call_df[yf_cols["Change"]].abs().idxmax()]
    highest_change_put = put_df.loc[put_df[yf_cols["Change"]].abs().idxmax()]
    
    try:
        atm_call_row = call_df.loc[(call_df[yf_cols["Strike"]] - current_price).abs().idxmin()]
        atm_put_row = put_df.loc[(put_df[yf_cols["Strike"]] - current_price).abs().idxmin()]
        atm_call_iv = atm_call_row[yf_cols["Implied Volatility"]]
        atm_put_iv = atm_put_row[yf_cols["Implied Volatility"]]
        iv_skew = (atm_put_iv - atm_call_iv) * 100 # 퍼센트로 변환
    except Exception as e:
        print("ATM 분석 오류: ", e)
        atm_call_iv = atm_put_iv = iv_skew = 0
    
    bearish_sentiment = (put_df[yf_cols["Volume"]].mean() > call_df[yf_cols["Volume"]].mean())
    bullish_sentiment = (call_df[yf_cols["Volume"]].mean() > put_df[yf_cols["Volume"]].mean() and 
                         put_call_ratio < 1 and 
                         highest_change_call[yf_cols["Change"]] > highest_change_put[yf_cols["Change"]])
    
    mean_iv = (call_df[yf_cols["Implied Volatility"]].mean() + put_df[yf_cols["Implied Volatility"]].mean()) / 2 * 100
    iv_diff = abs(atm_call_iv - atm_put_iv) * 100
    high_iv = (mean_iv > 30 or iv_diff > 5)
    
    skew_threshold = 2.0
    is_significant_positive_skew = iv_skew > skew_threshold
    is_significant_negative_skew = iv_skew < -skew_threshold
    
    try:
        today = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        expiry_dt = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        days_to_expiry = (expiry_dt - today).days
    except:
        days_to_expiry = 30
    
    volume_score = min((total_call_volume + total_put_volume) / 100000, 1.0)
    oi_score = min((call_df[yf_cols["Open Interest"]].sum() + put_df[yf_cols["Open Interest"]].sum()) / 200000, 1.0)

    call_atm_mask = call_df[yf_cols["Strike"]].between(current_price * 0.95, current_price * 1.05)
    put_atm_mask = put_df[yf_cols["Strike"]].between(current_price * 0.95, current_price * 1.05)
    atm_volume = call_df[call_atm_mask][yf_cols["Volume"]].sum() + put_df[put_atm_mask][yf_cols["Volume"]].sum()
    atm_concentration = atm_volume / (total_call_volume + total_put_volume + 1e-6)
    atm_score = min(atm_concentration * 2, 1.0)

    if 5 <= days_to_expiry <= 45:
        time_score = 1.0
    elif days_to_expiry < 90:
        time_score = 0.7
    else:
        time_score = 0.3

    reliability_index = round((
        volume_score * 0.3 +
        oi_score * 0.3 +
        atm_score * 0.2 +
        time_score * 0.2
    ), 2)

    if reliability_index >= 0.8:
        reliability_msg = "거래량과 포지션이 풍부하며, 만기일도 적절합니다. → 매우 신뢰할 수 있습니다."
    elif reliability_index >= 0.6:
        reliability_msg = "보통 수준의 신뢰도입니다. 시장 심리 해석은 가능하지만 다소 주의가 필요합니다."
    else:
        reliability_msg = "데이터 신뢰도가 낮습니다. 해당 만기일은 참고 수준으로만 해석하세요."
    
    strategy = "🔍 중립: 시장 방향성이 뚜렷하지 않음."
    if bullish_sentiment:
        if not high_iv and is_significant_negative_skew:
            strategy = "🚀 매우 강한 매수 신호: 주식 매수 또는 레버리지 매수 + 저변동성 혜택 가능."
        elif high_iv and is_significant_negative_skew:
            strategy = "📈 조심스러운 매수 신호: 상승 기대는 있으나 변동성 리스크 존재."
        elif not high_iv:
            strategy = "🚀 매수 신호: 주식 매수 또는 콜 옵션 매수 유효."
        else:
            strategy = "📈 조심스러운 매수 신호: 상승 기대는 있으나 확실치 않음."
    elif bearish_sentiment:
        if not high_iv and is_significant_positive_skew:
            strategy = "⚠️ 매우 강한 매도 신호: 현물 매도 및 숏 포지션 유리 + 변동성 낮음."
        elif high_iv and is_significant_positive_skew:
            strategy = "📉 조심스러운 매도 신호: 하락 대비 심리 강화 + 변동성 주의."
        elif not high_iv:
            strategy = "⚠️ 일반 매도 신호: 방향은 약세지만 리스크는 낮음."
        else:
            strategy = "📉 조심스러운 매도 신호: 하락 대비 심리 강화이나 확실치 않음."
    else:
        if put_call_ratio > 1.2 and high_iv:
            strategy = "🧐 하락 대비 강화 중 (공포 심리 징후)"
        elif put_call_ratio < 0.8 and not high_iv:
            strategy = "👀 조심스러운 상승 기대감 (거래 약하지만 방향성 존재)"

    report_text = f"""
    📌 {ticker} 옵션 데이터 분석 보고서

    {strategy}
    📅 기준 옵션 만기일: {expiry_date}
    💰 현재 주가: ${current_price}

    🔥 거래량 TOP 옵션
    - 📈 콜 옵션 행사가: ${most_traded_call_strike}
        - Volume : {int(most_traded_call_volume)}
        - OI : {int(most_traded_call_oi)}
    - 📉 풋 옵션 행사가: ${most_traded_put_strike} 
        - Volume : {int(most_traded_put_volume)}
        - OI : {int(most_traded_put_oi)}

    📊 시장 심리 분석
    - 🔄 Put/Call Ratio: {put_call_ratio:.2f}
    - 🔄 IV Skew (Put - Call): {iv_skew:.2f}%
    - 📌 실시간 변동성: {mean_iv:.1f}%

    📈 신뢰도 분석
    - 🧮 신뢰도 지수: {reliability_index} / 1.00
    - 📘 해석: {reliability_msg}

    """.strip()

    put_box_min = get_box_range_weighted(put_df, current_price, strike_distance_limit=0.3)
    call_box_max = get_box_range_weighted(call_df, current_price, strike_distance_limit=0.3)
    if put_box_min and call_box_max:
        report_text += f"\n\n📦 시장 참여자 예상 박스권: ${put_box_min:.1f} ~ ${call_box_max:.1f}"

    return report_text
