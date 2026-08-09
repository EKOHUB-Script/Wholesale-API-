import os
import datetime
import requests
from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User, Script  # 🚨 변경된 부분: models에서 import
from security.rate_limit import limiter
from security.auth import login_required, admin_required, check_upload_limits, get_current_user

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = os.environ.get('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 # 1MB 제한

database_url = os.environ.get('DATABASE_URL', 'sqlite:///local_test.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🚨 변경된 부분: db 객체를 app에 초기화
db.init_app(app)
limiter.init_app(app)

# --- 보안 헤더 ---
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:;"
    return response

# --- 웹 대시보드 ---
@app.route("/")
@limiter.limit("30 per minute")
def index():
    return render_template("index.html")

# --- 디스코드 OAuth2 인증 ---
@app.route("/api/auth/discord")
def discord_login():
    client_id = os.environ.get('DISCORD_CLIENT_ID')
    redirect_uri = "https://script.ekohub.xyz/api/auth/discord/callback"
    scope = "identify"
    discord_auth_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}"
    return redirect(discord_auth_url)

@app.route("/api/auth/discord/callback")
@limiter.limit("10 per minute")
def discord_callback():
    code = request.args.get('code')
    if not code:
        return redirect("/?error=auth_failed")

    token_url = "https://discord.com/api/oauth2/token"
    payload = {
        "client_id": os.environ.get('DISCORD_CLIENT_ID'),
        "client_secret": os.environ.get('DISCORD_CLIENT_SECRET'),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://script.ekohub.xyz/api/auth/discord/callback"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    token_res = requests.post(token_url, data=payload, headers=headers)
    if token_res.status_code != 200:
        return redirect("/?error=token_failed")
    
    access_token = token_res.json().get("access_token")
    
    user_res = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access_token}"})
    if user_res.status_code != 200:
        return redirect("/?error=user_fetch_failed")
    
    discord_id = user_res.json().get("id")
    
    user = User.query.filter_by(discord_id=discord_id).first()
    if not user:
        user = User(discord_id=discord_id, role='user')
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    return redirect("/")

# --- 관리자 인증 ---
@app.route("/api/auth/admin", methods=['POST'])
@limiter.limit("5 per minute")
def admin_auth():
    data = request.json
    if data and data.get('password') == os.environ.get('ADMIN_PASSWORD'):
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            admin_user = User(discord_id='admin', role='admin')
            db.session.add(admin_user)
            db.session.commit()
        session['user_id'] = admin_user.id
        return jsonify({"success": True, "role": "admin"})
    return jsonify({"error": "관리자 비밀번호가 틀렸습니다."}), 401

@app.route("/api/auth/logout", methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({"success": True})

@app.route("/api/auth/me", methods=['GET'])
def get_me():
    user = get_current_user()
    if user:
        return jsonify({"loggedIn": True, "role": user.role})
    return jsonify({"loggedIn": False}), 401

# --- 스크립트 API ---
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
    except Exception as e:
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

# --- 공개 스크립트 호스팅 (로블록스용) ---
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

# --- 테이블 생성 ---
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
