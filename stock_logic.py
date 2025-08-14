import pandas as pd
import re
import yfinance as yf
import datetime
from functools import lru_cache
import time

# ======================================================================
# 섹션 1: 데이터 수집 및 기본 헬퍼 함수
# ======================================================================

@lru_cache(maxsize=32)
def fetch_options_data(ticker, expiry_date=None):
    """yfinance를 사용하여 특정 만기일의 옵션 데이터를 가져옵니다."""
    try:
        stock = yf.Ticker(ticker)
        options = stock.option_chain(expiry_date)
        call_options = options.calls
        put_options = options.puts
        # 데이터가 전혀 없는 경우 None을 반환하여 오류 처리
        if call_options.empty and put_options.empty:
            return None
        return call_options, put_options
    except Exception as e:
        print(f"yfinance 데이터 가져오기 오류: {ticker}, {expiry_date} - {e}")
        return None

@lru_cache(maxsize=32)
def get_expiry_dates(ticker):
    """특정 티커의 모든 옵션 만기일 목록을 가져옵니다."""
    try:
        stock = yf.Ticker(ticker)
        return sorted(stock.options)
    except Exception as e:
        print(f"만기일 가져오기 오류: {ticker} - {e}")
        return []

def extract_expiry_date(contract_name):
    """yfinance의 contractSymbol에서 만기일을 추출합니다 (YYYY-MM-DD 형식)."""
    if isinstance(contract_name, bytes):
        contract_name = contract_name.decode('utf-8')
    match = re.search(r"(\d{6})", contract_name)
    if match:
        raw_date = match.group(1)
        return f"20{raw_date[:2]}-{raw_date[2:4]}-{raw_date[4:]}"
    return "N/A"

@lru_cache(maxsize=32)
def get_current_price(ticker):
    """더 실시간에 가까운 주가를 가져옵니다."""
    try:
        stock = yf.Ticker(ticker)
        # 우선순위 1: 실시간 시장 가격
        info = stock.info
        price = info.get('regularMarketPrice')
        if price:
            return round(price, 2)
        # 우선순위 2: 이전 종가 (대체 수단)
        return round(stock.history(period="1d")["Close"].iloc[-1], 2)
    except Exception as e:
        print(f"현재가 가져오기 오류: {ticker} - {e}")
        return "N/A"

def get_box_range_weighted(df, current_price, strike_distance_limit=0.3):
    """미결제약정과 거래량을 가중치로 사용하여 지지/저항선을 계산합니다."""
    if df.empty: return None
    lower_bound = current_price * (1 - strike_distance_limit)
    upper_bound = current_price * (1 + strike_distance_limit)
    df_filtered = df[df["strike"].between(lower_bound, upper_bound)].copy()
    if df_filtered.empty or df_filtered["openInterest"].sum() == 0: return None
    
    # 가중치 점수 계산
    df_filtered["WeightedScore"] = df_filtered["openInterest"] * 0.3 + df_filtered["volume"] * 0.7
    
    if df_filtered["WeightedScore"].max() == 0: return None
    
    # 가장 높은 점수를 가진 행사가를 반환
    best_strike = df_filtered.loc[df_filtered["WeightedScore"].idxmax(), "strike"]
    return best_strike

# ======================================================================
# 섹션 2: 메인 분석 함수 (parse_options_data 대체)
# ======================================================================

