import os
import requests
import json
import time
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

def sync_argocd_app(app_name):
    """ArgoCD 앱 동기화 API 호출"""
    try:
        headers = {
            "Authorization": f"Bearer {ARGOCD_AUTH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        sync_data = {
            "prune": False,
            "dryRun": False,
            "strategy": {
                "apply": {
                    "force": False
                }
            }
        }
        
        url = f"{ARGOCD_SERVER_URL}/api/v1/applications/{app_name}/sync"
        
        response = requests.post(
            url,
            headers=headers,
            json=sync_data,
            timeout=30,
            verify=False
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "message": f"{app_name} 동기화 성공",
                "app_name": app_name
            }
        else:
            return {
                "success": False,
                "message": f"{app_name} 동기화 실패: {response.status_code}",
                "error": response.text
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"{app_name} 동기화 실패: {str(e)}"
        }

def call_argocd_pm_api():
    """ArgoCD PM 환경 앱들 동기화"""
    pm_apps = [
        "k-rater-uq-remains-data-pm",
        "k-rater-uq-summary-pm", 
        "k-rater-uq-summary-customer-pm"
    ]
    
    results = []
    success_count = 0
    
    for app in pm_apps:
        result = sync_argocd_app(app)
        results.append(result)
        if result["success"]:
            success_count += 1
    
    return {
        "success": success_count == len(pm_apps),
        "message": f"PM 환경 동기화 완료: {success_count}/{len(pm_apps)}개 성공",
        "environment": "PM",
        "results": results,
        "success_count": success_count,
        "total_count": len(pm_apps)
    }

def call_argocd_prd_api():
    """ArgoCD PRD 환경 앱들 동기화"""
    prd_apps = [
        "k-rater-uq-remains-data-prd",
        "k-rater-uq-summary-prd",
        "k-rater-uq-summary-customer-prd"
    ]
    
    results = []
    success_count = 0
    
    for app in prd_apps:
        result = sync_argocd_app(app)
        results.append(result)
        if result["success"]:
            success_count += 1
    
    return {
        "success": success_count == len(prd_apps),
        "message": f"PRD 환경 동기화 완료: {success_count}/{len(prd_apps)}개 성공",
        "environment": "PRD", 
        "results": results,
        "success_count": success_count,
        "total_count": len(prd_apps)
    }

# PM 동기화 메시지 핸들러
@slack_server.message("pm")
def handle_pm_message(message, say):
    """PM 환경 앱들 동기화"""
    user_id = message.get('user', '')
    
    say("🔄 PM 환경 앱들을 동기화 중입니다... 잠시만 기다려주세요!")
    
    # PM 동기화 실행
    result = call_argocd_pm_api()
    
    if result["success"]:
        apps_detail = "\n".join([f"• {r['app_name']}: {'✅' if r['success'] else '❌'}" 
                                for r in result['results']])
        
        say(f"""🎉 **{result['message']}**

📊 **동기화 결과:**
{apps_detail}

• 🏷️ 환경: {result['environment']}
• 📊 성공률: {result['success_count']}/{result['total_count']}
• 🕐 동기화 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}
• 👤 요청자: <@{user_id}>

✅ PM 환경 동기화 완료!""")
    else:
        failed_apps = [r for r in result['results'] if not r['success']]
        error_detail = "\n".join([f"• {r['app_name']}: {r['message']}" for r in failed_apps])
        
        say(f"""❌ **PM 동기화 실패**

🔥 실패한 앱들:
{error_detail}

📊 성공률: {result['success_count']}/{result['total_count']}
👤 요청자: <@{user_id}>
🕐 실패 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}""")

# PRD 동기화 메시지 핸들러  
@slack_server.message("prd")
def handle_prd_message(message, say):
    """PRD 환경 앱들 동기화"""
    user_id = message.get('user', '')
    
    say("🚀 PRD 환경 앱들을 동기화 중입니다... 잠시만 기다려주세요!")
    
    # PRD 동기화 실행
    result = call_argocd_prd_api()
    
    if result["success"]:
        apps_detail = "\n".join([f"• {r['app_name']}: {'✅' if r['success'] else '❌'}" 
                                for r in result['results']])
        
        say(f"""🎉 **{result['message']}**

📊 **동기화 결과:**
{apps_detail}

• 🏷️ 환경: {result['environment']}  
• 📊 성공률: {result['success_count']}/{result['total_count']}
• 🕐 동기화 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}
• 👤 요청자: <@{user_id}>

🚀 PRD 환경 동기화 완료!""")
    else:
        failed_apps = [r for r in result['results'] if not r['success']]
        error_detail = "\n".join([f"• {r['app_name']}: {r['message']}" for r in failed_apps])
        
        say(f"""❌ **PRD 동기화 실패**

🔥 실패한 앱들:
{error_detail}

📊 성공률: {result['success_count']}/{result['total_count']}
👤 요청자: <@{user_id}>
🕐 실패 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}""")

# 도움말 메시지
@slack_server.message("help")
def handle_help_message(message, say):
    """도움말 메시지"""
    help_text = """🤖 **ArgoCD 동기화 봇 사용법**

📋 **사용 가능한 명령어:**
• `pm` - 🔄 PM 환경 앱들 동기화
• `prd` - 🚀 PRD 환경 앱들 동기화  
• `help` - 이 도움말 표시

📱 **동기화되는 앱들:**
**PM 환경:**
• k-rater-uq-remains-data-pm
• k-rater-uq-summary-pm
• k-rater-uq-summary-customer-pm

**PRD 환경:**
• k-rater-uq-remains-data-prd
• k-rater-uq-summary-prd
• k-rater-uq-summary-customer-prd

💡 **사용법:** 
- PM 환경 앱들을 동기화하려면 `pm` 입력
- PRD 환경 앱들을 동기화하려면 `prd` 입력

⚠️ **주의사항:**
- 동기화 작업은 약 30초 소요됩니다
- 동기화 중에는 서비스 업데이트가 발생할 수 있습니다"""
    
    say(help_text)

# Flask API 엔드포인트
@flask_app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "message": "ArgoCD 동기화 봇 실행 중",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@flask_app.route('/sync-env', methods=['POST'])
def sync_environment():
    """외부에서 환경 동기화를 트리거하는 API"""
    try:
        data = request.get_json() or {}
        env = data.get('environment', '').lower()
        
        if env == 'pm':
            result = call_argocd_pm_api()
        elif env == 'prd':
            result = call_argocd_prd_api()
        else:
            return {"error": "Invalid environment. Use 'pm' or 'prd'"}, 400
        
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
    print("🤖 ArgoCD 동기화 봇")
    print("🔄 PM/PRD 환경 앱 동기화")
    print("=" * 60)
    
    print("✅ 환경 변수 로드 완료")
    print("🔗 Flask API: http://localhost:5000")
    print("💡 사용법: Slack에서 'pm' 또는 'prd' 입력")
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