# app.py

from flask import Flask, render_template, request, jsonify
from stock_logic import get_expiry_dates, fetch_options_data, parse_options_data

app = Flask(__name__)

# 1. 메인 페이지 라우트
@app.route('/')
def index():
    # index.html 템플릿을 렌더링합니다.
    return render_template('index.html')

# 2. 만기일 가져오기 API 라우트
@app.route('/get-expiry-dates')
def api_get_expiry_dates():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({'error': '티커를 입력해주세요.'}), 400
    
    dates = get_expiry_dates(ticker.upper())
    return jsonify(dates)

# 3. 분석 결과 페이지 라우트
@app.route('/report', methods=['POST'])
def report():
    ticker = request.form.get('ticker')
    expiry_date = request.form.get('expiry_date')

    if not ticker or not expiry_date:
        return "티커와 만기일을 모두 선택해야 합니다.", 400
    
    # 데이터 가져오기 및 분석
    try:
        options_data = fetch_options_data(ticker.upper(), expiry_date)
        if options_data is None:
            raise ValueError("옵션 데이터를 가져올 수 없습니다. 다른 만기일을 선택하세요.")
            
        call_df, put_df, ticker_name = options_data
        analysis_report = parse_options_data(call_df, put_df, ticker_name)
        
        # 결과를 report.html 템플릿에 담아 렌더링
        return render_template('report.html', report_content=analysis_report)

    except Exception as e:
        error_message = f"분석 중 오류가 발생했습니다: {e}"
        # 오류 발생 시에도 report.html을 사용해 일관된 UI로 오류 메시지 표시
        return render_template('report.html', report_content=error_message)

if __name__ == '__main__':
    app.run(debug=True)