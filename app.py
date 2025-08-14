from flask import Flask, render_template, request, jsonify
from stock_logic import get_expiry_dates, analyze_data_for_visualization
import pandas as pd

app = Flask(__name__)

# 초기 화면 - 종목 검색
@app.route('/')
def index():
    return render_template('index.html')

# 사용자가 티커를 입력하면 만기일 목록을 동적으로 가져오는 API
@app.route('/get-expiries')
def get_expiries_api():
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return jsonify({"error": "티커를 입력하세요."}), 400
    
    dates = get_expiry_dates(ticker)
    if not dates:
        return jsonify({"error": "유효한 만기일을 찾을 수 없습니다."}), 404
        
    return jsonify(dates)

# 분석 리포트를 생성하고 보여주는 메인 라우트
@app.route('/report', methods=['POST'])
def report():
    ticker = request.form.get('ticker', '').upper()
    expiry_date = request.form.get('expiry_date')

    if not ticker or not expiry_date:
        return "오류: 티커와 만기일을 모두 올바르게 선택해야 합니다.", 400

    # stock_logic에서 구조화된 데이터 받아오기
    viz_data = analyze_data_for_visualization(ticker, expiry_date)

    if viz_data.get("error"):
        return f"분석 중 오류 발생: {viz_data['error']}", 500

    # report.html에 데이터 전체를 전달
    return render_template('report.html', data=viz_data)

if __name__ == '__main__':
    app.run(debug=True)