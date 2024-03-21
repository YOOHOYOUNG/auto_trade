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

# Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))

def get_current_status():
    orderbook = pyupbit.get_orderbook(ticker="KRW-BTT")
    current_time = orderbook['timestamp']
    btt_balance = 0
    krw_balance = 0
    btt_avg_buy_price = 0
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == "BTT":
            btt_balance = b['balance']
            btt_avg_buy_price = b['avg_buy_price']
        if b['currency'] == "KRW":
            krw_balance = b['balance']

    current_status = {'current_time': current_time, 'orderbook': orderbook, 'btt_balance': btt_balance, 'krw_balance': krw_balance, 'btt_avg_buy_price': btt_avg_buy_price}
    return json.dumps(current_status)


def fetch_and_prepare_data():
    # Fetch data
    df_daily = pyupbit.get_ohlcv("KRW-BTT", "day", count=30)
    df_hourly = pyupbit.get_ohlcv("KRW-BTT", interval="minute60", count=24)

    # Define a helper function to add indicators
    def add_indicators(df):
        # Moving Averages
        df['SMA_10'] = ta.sma(df['close'], length=10)
        df['EMA_10'] = ta.ema(df['close'], length=10)

        # RSI
        df['RSI_14'] = ta.rsi(df['close'], length=14)

        # Stochastic Oscillator
        stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
        df = df.join(stoch)

        # MACD
        ema_fast = df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']

        # Bollinger Bands
        df['Middle_Band'] = df['close'].rolling(window=20).mean()
        # Calculate the standard deviation of closing prices over the last 20 days
        std_dev = df['close'].rolling(window=20).std()
        # Calculate the upper band (Middle Band + 2 * Standard Deviation)
        df['Upper_Band'] = df['Middle_Band'] + (std_dev * 2)
        # Calculate the lower band (Middle Band - 2 * Standard Deviation)
        df['Lower_Band'] = df['Middle_Band'] - (std_dev * 2)

        return df

    # Add indicators to both dataframes
    df_daily = add_indicators(df_daily)
    df_hourly = add_indicators(df_hourly)

    combined_df = pd.concat([df_daily, df_hourly], keys=['daily', 'hourly'])
    combined_data = combined_df.to_json(orient='split')

    # make combined data as string and print length
    print(len(combined_data))

    return json.dumps(combined_data)

def get_instructions(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            instructions = file.read()
        return instructions
    except FileNotFoundError:
        print("File not found.")
    except Exception as e:
        print("An error occurred while reading the file:", e)

def analyze_data_with_gpt4(data_json):
    instructions_path = "instructions.md"
    try:
        instructions = get_instructions(instructions_path)
        if not instructions:
            print("No instructions found.")
            return None

        current_status = get_current_status()
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": data_json},
                {"role": "user", "content": current_status}
            ],
            response_format={"type":"json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in analyzing data with GPT-4: {e}")
        return None

def execute_buy():
    print("Attempting to buy BTT...")
    try:
        krw = upbit.get_balance("KRW")
        if krw > 5000:
            result = upbit.buy_market_order("KRW-BTT", krw*0.9995)
            print("Buy order successful:", result)
    except Exception as e:
        print(f"Failed to execute buy order: {e}")

def execute_sell():
    print("Attempting to sell BTT...")
    try:
        btt = upbit.get_balance("BTT")
        current_price = pyupbit.get_orderbook(ticker="KRW-BTT")['orderbook_units'][0]["ask_price"]
        if current_price*btt > 5000:
            result = upbit.sell_market_order("KRW-BTT", btt)
            print("Sell order successful:", result)
    except Exception as e:
        print(f"Failed to execute sell order: {e}")

def make_decision_and_execute():
    print("Making decision and executing...")
    data_json = fetch_and_prepare_data()
    advice = analyze_data_with_gpt4(data_json)

    try:
        decision = json.loads(advice)
        print(decision)
        # 딕셔너리를 보기 좋은 문자열로 변환
        pretty_advice = json.dumps(decision, indent=2, ensure_ascii=False)
        
        async def main():
            token = os.getenv('TELEGRAM_API_KEY')
            bot = telegram.Bot(token)
            await bot.send_message(chat_id=os.getenv('TELEGRAM_CHAT_ID'), text=pretty_advice)

        # 현재 실행 중인 이벤트 루프를 얻습니다.
        loop = asyncio.get_event_loop()

        # 이벤트 루프가 실행 중이지 않은 경우 main() 코루틴을 실행합니다.
        if not loop.is_running():
            loop.run_until_complete(main())
        else:
            # 이미 실행 중인 이벤트 루프에 main() 코루틴을 스케줄링합니다.
            asyncio.create_task(main())
        
        if decision.get('decision') == "buy":
            execute_buy()
        elif decision.get('decision') == "sell":
            execute_sell()
    except Exception as e:
        print(f"Failed to parse the advice as JSON: {e}")

if __name__ == "__main__":
    make_decision_and_execute()
    schedule.every().hour.at(":01").do(make_decision_and_execute)

    while True:
        schedule.run_pending()
        time.sleep(1)
