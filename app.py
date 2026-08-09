import os
import datetime
import requests
from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User, Script
from security.rate_limit import limiter
from security.auth import login_required, admin_required, check_upload_limits, get_current_user

app = Flask(__name__)
# Render 리버스 프록시 환경에서 실제 클라이언트 IP 및 HTTPS 정보 보존
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- 기본 설정 ---
app.secret_key = os.environ.get('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 # 1MB 제한
# Render HTTPS 환경에 맞춘 세션 쿠키 보안 설정 (매우 중요)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# --- DB 설정 ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local_test.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
limiter.init_app(app)

# --- 인증 서버 설정 ---
AUTH_SERVER_URL = os.environ.get("AUTH_SERVER_URL", "https://authentication.p-e.kr")
AUTH_INTERNAL_SECRET = os.environ.get('AUTH_INTERNAL_SECRET')

# --- 보안 헤더 ---
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://cdn.discordapp.com; connect-src 'self';"
    return response

# --- 웹 대시보드 및 auth_code 처리 ---
@app.route("/")
@limiter.limit("30 per minute")
def index():
    auth_code = request.args.get('auth_code')
    
    # 인증 서버에서 리다이렉트된 auth_code가 있는 경우 서버 사이드 검증
    if auth_code:
        try:
            verify_res = requests.post(
                f"{AUTH_SERVER_URL}/api/auth/verify",
                headers={
                    "Content-Type": "application/json",
                    "X-Auth-Secret": AUTH_INTERNAL_SECRET
                },
                json={"code": auth_code},
                timeout=5 # 타임아웃 설정
            )
            
            # HTTP 상태 코드와 JSON 형식 검증
            if verify_res.status_code == 200:
                user_data = verify_res.json()
                discord_id = user_data.get("discord_id")
                username = user_data.get("username")
                avatar_url = user_data.get("avatar_url")
                
                if discord_id:
                    # DB 유저 조회/생성
                    user = User.query.filter_by(discord_id=discord_id).first()
                    if not user:
                        user = User(discord_id=discord_id, role='user', username=username, avatar_url=avatar_url)
                        db.session.add(user)
                    else:
                        # 기존 유저 정보(이름, 프사) 업데이트
                        user.username = username
                        user.avatar_url = avatar_url
                        
                    db.session.commit()
                    session['user_id'] = user.id
                    # 파라미터 제거하고 메인 페이지로 새로고침
                    return redirect(url_for('index'))
            else:
                app.logger.error(f"Auth verify failed: Status {verify_res.status_code}")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Auth server network error: {str(e)}")
        except ValueError:
            app.logger.error("Auth verify response is not valid JSON")
        
        # 검증 실패 시 에러 파라미터와 함께 리다이렉트
        return redirect(url_for('index', error='auth_failed'))
        
    return render_template("index.html")

# --- 인증 라우트 ---
@app.route("/api/auth/discord")
def discord_login():
    # 메인 서버는 직접 OAuth를 처리하지 않고 인증 서버로 리다이렉트
    return redirect(f"{AUTH_SERVER_URL}/api/auth/discord")

@app.route("/api/auth/logout", methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({"success": True})

@app.route("/api/auth/me", methods=['GET'])
def get_me():
    user = get_current_user()
    if user:
        return jsonify({
            "loggedIn": True, 
            "role": user.role,
            "username": user.username,
            "avatar_url": user.avatar_url
        })
    return jsonify({"loggedIn": False}), 401

# --- 관리자 로그인 (비밀번호 방식 유지) ---
@app.route("/api/auth/admin", methods=['POST'])
@limiter.limit("5 per minute")
def admin_auth():
    data = request.json
    if data and data.get('password') == os.environ.get('ADMIN_PASSWORD'):
        # 관리자 Discord ID가 설정되어 있으면 해당 유저를 찾아서 로그인
        admin_user = User.query.filter_by(discord_id=os.environ.get('ADMIN_DISCORD_ID', 'admin')).first()
        if not admin_user:
            admin_user = User(discord_id='admin', role='admin', username='EKOHUB Admin', avatar_url=None)
            db.session.add(admin_user)
            db.session.commit()
        session['user_id'] = admin_user.id
        return jsonify({"success": True, "role": "admin"})
    return jsonify({"error": "관리자 비밀번호가 틀렸습니다."}), 401

# --- 스크립트 API (기존 로직 유지) ---
@app.route("/api/scripts", methods=['GET'])
@limiter.limit("30 per minute")
def get_scripts():
    current_user = get_current_user()
    scripts = Script.query.order_by(Script.name).all()
    result = []
    for script in scripts:
        data = script.to_dict(current_user)
        data['content'] = script.content
        result.append(data)
    return jsonify(result)

@app.route("/api/scripts", methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def save_script():
    user = get_current_user()
    
    if user.role != 'admin':
        allowed, msg = check_upload_limits()
        if not allowed:
            return jsonify({"error": msg}), 429

    data = request.json
    name = data.get('name', '').strip().lower()
    content = data.get('content', '')
    
    if not name or not all(c.isalnum() or c in ('_', '-') for c in name) or len(name) > 50:
        return jsonify({'error': '이름은 영문, 숫자, _, - 만 가능하며 50자 이내여야 합니다.'}), 400
    
    if len(content) > 100000:
        return jsonify({'error': '코드 길이가 너무 깁니다.'}), 400
    
    existing_script = Script.query.filter_by(name=name).first()
    try:
        if existing_script:
            if existing_script.owner_id != user.id and user.role != 'admin':
                return jsonify({"error": "다른 유저의 스크립트는 수정할 수 없습니다."}), 403
            existing_script.content = content
        else:
            new_script = Script(name=name, content=content, owner_id=user.id)
            db.session.add(new_script)
            
            if user.role != 'admin':
                user.daily_upload_count += 1
                user.last_upload_time = datetime.datetime.now()
                user.last_upload_date = datetime.date.today()

        db.session.commit()
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        return jsonify({'error': '서버 오류'}), 500

@app.route("/api/scripts/<name>", methods=['DELETE'])
@login_required
@limiter.limit("10 per minute")
def delete_script(name):
    user = get_current_user()
    safe_name = "".join(c for c in name if c.isalnum() or c in ('_', '-')).lower()
    
    script_to_delete = Script.query.filter_by(name=safe_name).first()
    if script_to_delete:
        if script_to_delete.owner_id != user.id and user.role != 'admin':
            return jsonify({"error": "다른 유저의 스크립트는 삭제할 수 없습니다."}), 403
            
        try:
            db.session.delete(script_to_delete)
            db.session.commit()
            return jsonify({'success': True})
        except Exception:
            db.session.rollback()
            return jsonify({'error': '서버 오류'}), 500
    
    return jsonify({'error': '스크립트를 찾을 수 없습니다.'}), 404

# --- 공개 스크립트 호스팅 ---
@app.route("/<script_name>")
@limiter.limit("100 per minute")
def serve_script(script_name):
    safe_name = "".join(c for c in script_name if c.isalnum() or c in ('_', '-')).lower()
    if not safe_name or len(safe_name) > 50 or safe_name != script_name.lower():
        return Response("-- Invalid script name", status=400, mimetype='text/plain')
    script = Script.query.filter_by(name=safe_name).first()
    if script:
        return Response(script.content, mimetype='text/plain')
    return Response("-- Script not found", status=404, mimetype='text/plain')

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
