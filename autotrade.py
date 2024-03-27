import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
import pyupbit
import pandas as pd
import pandas_ta as ta
import json
from openai import OpenAI
import schedule
# import time
import asyncio
import telegram
from datetime import datetime

# 전역 변수로 거래 정보를 저장
INIT_VOLUME = float(os.getenv("INIT_VOLUME"))  # .env에서 무조건 받아오기, 설정되지 않으면 에러 발생
MAX_KRW_BUY_AMOUNT_ENV = os.getenv("MAX_KRW_BUY_AMOUNT")  # "max" 또는 숫자 값

# 로그 파일 경로 설정
LOG_FILE_PATH = "autotrade_log.txt"

# MAX_KRW_BUY_AMOUNT 값이 "max"인지 확인하거나 숫자로 변환
if MAX_KRW_BUY_AMOUNT_ENV is None:
    raise ValueError("MAX_KRW_BUY_AMOUNT must be set in the .env file.")

if MAX_KRW_BUY_AMOUNT_ENV.lower() == "max":
    MAX_KRW_BUY_AMOUNT = "max"
else:
    try:
        MAX_KRW_BUY_AMOUNT = float(MAX_KRW_BUY_AMOUNT_ENV)
    except ValueError:
        raise ValueError("MAX_KRW_BUY_AMOUNT must be a number or 'max'.")


def log_to_file(message, print_to_console=False):
    """로그 메시지를 파일에 기록하고, 선택적으로 콘솔에도 출력합니다."""
    with open(LOG_FILE_PATH, "a", encoding='utf-8') as log_file:
        log_file.write(f"{message}\n\n")  # 메시지를 파일에 기록
    if print_to_console:
        print(message)  # 선택적으로 콘솔에도 메시지를 출력합니다.


# Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
ticker = os.getenv("TRADING_PAIR")
currency = ticker.split("-")[1]



# 현재 상태 가져오기 함수
def get_current_status():
    orderbook = pyupbit.get_orderbook(ticker=ticker)
    balances = upbit.get_balances()
    currency_balance = next((item for item in balances if item['currency'] == currency), {}).get('balance', 0)
    krw_balance = next((item for item in balances if item['currency'] == 'KRW'), {}).get('balance', 0)
    currency_avg_buy_price = next((item for item in balances if item['currency'] == currency), {}).get('avg_buy_price', 0)

    return {
        'current_time': orderbook['timestamp'],
        'currency_balance': currency_balance,
        'krw_balance': krw_balance,
        'currency_avg_buy_price': currency_avg_buy_price
    }

# 데이터 가져오기 및 준비 함수
def fetch_and_prepare_data():
    # Fetch data
    df_daily = pyupbit.get_ohlcv(ticker, "day", count=30)
    df_hourly = pyupbit.get_ohlcv(ticker, interval="minute60", count=24)

    # 여기에서 DataFrame을 JSON 문자열로 변환하는 코드는 제거
    return df_daily, df_hourly

