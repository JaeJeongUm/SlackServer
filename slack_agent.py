import os
import requests
import json
import time
import subprocess
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from flask import Flask, request, jsonify
from threading import Thread

# 환경 변수 로드 (.env 파일 사용)
load_dotenv(dotenv_path='config/.env')

# 환경 변수 확인 및 로드
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
ARGOCD_SERVER_URL = os.environ.get("ARGOCD_SERVER_URL")
ARGOCD_AUTH_TOKEN = os.environ.get("ARGOCD_AUTH_TOKEN")

# 환경 변수 디버깅
print("=== 환경 변수 확인 ===")
print(f"SLACK_BOT_TOKEN: {'설정됨' if SLACK_BOT_TOKEN else '❌ 없음'}")
print(f"SLACK_SIGNING_SECRET: {'설정됨' if SLACK_SIGNING_SECRET else '❌ 없음'}")
print(f"SLACK_APP_TOKEN: {'설정됨' if SLACK_APP_TOKEN else '❌ 없음'}")
print(f"ARGOCD_SERVER_URL: {ARGOCD_SERVER_URL if ARGOCD_SERVER_URL else '❌ 없음'}")
print(f"ARGOCD_AUTH_TOKEN: {'설정됨' if ARGOCD_AUTH_TOKEN else '❌ 없음'}")
print("=====================")

# 필수 환경 변수 검증
if not all([SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APP_TOKEN]):
    print("❌ Slack 토큰이 설정되지 않았습니다!")
    exit(1)

# Slack Server 역할
slack_server = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET
)

# Flask 서버 초기화
flask_app = Flask(__name__)


def execute_env_switch(environment):
    """환경 전환 스크립트 실행"""
    try:
        # 스크립트 실행
        result = subprocess.run(
            ['/app/prd-pm-exchange.sh', environment],
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )

        if result.returncode == 0:
            return {
                "success": True,
                "message": f"환경 전환 성공: {environment.upper()}",
                "output": result.stdout,
                "environment": environment.upper()
            }
        else:
            return {
                "success": False,
                "message": f"환경 전환 실패: {environment.upper()}",
                "error": result.stderr,
                "environment": environment.upper()
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "환경 전환 타임아웃 (5분 초과)",
            "environment": environment.upper()
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"환경 전환 스크립트 실행 오류: {str(e)}",
            "environment": environment.upper()
        }


# PM 환경 전환 메시지 핸들러
@slack_server.message("pm")
def handle_pm_message(message, say):
    """PM 환경으로 전환"""
    user_id = message.get('user', '')

    say("🔄 PM 환경으로 전환 중입니다... 잠시만 기다려주세요!")

    # PM 환경 전환 실행
    result = execute_env_switch("pm")

    if result["success"]:
        say(f"""🎉 **PM 환경 전환 완료!**

✅ {result['message']}
🏷️ 현재 환경: **{result['environment']}**
🕐 전환 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}
👤 요청자: <@{user_id}>

✅ PM 환경이 활성화되었습니다!""")
    else:
        say(f"""❌ **PM 환경 전환 실패**

🔥 오류: {result['message']}
👤 요청자: <@{user_id}>
🕐 실패 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ 환경 전환에 실패했습니다. 관리자에게 문의하세요.""")


# PRD 환경 전환 메시지 핸들러
@slack_server.message("prd")
def handle_prd_message(message, say):
    """PRD 환경으로 전환"""
    user_id = message.get('user', '')

    say("🚀 PRD 환경으로 전환 중입니다... 잠시만 기다려주세요!")

    # PRD 환경 전환 실행
    result = execute_env_switch("prd")

    if result["success"]:
        say(f"""🎉 **PRD 환경 전환 완료!**

✅ {result['message']}
🏷️ 현재 환경: **{result['environment']}**
🕐 전환 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}
👤 요청자: <@{user_id}>

🚀 PRD 환경이 활성화되었습니다!""")
    else:
        say(f"""❌ **PRD 환경 전환 실패**

🔥 오류: {result['message']}
👤 요청자: <@{user_id}>
🕐 실패 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ 환경 전환에 실패했습니다. 관리자에게 문의하세요.""")


# 도움말 메시지
@slack_server.message("help")
def handle_help_message(message, say):
    """도움말 메시지"""
    help_text = """🤖 **ArgoCD 환경 전환 봇 사용법**

📋 **사용 가능한 명령어:**
• `pm` - 🔄 PM 환경으로 전환
• `prd` - 🚀 PRD 환경으로 전환  
• `help` - 이 도움말 표시

💡 **사용법:** 
- PM 환경으로 전환: `pm` 입력
- PRD 환경으로 전환: `prd` 입력

⚠️ **주의사항:**
- 환경 전환은 약 1-2분 소요됩니다
- 환경 전환 시 ApplicationSet이 업데이트되고 앱들이 재배포됩니다
- 한 번에 하나의 환경만 활성화됩니다

🔧 **전환 과정:**
1. Git 저장소 클론
2. ApplicationSet YAML 파일 수정 (yq 사용)
3. 변경사항 커밋 및 푸시
4. ArgoCD ApplicationSet 동기화"""

    say(help_text)


# Flask API 엔드포인트
@flask_app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "message": "ArgoCD 환경 전환 봇 실행 중",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@flask_app.route('/switch-env', methods=['POST'])
def switch_environment():
    """외부에서 환경 전환을 트리거하는 API"""
    try:
        data = request.get_json() or {}
        env = data.get('environment', '').lower()

        if env not in ['pm', 'prd']:
            return {"error": "Invalid environment. Use 'pm' or 'prd'"}, 400

        result = execute_env_switch(env)

        if result['success']:
            return {"status": "success", "result": result}
        else:
            return {"status": "error", "message": result['message'], "details": result}, 500

    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


def run_flask_server():
    """Flask 서버 실행 함수"""
    print("🌐 Flask 서버 시작 (포트: 5000)")
    try:
        flask_app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
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
    print("🤖 ArgoCD 환경 전환 봇")
    print("🔄 PM/PRD 환경 전환 자동화")
    print("=" * 60)

    print("✅ 환경 변수 로드 완료")
    print("🔗 Flask API: http://localhost:5000")
    print("💡 사용법: Slack에서 'pm' 또는 'prd' 입력")
    print("🔧 스크립트: /app/prd-pm-exchange.sh")
    print("=" * 60)

    # Flask 서버를 별도 스레드에서 실행
    flask_thread = Thread(
        target=run_flask_server,
        name="FlaskServerThread",
        daemon=True
    )
    flask_thread.start()

    # Slack 서버를 메인 스레드에서 실행
    run_slack_server()


if __name__ == '__main__':
    main()