import os
from dotenv import load_dotenv
load_dotenv()
import pyupbit
import pandas as pd
import pandas_ta as ta
import json
from openai import OpenAI
import schedule
import time
import asyncio
import telegram
from datetime import datetime

# 전역 변수로 거래 정보를 저장
trade_info = {}
INIT_VOLUME =  2298402227.5 # 초기 보유량

# Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))

# 현재 상태 가져오기 함수
def get_current_status():
    orderbook = pyupbit.get_orderbook(ticker="KRW-BTT")
    balances = upbit.get_balances()
    btt_balance = next((item for item in balances if item['currency'] == 'BTT'), {}).get('balance', 0)
    krw_balance = next((item for item in balances if item['currency'] == 'KRW'), {}).get('balance', 0)
    btt_avg_buy_price = next((item for item in balances if item['currency'] == 'BTT'), {}).get('avg_buy_price', 0)

    return {
        'current_time': orderbook['timestamp'],
        'btt_balance': btt_balance,
        'krw_balance': krw_balance,
        'btt_avg_buy_price': btt_avg_buy_price
    }

# 데이터 가져오기 및 준비 함수
def fetch_and_prepare_data():
    # Fetch data
    df_daily = pyupbit.get_ohlcv("KRW-BTT", "day", count=30)
    df_hourly = pyupbit.get_ohlcv("KRW-BTT", interval="minute60", count=24)

    # 여기에서 DataFrame을 JSON 문자열로 변환하는 코드는 제거
    return df_daily, df_hourly

# 파일에서 지시사항을 가져오는 함수
def get_instructions(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            instructions = file.read()
        return instructions
    except FileNotFoundError:
        print("File not found.")
    except Exception as e:
        print("An error occurred while reading the file:", e)

# GPT-4를 사용하여 데이터 분석        
def analyze_data_with_gpt4(data):
    instructions_path = "instructions.md"
    try:
        instructions = get_instructions(instructions_path)
        if not instructions:
            return None

        current_status = get_current_status()
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(data)}, # Python 객체를 JSON 문자열로 변환
                {"role": "user", "content": json.dumps(current_status)} # 여기도 마찬가지
            ],
            response_format={"type":"json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in analyzing data with GPT-4: {e}")
        return None

# 매수 함수
def execute_buy(buy_percentage=1.0):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        krw_balance = upbit.get_balance("KRW")  # KRW 잔고 조회
        buy_amount = krw_balance * buy_percentage  # 매수 금액 계산
        if buy_amount > 5000:  # 최소 거래 금액 조건 확인
            result = upbit.buy_market_order("KRW-BTT", buy_amount * 0.9995)  # 수수료 고려하여 매수 실행
            print(f"{current_time} - Buy order successful:", result)
            return result
    except Exception as e:
        print(f"{current_time} - Failed to execute buy order: {e}")
        return None

# 매도 함수
def execute_sell(sell_percentage=1.0):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        btt_balance = upbit.get_balance("BTT")  # BTT 보유 수량 조회
        sell_quantity = btt_balance * sell_percentage  # 매도 수량 계산
        if sell_quantity > 0.0001:  # 최소 거래 수량 조건 확인
            result = upbit.sell_market_order("KRW-BTT", sell_quantity)  # 매도 실행
            print(f"{current_time} - Sell order successful:", result)
            return result
    except Exception as e:
        print(f"{current_time} - Failed to execute sell order: {e}")
        return None

# 텔레그램 메시지 전송 함수
async def send_telegram_message(message):
    token = os.getenv('TELEGRAM_API_KEY')
    bot = telegram.Bot(token)
    await bot.send_message(chat_id=os.getenv('TELEGRAM_CHAT_ID'), text=message)

# 거래 결과 처리 함수
def process_trade_result(result, df_hourly, current_status):
    currency_name = result['market']  # 거래 대상 암호화폐
    trade_time = result['created_at']  # 거래 시간
    current_price = df_hourly['open'].iloc[-1]  # 현재 가격

    if result['side'] == 'bid':  # 매수일 경우
        locked_amount = float(result['locked'])  # 매수 금액
        trade_volume = locked_amount / current_price  # 매수 수량 계산
        trade_price = locked_amount  # 이미 매수 금액이므로 그대로 사용
    else:  # 매도일 경우
        trade_volume = float(result['volume'])  # 매도 수량
        trade_price = trade_volume * current_price  # 매도 금액 계산

    # 현재 BTT 보유량과 KRW 잔액을 current_status에서 추출
    btt_balance = float(current_status['btt_balance']) + (trade_volume if result['side'] == 'bid' else -trade_volume)
    krw_balance = float(current_status['krw_balance']) + (-trade_price if result['side'] == 'bid' else trade_price)

    current_total_value = btt_balance * current_price + krw_balance  # 현재 보유 총액 계산
    hold_price = INIT_VOLUME * current_price  # 홀딩했을 때의 원금 계산
    profit_or_loss = current_total_value - hold_price  # 홀딩 대비 손익액 계산

    return {
        "currency_name": currency_name,
        "trade_time": trade_time,
        "trade_volume": trade_volume,
        "trade_price": trade_price,
        "hold_price": hold_price,
        "current_total_value": current_total_value,
        "profit_or_loss": profit_or_loss
    }