# 파일에서 지시사항을 가져오는 함수
def get_instructions(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            instructions = file.read()

        # 특정 키워드를 동적으로 대체합니다.
        instructions = instructions.replace("BTT", currency.upper())
        instructions = instructions.replace("btt", currency.lower())

        return instructions
    except FileNotFoundError:
        log_to_file("File not found.", print_to_console=True)
    except Exception as e:
        log_to_file(f"An error occurred while reading the file: {e}", print_to_console=True)

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
        log_to_file(f"Error in analyzing data with GPT-4: {e}")
        return None
    
def execute_buy(buy_percentage=1.0):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        krw_balance = upbit.get_balance("KRW")
        buy_amount = krw_balance if MAX_KRW_BUY_AMOUNT == "max" else min(krw_balance * buy_percentage, MAX_KRW_BUY_AMOUNT)
        if buy_amount > 5000:
            result = upbit.buy_market_order(ticker, buy_amount * 0.9995)
            if 'error' not in result:
                log_message = f"{current_time} - Buy order successful: {json.dumps(result)}"
                log_to_file(log_message,print_to_console=True)
                return result
            else:
                raise Exception(result['error'])
        else:
            raise Exception("Insufficient KRW balance or amount less than minimum trade size")
    except Exception as e:
        log_message = f"{current_time} - Failed to execute buy order: {e}"
        log_to_file(log_message,print_to_console=True)
        return None

def execute_sell(sell_percentage=1.0):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        currency_balance = upbit.get_balance(currency)
        sell_quantity = currency_balance * sell_percentage
        if sell_quantity > 0.0001:
            result = upbit.sell_market_order(ticker, sell_quantity)
            if 'error' not in result:
                log_message = f"{current_time} - Sell order successful: {json.dumps(result)}"
                log_to_file(log_message,print_to_console=True)
                return result
            else:
                raise Exception(result['error'])
        else:
            raise Exception("Insufficient currency balance or amount less than minimum trade size")
    except Exception as e:
        log_message = f"{current_time} - Failed to execute sell order: {e}"
        log_to_file(log_message,print_to_console=True)
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

    # 현재 currency 보유량과 KRW 잔액을 current_status에서 추출
    currency_balance = float(current_status['currency_balance']) + (trade_volume if result['side'] == 'bid' else -trade_volume)
    krw_balance = float(current_status['krw_balance']) + (-trade_price if result['side'] == 'bid' else trade_price)

    current_total_value = currency_balance * current_price + krw_balance  # 현재 보유 총액 계산
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
    log_to_file( "make_decision_and_execute 함수 시작\n",print_to_console=True)   
    df_daily, df_hourly = fetch_and_prepare_data()
    if df_daily is None or df_hourly is None:
        log_to_file( "데이터 가져오기 실패. 종료합니다.",print_to_console=True)
        return

    data_json = {
        "daily": json.loads(df_daily.to_json(orient='split')),
        "hourly": json.loads(df_hourly.to_json(orient='split'))
    }

    advice = analyze_data_with_gpt4(data_json)
    if not advice:
        log_to_file( "데이터 분석 실패. 종료합니다.",print_to_console=True)
        return

    decision = json.loads(advice)
    log_to_file(f"분석 결과: {decision}",print_to_console=True)
    await send_telegram_message(json.dumps(decision, indent=2, ensure_ascii=False))

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if decision.get('decision') in ["buy", "sell"]:
        percentage = decision.get('percentage', 1.0)
        result = execute_buy(percentage) if decision['decision'] == "buy" else execute_sell(percentage)
        
        if result and 'error' not in result:
            current_status = get_current_status()
            trade_result = process_trade_result(result, df_hourly, current_status)

            result_message = f"{current_time}\n" \
                             "※ 거래 결과\n" \
                             f"거래 화폐명: {trade_result['currency_name']}\n" \
                             f"거래 시간: {trade_result['trade_time']}\n" \
                             f"거래한 수량: {trade_result['trade_volume']:.2f}\n" \
                             f"거래 금액: {trade_result['trade_price']:.2f}\n" \
                             f"홀딩 했을 때 원금: {trade_result['hold_price']:.2f}\n" \
                             f"현재 보유 총액: {trade_result['current_total_value']:.2f}\n" \
                             f"홀딩 대비 손익액: {trade_result['profit_or_loss']:.2f}"
            log_to_file(result_message,print_to_console=True)
            await send_telegram_message(result_message)
        else:
            fail_message = f"{current_time} 거래 실패: 거래 명령 실행에 실패했습니다."
            log_to_file(fail_message,print_to_console=True)
            await send_telegram_message(fail_message)

    elif decision.get('decision') == "hold":
        currency_balance = 0
        krw_balance = 0
        currency_avg_buy_price = 0

        df_daily, df_hourly = fetch_and_prepare_data()
        current_price = df_hourly['open'].iloc[-1]  # 현재 가격
        hold_value = current_price * INIT_VOLUME

        currency_balance = float(get_current_status()['currency_balance'])
        krw_balance = float(get_current_status()['krw_balance'])
        currency_avg_buy_price = float(get_current_status()['currency_avg_buy_price'])
        current_value = (currency_balance * currency_avg_buy_price) + krw_balance

        profit_value = current_value - hold_value
        hold_message = f"{current_time}\n" \
                "※ 분석 결과: 홀딩합니다.\n" \
                f"홀딩 했을 때 원금: {hold_value:.2f}\n" \
                f"현재 보유 총액: {current_value:.2f}\n" \
                f"홀딩 대비 손익액: {profit_value:.2f}\n"
        log_to_file(hold_message,print_to_console=True)  # 로그 파일에 홀딩 관련 메시지 기록
        await send_telegram_message(hold_message)
        log_to_file( "make_decision_and_execute 함수 종료\n",print_to_console=True)

def run_autotrade_sync():
    """
    동기 방식으로 비동기 main 함수를 실행하는 래퍼 함수.
    이 함수는 config_ui.py에서 호출할 수 있습니다.
    """
    asyncio.run(main())

# 메인 함수
async def main():
    log_to_file( "#" * 50, print_to_console=True)
    time1 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_to_file( f"{time1}\nAutotrade.py 실행됨",print_to_console=True)
    log_to_file("비동기 main 함수 시작",print_to_console=True)
    await make_decision_and_execute()
    # 이벤트 루프를 가져오고, 주기적으로 실행할 작업을 스케줄링합니다.
    loop = asyncio.get_running_loop()
    # 현재 시간을 datetime 객체로 받음
    time2 = datetime.now()

    # 현재 시간에 1시간을 더함
    next_run_time = time2 + timedelta(hours=1)

    # 두 시간 모두를 문자열로 변환하여 출력
    log_to_file(f"{time2.strftime('%Y-%m-%d %H:%M:%S')} Autotrade.py 실행완료\n{next_run_time.strftime('%Y-%m-%d %H:%M:%S')}에 재실행 예정",print_to_console=True)
    log_to_file( "#" * 50,print_to_console=True)
    def schedule_job():
        loop.call_soon_threadsafe(schedule.run_pending)

    # 매 4시간마다 1분에 make_decision_and_execute() 코루틴을 실행합니다.
    schedule.every().hours.at(":01").do(lambda: asyncio.create_task(make_decision_and_execute()))


    # 스케줄러가 주기적으로 실행될 수 있도록 무한 루프를 설정합니다.
    while True:
        await asyncio.sleep(1)  # 현재 실행 중인 이벤트 루프를 블록하지 않습니다.
        schedule_job()

if __name__ == "__main__":
    run_autotrade_sync()