def analyze_data_for_visualization(ticker, expiry_date):
    """
    옵션 데이터를 분석하고, 웹 시각화에 필요한 모든 데이터를 포함한
    구조화된 딕셔너리를 반환합니다.
    """
    options_data = fetch_options_data(ticker, expiry_date)
    if not options_data:
        return {"error": "해당 만기일의 옵션 데이터를 가져올 수 없습니다."}
    
    call_df, put_df = options_data
    
    if call_df.empty or put_df.empty:
        return {"error": "콜 또는 풋 옵션 데이터가 비어있습니다."}

    # --- 2-1. 데이터 전처리 ---
    yf_cols = {
        "Volume": "volume", "Open Interest": "openInterest", "Strike": "strike",
        "Implied Volatility": "impliedVolatility", "Last Price": "lastPrice",
        "Bid": "bid", "Ask": "ask", "Change": "change", "Contract Name": "contractSymbol"
    }
    for df in [call_df, put_df]:
        if "contractSymbol" in df.columns:
            df["contractSymbol"] = df["contractSymbol"].astype(str)
        for col in yf_cols.values():
            if col in df.columns and col != "contractSymbol":
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- 2-2. 핵심 지표 계산 ---
    current_price = get_current_price(ticker)
    if not isinstance(current_price, (int, float)): 
        current_price = call_df['strike'].median()

    total_call_volume = call_df['volume'].sum()
    total_put_volume = put_df['volume'].sum()
    put_call_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else float('inf')

    if put_call_ratio >= 1.2: pcr_msg = "극단적 비관 (매도 과열)"
    elif put_call_ratio >= 1.0: pcr_msg = "비관적 (하락 우려)"
    elif put_call_ratio >= 0.7: pcr_msg = "낙관적 (상승 기대)"
    else : pcr_msg= "극단적 낙관 (매수 과열)"
    # 등가격(ATM) 옵션 찾기 및 IV Skew 계산
    try:
        atm_call_row = call_df.iloc[(call_df['strike'] - current_price).abs().idxmin()]
        atm_put_row = put_df.iloc[(put_df['strike'] - current_price).abs().idxmin()]
        atm_call_iv = atm_call_row['impliedVolatility']
        atm_put_iv = atm_put_row['impliedVolatility']
        iv_skew = (atm_put_iv - atm_call_iv) * 100
    except Exception:
        atm_call_iv = atm_put_iv = iv_skew = 0

    mean_iv = (call_df['impliedVolatility'].mean() + put_df['impliedVolatility'].mean()) / 2 * 100
    iv_diff = abs(atm_call_iv - atm_put_iv) * 100
    high_iv = (mean_iv > 30 or iv_diff > 5)

    if (iv_skew > 5): iv_skew_msg = "극단적인 공포"
    elif (iv_skew >= 1): iv_skew_msg= "일반적인 하락 경계감"
    elif (iv_skew >= -1): iv_skew_msg= "중립"
    else: iv_skew_msg= "강한 낙관 혹은 투기적"

    mean_iv_msg = "종목의 특성에 따라 크게 차이가 날 수 있습니다."
    # --- 2-3. 신뢰도 지수 계산 ---
    try:
        today = datetime.datetime.now(datetime.timezone.utc)
        expiry_dt = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        days_to_expiry = (expiry_dt - today).days
    except Exception:
        days_to_expiry = 30 # 기본값

    volume_score = min((total_call_volume + total_put_volume) / 100000, 1.0)
    oi_score = min((call_df['openInterest'].sum() + put_df['openInterest'].sum()) / 200000, 1.0)
    
    call_atm_mask = call_df['strike'].between(current_price * 0.95, current_price * 1.05)
    put_atm_mask = put_df['strike'].between(current_price * 0.95, current_price * 1.05)
    atm_volume = call_df[call_atm_mask]['volume'].sum() + put_df[put_atm_mask]['volume'].sum()
    atm_concentration = atm_volume / (total_call_volume + total_put_volume + 1e-6)
    atm_score = min(atm_concentration * 2, 1.0)

    if 5 <= days_to_expiry <= 45: time_score = 1.0
    elif days_to_expiry < 90: time_score = 0.7
    else: time_score = 0.3
    
    reliability_index = round((volume_score * 0.3 + oi_score * 0.3 + atm_score * 0.2 + time_score * 0.2), 2)

    if reliability_index >= 0.8: reliability_msg = "거래량과 포지션이 풍부하며, 만기일도 적절합니다. → 매우 신뢰할 수 있습니다."
    elif reliability_index >= 0.6: reliability_msg = "보통 수준의 신뢰도입니다. 시장 심리 해석은 가능하지만 다소 주의가 필요합니다."
    else: reliability_msg = "데이터 신뢰도가 낮습니다. 해당 만기일은 참고 수준으로만 해석하세요."

    # --- 2-4. 시장 심리 및 전략 분석 ---
    highest_change_call = call_df.loc[call_df['change'].abs().idxmax()]
    highest_change_put = put_df.loc[put_df['change'].abs().idxmax()]

    bearish_sentiment = (put_df['volume'].mean() > call_df['volume'].mean())
    bullish_sentiment = (call_df['volume'].mean() > put_df['volume'].mean() and 
                         put_call_ratio < 1 and 
                         highest_change_call['change'] > highest_change_put['change'])
    
    skew_threshold = 2.0
    is_significant_positive_skew = iv_skew > skew_threshold
    is_significant_negative_skew = iv_skew < -skew_threshold

    strategy = "🔍 중립: 시장 방향성이 뚜렷하지 않음."
    if bullish_sentiment:
        if not high_iv and is_significant_negative_skew: strategy = "🚀 매우 강한 매수 신호: 주식 매수 또는 레버리지 매수 + 저변동성 혜택 가능."
        elif high_iv and is_significant_negative_skew: strategy = "📈 조심스러운 매수 신호: 상승 기대는 있으나 변동성 리스크 존재."
        elif not high_iv: strategy = "🚀 매수 신호: 주식 매수 또는 콜 옵션 매수 유효."
        else: strategy = "📈 조심스러운 매수 신호: 상승 기대는 있으나 확실치 않음."
    elif bearish_sentiment:
        if not high_iv and is_significant_positive_skew: strategy = "⚠️ 매우 강한 매도 신호: 현물 매도 및 숏 포지션 유리 + 변동성 낮음."
        elif high_iv and is_significant_positive_skew: strategy = "📉 조심스러운 매도 신호: 하락 대비 심리 강화 + 변동성 주의."
        elif not high_iv: strategy = "⚠️ 일반 매도 신호: 방향은 약세지만 리스크는 낮음."
        else: strategy = "📉 조심스러운 매도 신호: 하락 대비 심리 강화이나 확실치 않음."
    else:
        if put_call_ratio > 1.2 and high_iv: strategy = "🧐 하락 대비 강화 중 (공포 심리 징후)"
        elif put_call_ratio < 0.8 and not high_iv: strategy = "👀 조심스러운 상승 기대감 (거래 약하지만 방향성 존재)"

    # --- 2-5. 최종 결과물 구조화 ---
    most_traded_call_row = call_df.loc[call_df['volume'].idxmax()]
    most_traded_put_row = put_df.loc[put_df['volume'].idxmax()]
    put_box_min = get_box_range_weighted(put_df, current_price)
    call_box_max = get_box_range_weighted(call_df, current_price)

    result = {
        "ticker": ticker.upper(),
        "expiry_date": expiry_date,
        "current_price": current_price,
        "strategy": strategy,
        "market_sentiment": {
            "put_call_ratio": round(put_call_ratio, 2),
            "pcr_msg" : pcr_msg,
            "iv_skew_percent": round(iv_skew, 2),
            "iv_skew_msg" : iv_skew_msg,
            "mean_iv_percent": round(mean_iv, 1),
            "mean_iv_msg" : mean_iv_msg,
        },
        "reliability": {
            "score": reliability_index,
            "message": reliability_msg
        },
        "top_options": {
            "call": {"strike": most_traded_call_row['strike'], "volume": int(most_traded_call_row['volume']), "oi": int(most_traded_call_row['openInterest'])},
            "put": {"strike": most_traded_put_row['strike'], "volume": int(most_traded_put_row['volume']), "oi": int(most_traded_put_row['openInterest'])}
        },
        "box_range": {
            "min": round(put_box_min, 1) if put_box_min else None,
            "max": round(call_box_max, 1) if call_box_max else None
        },
        "chart_data": {
            "strikes": call_df['strike'].tolist(),
            "call_oi": call_df['openInterest'].astype(int).tolist(),
            "put_oi": put_df['openInterest'].astype(int).tolist(),
            "call_volume": call_df['volume'].astype(int).tolist(),
            "put_volume": put_df['volume'].astype(int).tolist()
        }
    }
    return result