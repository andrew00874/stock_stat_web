
# 📈 Stock Option Analysis - 옵션 데이터 분석기

---

## 🧩 주요 기능

- ✅ 콜/풋 옵션 체인 자동 수집 (`requests`, `pandas.read_html`)
- ✅ 옵션 만기일 자동 탐지 (재시도 로직 포함)
- ✅ 심리 분석 지표 계산:
  - Put/Call Volume Ratio
  - IV Skew (ATM 기준)
  - 평균 IV 및 스프레드
  - Open Interest 및 거래량 집중도
  - ATM 옵션 집중도 분석
- ✅ 전략 추천 엔진 (다단계 조건 기반)
- ✅ 신뢰도 지수 계산 (Volume, OI, ATM 비중, 만기일 기준)
- ✅ 시장 박스권 예측 (OI 누적 + 가중치 기반)

---

## 🖥 실행 방법

https://stock-stat-web.vercel.app/

## 🔧 기술 설명

### ▶ 만기일 가져오기 (`yfinance`) 개선

```python
@lru_cache
def get_expiry_dates(ticker):
    for attempt in range(3):
        try:
            return yf.Ticker(ticker).options
        except Exception:
            time.sleep(2)
```

- 재시도 및 시간 딜레이 포함
- 빈 리스트 반환 시 에러 메시지 출력

### ▶ 옵션 데이터 수집 (`requests` + `read_html`)

```python
def fetch_options_data(ticker, expiry_timestamp):
    url = f"https://finance.yahoo.com/quote/{ticker}/options?date={expiry_timestamp}"
    tables = pd.read_html(StringIO(requests.get(url).text))
    return tables[0], tables[1]
```

### ▶ 심리 지표 계산 및 전략 판단

- Put/Call 비율
- IV Skew 및 평균 IV
- ATM 기준 집중도
- 가장 많이 거래된 행사가 분석
- 박스권(가중치 기반) 및 Open Interest 누적범위 추정
- 전략 조건 예:
  ```python
  if bullish_sentiment and not high_iv and iv_skew < -2:
      strategy = "🚀 매우 강한 매수 신호"
  ```

### ▶ 신뢰도 지수 계산 로직

```python
reliability_index = (
    volume_score * 0.3 +
    oi_score * 0.3 +
    atm_score * 0.2 +
    time_score * 0.2
)
```

- Volume, OI, ATM 집중도, 만기일 등 4가지 축 종합 평가

```
