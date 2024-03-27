# pyinstaller --onefile --noconsole --hidden-import=numpy run_autotrade.py


0. 프로그램 설명

1) 프로그램의 autotrade 실행 버튼을 누르게 되면 프로그램이 켜져있는 동안 1시간에 한번 gpt의 판단하에 업비트에서 사용자가 지정한 가상화폐에 대해 buy, sell, hold를 gpt의 확신도에 따라 10 ~ 100%의 비율로 매수 매도 주문을 수행하게 되며 수행된 결과는 텔레그램으로 전달받게 됨
2) 1회 최대 매수금액은 지정 가능함
3) 매수 이후 홀딩했을 때 대비 손익액의 파악이 가능함

※ 프로그램이 실행되는 동안 컴퓨터를 계속 켜놓는게 부담스러울 경우 클라우드상에서 24시간 실행도 가능(문의바람)

1. 사전준비

1) openai api key 발급 방법
https://newjerry.tistory.com/entry/4-Open-AI-%EC%B9%B4%EB%93%9C-%EB%93%B1%EB%A1%9D-%EB%B0%8F-API-%ED%82%A4-%EB%B0%9C%EA%B8%89

2) 업비트 api key 및 secret key 발급 방법
https://technfin.tistory.com/entry/%EC%97%85%EB%B9%84%ED%8A%B8-%EC%9E%90%EB%8F%99%EB%A7%A4%EB%A7%A4-API-KEY-%EB%B0%9C%EA%B8%89%EB%B0%9B%EA%B8%B0
2-1) 업비트 개인 ip 등록
https://ipaddress.my/?lang=ko

3) telegram 봇생성 + api key 및 chat id 발급 방법
https://tblog.rudi2e.com/27


2. 환경변수 설명

OPENAI_API_KEY: 오픈ai api 키
UPBIT_ACCESS_KEY: 업비트 엑세스 키
UPBIT_SECRET_KEY: 업비트 시크릿 키
TELEGRAM_API_KEY: 텔레그램 api 키
TELEGRAM_CHAT_ID: 텔레그램 chat id
TRADING_PAIR: 거래할 화폐 선택(ex : KRW-BTC)
INIT_VOLUME: 거래할 화폐의 초기 보유 수량(현재 보유원화로 최대 매수했을 때의 화폐 수량, 본 프로그램은 초기 수량으로 홀딩했을 때와 gpt를 이용해 자동 매매 했을때 손익액을 비교하기 때문에 필요한 값)
MAX_KRW_BUY_AMOUNT: 1회 최대 매수 금액(ex : 1000000, ex2 : max)

3. 실행방법

1) 환경 변수 설정을 눌러 모든 변수를 입력 or .env파일을 메모장으로 열어서 필요한 값을 입력(처음 1번만 입력하면 됨)
2) 최대 매수 금액 설정 (환경변수 설정에서 입력했으면 입력할 필요 없으나 변경이 필요할 경우 해당 버튼 사용)
3) 거래 통화 변경(ex : KRW-BTC, 환경변수 설정에서 입력했으면 입력할 필요 없으나 변경이 필요할 경우 해당 버튼 사용)
4) autotrade 실행(프로그램이 실행 중일때 1시간에 한번 동작이 실행됨)
5) 종료
