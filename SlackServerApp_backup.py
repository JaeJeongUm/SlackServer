import config
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import slack_sdk
from flask import Flask, request, jsonify
from threading import Thread
import requests
import json
import os
import time
from dotenv import load_dotenv

# 환경 변수 로드 (.env 파일 사용)
load_dotenv(dotenv_path='config/.env')

# 환경 변수 확인 및 로드
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
RATER_CHANNEL = os.environ.get("RATER_CHANNEL")

# 환경 변수 디버깅
print("=== 환경 변수 확인 ===")
print(f"SLACK_BOT_TOKEN: {'설정됨' if SLACK_BOT_TOKEN else '❌ 없음'}")
print(f"SLACK_SIGNING_SECRET: {'설정됨' if SLACK_SIGNING_SECRET else '❌ 없음'}")
print(f"SLACK_APP_TOKEN: {'설정됨' if SLACK_APP_TOKEN else '❌ 없음'}")
print(f"RATER_CHANNEL: {RATER_CHANNEL if RATER_CHANNEL else '❌ 없음'}")
print("=====================")

# 필수 환경 변수 검증
if not SLACK_BOT_TOKEN:
    print("❌ SLACK_BOT_TOKEN이 설정되지 않았습니다!")
    print("config/.env 파일을 확인해주세요.")
    exit(1)

if not SLACK_SIGNING_SECRET:
    print("❌ SLACK_SIGNING_SECRET이 설정되지 않았습니다!")
    exit(1)

if not SLACK_APP_TOKEN:
    print("❌ SLACK_APP_TOKEN이 설정되지 않았습니다!")
    exit(1)

# Slack Client 역할
slack_client = slack_sdk.WebClient(token=SLACK_BOT_TOKEN)

# Slack Server 역할
slack_server = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET
)

# Flask 서버 초기화
flask_app = Flask(__name__)

# Flask 서버 상태 추적
flask_start_time = None

def line_feed():
    """라인피드 형식 반환"""
    return "\n*************************************************************************************************\n"

def warning_icon():
    """경고 아이콘 반환"""
    return ":alert:"
 
def warning_message_format(message):
    """장애 관제시 Slack Message 형식"""
    return line_feed() + warning_icon() + message + line_feed()

def send_message(channel_id, message_text):
    """Slack 메시지 전송"""
    try:
        if "정상" in message_text:
            response = slack_client.chat_postMessage(
                channel=channel_id,
                text=line_feed() + ":white_check_mark: 정상 동작 :white_check_mark:" + line_feed()
            )
        else:
            response = slack_client.chat_postMessage(
                channel=channel_id,
                text=warning_message_format(message_text)
            )

        if response.get("ok"):
            print("****************************************************************************")
            print("Slack Message 전송 성공!")
            print("****************************************************************************")
            return "success"
        else:
            print(f"Slack 전송 실패: {response.get('error')}")
            return "fail"
            
    except Exception as e:
        print(f"Slack 메시지 전송 중 오류: {e}")
        return "fail"

@flask_app.route('/detect', methods=['POST'])
def detect():
    """장애 감지 API 엔드포인트"""
    try:
        data = request.get_json()
        if not data or 'data' not in data:
            return {"status": "error", "message": "Invalid request data"}, 400
            
        answer = data['data']
        result = send_message(RATER_CHANNEL, answer)
        
        return {"status": result}
        
    except Exception as e:
        print(f"API 처리 중 오류: {e}")
        return {"status": "error", "message": str(e)}, 500

