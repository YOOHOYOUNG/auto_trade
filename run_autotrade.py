# 환경변수 입력 버튼 누른 이후 입력하면 value가 덮어쓰기 안되고 밑에 새로 key value가 써지는 이슈

import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import os
import threading
import queue
import autotrade
import asyncio

# 기존 환경 변수 키들을 정의합니다.
env_keys = ["OPENAI_API_KEY", "UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "TELEGRAM_API_KEY", "TELEGRAM_CHAT_ID", "TRADING_PAIR", "INIT_VOLUME", "MAX_KRW_BUY_AMOUNT"]
env_vars = {}  # 환경 변수를 저장할 딕셔너리

def update_env_display():
    """UI의 환경 변수 표시를 업데이트합니다."""
    env_display.config(state=tk.NORMAL)
    env_display.delete('1.0', tk.END)
    for key, value in env_vars.items():
        env_display.insert(tk.END, f"{key}: {value}\n")
    env_display.config(state=tk.DISABLED)

def load_env_variables():
    """'.env' 파일에서 환경 변수를 로드하고 UI를 업데이트합니다."""
    env_vars.clear()
    if os.path.exists('.env'):
        with open('.env', 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#") and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value.strip('"').strip("'")

    update_env_display()

def validate_and_set_env_var(key, value):
    """환경 변수의 값 유효성을 검사하고 설정합니다."""
    if key == "TRADING_PAIR" and not value.startswith("KRW-"):
        messagebox.showerror("오류", "TRADING_PAIR는 'KRW-'로 시작해야 합니다.")
        return False
    if key in ["OPENAI_API_KEY", "UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", 
               "TELEGRAM_API_KEY", "TELEGRAM_CHAT_ID", "TRADING_PAIR"]:
        env_vars[key] = value  # 문자열 필드
    elif key == "INIT_VOLUME":
        try:
            env_vars[key] = float(value)
        except ValueError:
            messagebox.showerror("오류", "INIT_VOLUME은 숫자여야 합니다.")
            return False
    elif key == "MAX_KRW_BUY_AMOUNT":
        if value.lower() == "max" or value.isdigit():
            env_vars[key] = value.lower() if value.lower() == "max" else int(value)
        else:
            messagebox.showerror("오류", "MAX_KRW_BUY_AMOUNT는 숫자 또는 'max'여야 합니다.")
            return False
    return True


def set_env_variable(key):
    """사용자 입력을 통해 단일 환경 변수를 설정합니다."""
    while True:
        value = simpledialog.askstring("환경 변수 입력", f"{key} 값을 입력하세요:", parent=app)
        if value is None:
            messagebox.showwarning("경고", "입력이 취소되었습니다.")
            return  # 입력 취소 시 함수를 종료합니다.
        
        # 값 유효성 검사
        if validate_and_set_env_var(key, value):
            break  # 유효한 값이 입력되면 반복을 종료합니다.
    
    update_env_file()  # .env 파일 업데이트
    load_env_variables()  # 환경변수 다시 로드하여 UI 업데이트

def update_env_file():
    """'.env' 파일을 현재의 환경 변수 상태로 업데이트합니다."""
    with open('.env', 'w') as file:
        for key in env_keys:  # 기존에 정의된 키에 대해서만 처리
            if key in env_vars:
                value = env_vars[key]
                # INIT_VOLUME 처리: 입력된 값을 실수로 변환하여 저장합니다.
                if key == "INIT_VOLUME":
                    try:
                        # value를 실수로 변환을 시도합니다. 실패할 경우 원래 값을 유지합니다.
                        numeric_value = float(value)
                        file.write(f"{key}={numeric_value}\n")
                    except ValueError:
                        # 형변환 실패 시, 입력 값이 유효하지 않음을 나타냅니다. 오류 처리를 해야 할 수 있습니다.
                        print(f"Warning: {key} has an invalid value '{value}'. It must be a number.")
                # MAX_KRW_BUY_AMOUNT가 "max"인 경우, 문자열 "max"로 저장합니다.
                elif key == "MAX_KRW_BUY_AMOUNT" and str(value).lower() == "max":
                    file.write(f'{key}="max"\n')
                # 문자열 값은 따옴표로 감싸서 저장합니다.
                elif isinstance(value, str):
                    file.write(f'{key}="{value}"\n')
                # 그 외의 경우 (숫자 등), 값을 그대로 저장합니다.
                else:
                    file.write(f"{key}={value}\n")

                
def set_env_variables():
    """사용자에게 모든 환경 변수의 값을 입력받아 설정합니다."""
    for key in env_keys:
        set_env_variable(key)

def set_max_buy_amount():
    """최대 매수 가능 금액을 설정합니다."""
    max_buy_amount = simpledialog.askstring("최대 매수 가능 금액 설정", "MAX_KRW_BUY_AMOUNT 값을 입력하세요 (숫자 또는 'max'):", parent=app)
    if max_buy_amount:
        env_vars["MAX_KRW_BUY_AMOUNT"] = max_buy_amount
        update_env_file()
        load_env_variables()
    else:
        messagebox.showwarning("경고", "최대 매수 가능 금액 설정이 취소되었습니다.", parent=app)

def change_trading_pair():
    """거래 통화 쌍을 변경하고 '.env' 파일을 업데이트합니다."""
    trading_pair = simpledialog.askstring("거래 통화 변경", "TRADING_PAIR 값을 입력하세요 ex)KRW-BTC", parent=app)
    if trading_pair:
        env_vars["TRADING_PAIR"] = trading_pair
        update_env_file()
        load_env_variables()
    else:
        messagebox.showwarning("경고", "거래 통화 변경이 취소되었습니다.", parent=app)

def enqueue_output(out, queue):
    for line in iter(out.readline, ''):
        queue.put(line)
    out.close()



def update_output_display(output_display, queue):
    while not queue.empty():
        line = queue.get_nowait()
        output_display.insert(tk.END, line)
        output_display.see(tk.END)
    output_display.after(100, update_output_display, output_display, queue)

last_read_position = 0  # 전역 변수로, 마지막으로 읽은 파일 위치를 저장

def update_output_display_from_file(output_display, file_path):
    global last_read_position
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            file.seek(last_read_position)  # 마지막으로 읽은 위치로 이동
            new_logs = file.read()  # 새로운 로그 읽기
            if new_logs:  # 새로운 로그가 있으면 UI에 추가
                output_display.insert(tk.END, new_logs)
                output_display.see(tk.END)  # 스크롤 자동 조정
            last_read_position = file.tell()  # 마지막으로 읽은 위치 업데이트
    except FileNotFoundError:
        output_display.insert(tk.END, "로그 파일을 찾을 수 없습니다.\n")
    except Exception as e:
        output_display.insert(tk.END, f"파일 읽기 오류: {e}\n")
    # 주기적으로 함수 호출을 계속한다.
    output_display.after(1000, lambda: update_output_display_from_file(output_display, file_path))


# autotrade.py 스크립트의 출력을 실시간으로 읽어서 UI에 표시하는 함수
def read_and_display_output(process, output_display):
    """
    subprocess의 출력을 읽어서 tkinter의 Text 위젯에 실시간으로 출력합니다.
    process: subprocess.Popen 객체
    output_display: tkinter의 Text 위젯 객체
    """
    for line in iter(process.stdout.readline, ''):
        output_display.insert(tk.END, line)
        output_display.see(tk.END)
    process.stdout.close()
    process.wait()  # autotrade.py의 실행이 끝날 때까지 기다립니다.


def run_autotrade_async():
    """
    autotrade.py의 비동기 함수를 실행하는 함수.
    비동기 이벤트 루프를 생성하고, autotrade.py의 main 함수를 실행합니다.
    """
    asyncio.run(autotrade.main())

def run_autotrade(output_display):
    global last_read_position
    # 로그 파일의 현재 크기를 last_read_position에 저장
    log_file_path = "autotrade_log.txt"
    try:
        with open(log_file_path, "r", encoding="utf-8") as file:
            file.seek(0, os.SEEK_END)  # 파일의 끝으로 이동
            last_read_position = file.tell()  # 현재 위치(파일 크기) 저장
    except FileNotFoundError:
        output_display.insert(tk.END, "로그 파일을 초기화 중 에러 발생.\n")
        last_read_position = 0  # 파일이 없는 경우, 0으로 초기화
    
    threading.Thread(target=run_autotrade_async, daemon=True).start()
    update_output_display_from_file(output_display, log_file_path)

def run_autotrade_thread(output_display):
    """
    autotrade 실행 함수를 별도의 스레드에서 실행합니다.
    이 함수는 output_display를 매개변수로 받아 실제 autotrade 실행 로직을 수행합니다.
    """
    run_autotrade(output_display)

def quit_program():
    app.quit()

app = tk.Tk()
app.title("HY-Autotrade Beta v1.0 (제작자 : 유호영)")
app.geometry("590x650")

# 여기에 'INIT_VOLUME', 'MAX_KRW_BUY_AMOUNT' 추가
env_keys = ["OPENAI_API_KEY", "UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "TELEGRAM_API_KEY", "TELEGRAM_CHAT_ID", "TRADING_PAIR", "INIT_VOLUME", "MAX_KRW_BUY_AMOUNT"]
env_vars = {}

env_display = scrolledtext.ScrolledText(app, height=8, state=tk.DISABLED)
env_display.pack(pady=5)


output_display = scrolledtext.ScrolledText(app, height=20)
output_display.pack(pady=5)

# Queue 초기화
queue = queue.Queue()

set_env_button = tk.Button(app, text="환경 변수 설정", command=set_env_variables, width=20, height=2)
set_env_button.pack(pady=5, side=tk.TOP)

max_buy_amount_button = tk.Button(app, text="최대 매수 금액 설정", command=set_max_buy_amount, width=20, height=2)
max_buy_amount_button.pack(pady=5, side=tk.TOP)

change_pair_button = tk.Button(app, text="거래 통화 변경", command=change_trading_pair, width=20, height=2)
change_pair_button.pack(pady=5, side=tk.TOP)

# 실행 버튼
run_button = tk.Button(app, text="Autotrade 실행", command=lambda: run_autotrade_thread(output_display), width=20, height=2)
run_button.pack(pady=5, side=tk.TOP)

quit_button = tk.Button(app, text="종료", command=quit_program, width=20, height=2)
quit_button.pack(pady=5, side=tk.BOTTOM)

# 환경변수 및 실행 출력창 초기화
load_env_variables()

app.mainloop()