# 결정 및 실행 함수
async def make_decision_and_execute():
    df_daily, df_hourly = fetch_and_prepare_data()
    if df_daily is None or df_hourly is None:
        print("데이터 가져오기 실패. 종료합니다.")
        return

    data_json = {
        "daily": json.loads(df_daily.to_json(orient='split')),
        "hourly": json.loads(df_hourly.to_json(orient='split'))
    }

    advice = analyze_data_with_gpt4(data_json)
    if not advice:
        print("데이터 분석 실패. 종료합니다.")
        return

    decision = json.loads(advice)
    await send_telegram_message(json.dumps(decision, indent=2, ensure_ascii=False))

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # current_time을 여기로 이동

    if decision.get('decision') in ["buy", "sell"]:
        percentage = decision.get('percentage', 1.0)  # 결정된 비율을 사용
        # buy 혹은 sell 함수 호출
        result = execute_buy(percentage) if decision['decision'] == "buy" else execute_sell(percentage)
        
        if result and 'error' not in result:
            current_status = get_current_status()  # 현재 상태 정보를 가져옴
            trade_result = process_trade_result(result, df_hourly, current_status)  # 수정된 함수 호출

            result_message = f"{current_time}\n" \
                             "※ 거래 결과\n" \
                             f"거래 화폐명: {trade_result['currency_name']}\n" \
                             f"거래 시간: {trade_result['trade_time']}\n" \
                             f"거래한 수량: {trade_result['trade_volume']:.2f}\n" \
                             f"거래 금액: {trade_result['trade_price']:.2f}\n" \
                             f"홀딩 했을 때 원금: {trade_result['hold_price']:.2f}\n" \
                             f"현재 보유 총액: {trade_result['current_total_value']:.2f}\n" \
                             f"홀딩 대비 손익액: {trade_result['profit_or_loss']:.2f}"
            print(result_message)
            await send_telegram_message(result_message)
        else:
            fail_message = f"{current_time} 거래 실패: {result.get('error', '알 수 없는 오류')}"
            print(fail_message)
            await send_telegram_message(fail_message)

    elif decision.get('decision') == "hold":
        btt_balance = 0
        krw_balance = 0
        btt_avg_buy_price = 0

        df_daily, df_hourly = fetch_and_prepare_data()
        current_price = df_hourly['open'].iloc[-1]  # 현재 가격
        hold_value = current_price * INIT_VOLUME


        btt_balance = float(get_current_status()['btt_balance'])
        krw_balance = float(get_current_status()['krw_balance'])
        btt_avg_buy_price = float(get_current_status()['btt_avg_buy_price'])
        current_value = (btt_balance * btt_avg_buy_price) + krw_balance

        profit_value = current_value - hold_value        
        hold_message =  f"{current_time}\n" \
                "※ 분석 결과: 홀딩합니다.\n" \
                f"홀딩 했을 때 원금: {hold_value}\n" \
                f"현재 보유 총액: {current_value}\n" \
                f"현재 대비 손익액: {profit_value}\n"
        print(hold_message)
        await send_telegram_message(hold_message)

# 메인 함수
async def main():
    await make_decision_and_execute()
    # 이벤트 루프를 가져오고, 주기적으로 실행할 작업을 스케줄링합니다.
    loop = asyncio.get_running_loop()

    def schedule_job():
        loop.call_soon_threadsafe(schedule.run_pending)

    # 매 4시간마다 1분에 make_decision_and_execute() 코루틴을 실행합니다.
    schedule.every().hours.at(":01").do(lambda: asyncio.create_task(make_decision_and_execute()))


    # 스케줄러가 주기적으로 실행될 수 있도록 무한 루프를 설정합니다.
    while True:
        await asyncio.sleep(1)  # 현재 실행 중인 이벤트 루프를 블록하지 않습니다.
        schedule_job()

if __name__ == "__main__":
    asyncio.run(main())