@flask_app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    uptime = int(time.time() - flask_start_time) if flask_start_time else 0
    return {
        "status": "healthy", 
        "message": "Flask server is running",
        "uptime_seconds": uptime,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def check_flask_health():
    """Flask 서버 상태 확인 함수"""
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            uptime_minutes = data.get('uptime_seconds', 0) // 60
            return {
                "status": "healthy",
                "uptime_minutes": uptime_minutes,
                "timestamp": data.get('timestamp', 'Unknown')
            }
        else:
            return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"status": "down", "error": "Connection refused - Flask 서버가 실행되지 않음"}
    except requests.exceptions.Timeout:
        return {"status": "timeout", "error": "응답 시간 초과"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

####################################################################################################
# Slack 메시지 핸들러
@slack_server.message("24x7 전환")
def handle_hello_message(message, say):
    """24x7 전환 메세지"""
    say("24x7으로 전환하시겠습니까? \n관리자의 승인이 필요합니다.\n\n관리자는 \"승인합니다.\"를 입력해 주세요.")

@slack_server.message("hello")
def handle_hello_message(message, say):
    """hello 메시지에 대한 응답"""
    say(f"Hey there <@{message['user']}>!")

@slack_server.message("ping")
def handle_ping_message(message, say):
    """ping 메시지에 대한 응답"""
    say("pong! 🏓")

@slack_server.message("status")
def handle_status_message(message, say):
    """상태 확인 메시지에 대한 응답"""
    say("서버가 정상 동작 중입니다! ✅")

@slack_server.message("health")
def handle_health_message(message, say):
    """Flask 서버 헬스 체크"""
    say("🔍 Flask 서버 상태를 확인 중...")
    
    health_status = check_flask_health()
    
    if health_status["status"] == "healthy":
        uptime_minutes = health_status.get("uptime_minutes", 0)
        timestamp = health_status.get("timestamp", "Unknown")
        
        say(f"""✅ **Flask 서버 상태: 정상**
            📊 가동 시간: {uptime_minutes}분
            🕐 마지막 확인: {timestamp}
            🌐 엔드포인트: http://localhost:5000""")
    
    elif health_status["status"] == "down":
        say(f"""❌ **Flask 서버 상태: 중단됨**
            🔥 오류: {health_status.get('error', 'Unknown error')}
            💡 Flask 서버를 다시 시작해주세요""")
    
    elif health_status["status"] == "timeout":
        say(f"""⏰ **Flask 서버 상태: 응답 지연**
            🔥 오류: {health_status.get('error', 'Unknown error')}
            💡 서버가 과부하 상태일 수 있습니다""")
    
    else:
        say(f"""⚠️ **Flask 서버 상태: 오류**
            🔥 오류: {health_status.get('error', 'Unknown error')}
            💡 서버 로그를 확인해주세요""")

@slack_server.message("flask")
def handle_flask_command(message, say):
    """Flask 관련 명령어 도움말"""
    help_text = """🤖 **Flask 서버 관리 명령어**

            📋 **사용 가능한 명령어:**
            • `health` - Flask 서버 상태 확인
            • `flask` - 이 도움말 표시
            • `status` - 전체 서버 상태
            • `ping` - 연결 테스트

            🔗 **Flask API 엔드포인트:**
            • POST `/detect` - 장애 감지 메시지 전송
            • GET `/health` - 헬스 체크

            💡 **사용법:** 채팅에서 위 명령어를 입력하세요!"""

    say(help_text)

@slack_server.message("help")
def handle_help_message(message, say):
    """도움말 메시지"""
    help_text = """🤖 **사용 가능한 명령어**

            📋 **기본 명령어:**
            • `hello` - 인사말
            • `ping` - 연결 테스트  
            • `status` - 서버 상태
            • `health` - Flask 상태 확인
            • `flask` - Flask 명령어 도움말
            • `help` - 이 도움말

            💡 **사용법:** 채팅에서 위 명령어를 입력하세요!
            🔧 **관리자:** 서버 관제 및 모니터링"""
    
    say(help_text)

# 일반 메시지 이벤트 핸들러 (모든 메시지 처리)
@slack_server.event("message")
def handle_message_events(body, logger):
    """모든 메시지 이벤트 처리 (로그만 기록)"""
    # 봇 자신의 메시지는 무시
    if body.get("event", {}).get("bot_id"):
        return
    
    # 특정 명령어가 아닌 일반 메시지는 로그만 기록
    event = body.get("event", {})
    user = event.get("user", "Unknown")
    text = event.get("text", "")
    channel = event.get("channel", "Unknown")
    
    logger.info(f"Message from {user} in {channel}: {text}")
    
    # 도움말 안내 (선택사항)
    # 너무 많은 응답을 피하기 위해 주석 처리
    # if text and not text.startswith(("hello", "ping", "status", "health", "flask", "help")):
    #     slack_client.chat_postMessage(
    #         channel=channel,
    #         text="명령어를 모르시겠다면 `help`를 입력해보세요! 😊"
    #     )

def run_flask_server():
    """Flask 서버 실행 함수"""
    global flask_start_time
    flask_start_time = time.time()
    
    print("🌐 Flask 서버 시작 (포트: 5000)")
    try:
        flask_app.run(
            host='0.0.0.0',
            port=5000, 
            debug=False, 
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        print(f"Flask 서버 오류: {e}")

def run_slack_server():
    """Slack 서버 실행 함수"""
    print("⚡ Slack 서버 시작")
    try:
        handler = SocketModeHandler(slack_server, SLACK_APP_TOKEN)
        handler.start()
    except Exception as e:
        print(f"Slack 서버 오류: {e}")

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 Slack & Flask 통합 서버 시작")
    print("=" * 60)
    
    # Flask 서버를 별도 스레드에서 실행
    flask_thread = Thread(
        target=run_flask_server, 
        name="FlaskServerThread",
        daemon=True
    )
    flask_thread.start()
    
    print("🌐 Flask 서버 스레드 시작됨")
    print("📡 Slack 서버를 메인 스레드에서 시작합니다...")
    print("🔗 API 엔드포인트:")
    print("   - POST /detect : 장애 감지 메시지 전송")
    print("   - GET  /health : 헬스 체크")
    print("💡 종료하려면 Ctrl+C를 누르세요")
    print("=" * 60)
    
    # Slack 서버를 메인 스레드에서 실행 (시그널 처리를 위해)
    run_slack_server()

if __name__ == '__main__':
    main()