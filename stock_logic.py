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

# 캐싱을 통한 성능 최적화 - yfinance로 데이터 수집 방식 변경
@lru_cache(maxsize=32)
def fetch_options_data(ticker, expiry_date=None):
    """
    yfinance를 사용하여 특정 만기일의 옵션 데이터를 가져옵니다.
    """
    try:
        stock = yf.Ticker(ticker)
        options = stock.option_chain(expiry_date)
        call_options = options.calls
        put_options = options.puts

        if call_options.empty or put_options.empty:
            print(f"{ticker}의 {expiry_date} 만기일 데이터가 비어있습니다.")
            return None

        return call_options, put_options, ticker

    except Exception as e:
        print(f"yfinance로 데이터 가져오기 오류: {e}")
        return None

# ( ... 중간 생략 ... )
# `parse_options_data` 함수까지 모두 복사

def parse_options_data(call_df, put_df, ticker):
    """옵션 데이터 파싱 및 분석"""
    if call_df is None or put_df is None:
        return "❌ 유효한 옵션 데이터를 가져오지 못했습니다."
    # ( ... 기존 코드와 동일 ... )
    # 보고서 텍스트의 줄바꿈(\n)을 HTML 태그(<br>)로 변경하면 웹에서 보기 좋습니다.
    report_text = f"""
    📌 {ticker} 옵션 데이터 분석 보고서 <br><br>

    {strategy}<br>
    📅 기준 옵션 만기일: {expiry_date}<br>
    💰 현재 주가: ${current_price}<br><br>

    🔥 거래량 TOP 옵션<br>
    - 📈 콜 옵션 행사가: ${most_traded_call_strike}<br>
        - Volume : {int(most_traded_call_volume)}<br>
        - OI : {int(most_traded_call_oi)}<br>
    - 📉 풋 옵션 행사가: ${most_traded_put_strike}<br>
        - Volume : {int(most_traded_put_volume)}<br>
        - OI : {int(most_traded_put_oi)}<br><br>

    📊 시장 심리 분석<br>
    - 🔄 Put/Call Ratio: {put_call_ratio:.2f}<br>
    - 🔄 IV Skew (Put - Call): {iv_skew:.2f}%<br>
    - 📌 실시간 변동성: {mean_iv:.1f}%<br><br>

    📈 신뢰도 분석<br>
    - 🧮 신뢰도 지수: {reliability_index} / 1.00<br>
    - 📘 해석: {reliability_msg}<br>
    """.strip()

    put_box_min = get_box_range_weighted(put_df, current_price, strike_distance_limit=0.3)
    call_box_max = get_box_range_weighted(call_df, current_price, strike_distance_limit=0.3)
    if put_box_min and call_box_max:
        report_text += f"<br><br>📦 시장 참여자 예상 박스권: ${put_box_min:.1f} ~ ${call_box_max:.1f}"

    return report_text

# get_expiry_dates 함수도 여기에 포함되어야 합니다.
@lru_cache(maxsize=32)
def get_expiry_dates(ticker):
    """옵션 만기일 목록을 가져옵니다."""
    # ( ... 기존 코드와 동일 ... )