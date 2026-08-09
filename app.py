import os
import logging
from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from security.rate_limit import limiter
from security.auth import admin_required, validate_script_name, log_audit, ADMIN_PASSWORD

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1) # Render 프록시 IP 처리

# --- 기본 설정 ---
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 # 1MB 요청 본문 크기 제한 (DDoS 방어)
app.config['SESSION_COOKIE_SECURE'] = True # HTTPS 전용 쿠키
app.config['SESSION_COOKIE_HTTPONLY'] = True # JS 접근 차단
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # CSRF 완화

# --- DB 설정 ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local_test.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
limiter.init_app(app)

# --- 데이터 모델 ---
class Script(db.Model):
    __tablename__ = 'scripts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)

    def to_dict(self, include_content=False):
        data = {'name': self.name, 'url': f"https://script.ekohub.xyz/{self.name}"}
        if include_content:
            data['content'] = self.content
        return data

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))
    action = db.Column(db.String(50))
    target = db.Column(db.String(100))
    success = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(255))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

with app.app_context():
    db.create_all()

# --- 보안 헤더 설정 ---
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY' # Clickjacking 방어
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # CSP: 대시보드 UI(인라인 스크립트/스타일, Google Fonts)가 깨지지 않도록 설정
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:;"
    return response

# --- 에러 핸들링 (정보 유출 방지) ---
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Resource not found"}), 404
    return Response("Not Found", status=404, mimetype='text/plain')

@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Server Error: {e}", exc_info=True) # 서버 로그에만 상세 기록
    return jsonify({"error": "서버 내부 오류가 발생했습니다."}), 500

@app.errorhandler(RequestEntityTooLarge)
def too_large(e):
    return jsonify({"error": "요청 크기가 1MB 제한을 초과했습니다."}), 413

# --- 웹 대시보드 및 인증 ---
@app.route("/")
@limiter.limit("30 per minute")
def index():
    return render_template("index.html")

@app.route("/login", methods=['POST'])
@limiter.limit("5 per minute") # 브루트포스 방어
def login():
    data = request.json
    if data and data.get('password') == ADMIN_PASSWORD:
        session['admin'] = True
        log_audit("LOGIN", "admin", True)
        return jsonify({"success": True})
    log_audit("LOGIN", "admin", False, "Invalid password")
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/logout", methods=['POST'])
def logout():
    session.pop('admin', None)
    return jsonify({"success": True})

# --- 관리자 API (인증 필수) ---
@app.route("/api/scripts", methods=['GET'])
@admin_required
@limiter.limit("30 per minute")
def get_scripts():
    scripts = Script.query.order_by(Script.name).all()
    return jsonify([script.to_dict(include_content=True) for script in scripts])

@app.route("/api/scripts", methods=['POST'])
@admin_required
@limiter.limit("10 per minute") # 스팸 생성 방어
def save_script():
    data = request.json
    name = data.get('name', '').strip().lower()
    content = data.get('content', '')
    
    if not validate_script_name(name):
        log_audit("CREATE", name, False, "Invalid name format")
        return jsonify({'error': '이름은 영문, 숫자, _, - 만 가능합니다.'}), 400
    
    if len(content) > 100000:
        return jsonify({'error': '코드 길이가 너무 깁니다 (최대 100,000자).'}), 400
    
    existing_script = Script.query.filter_by(name=name).first()
    try:
        if existing_script:
            existing_script.content = content
            log_audit("UPDATE", name, True)
        else:
            new_script = Script(name=name, content=content)
            db.session.add(new_script)
            log_audit("CREATE", name, True)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"DB Error: {e}")
        return jsonify({'error': '서버 내부 오류가 발생했습니다.'}), 500

@app.route("/api/scripts/<name>", methods=['DELETE'])
@admin_required
@limiter.limit("10 per minute")
def delete_script(name):
    safe_name = "".join(c for c in name if c.isalnum() or c in ('_', '-')).lower()
    
    script_to_delete = Script.query.filter_by(name=safe_name).first()
    if script_to_delete:
        try:
            db.session.delete(script_to_delete)
            db.session.commit()
            log_audit("DELETE", safe_name, True)
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"DB Error: {e}")
            return jsonify({'error': '서버 내부 오류가 발생했습니다.'}), 500
    
    log_audit("DELETE", safe_name, False, "Not found")
    return jsonify({'error': '스크립트를 찾을 수 없습니다.'}), 404

# --- 공개 스크립트 호스팅 (로블록스용 / 인증 불필요) ---
@app.route("/<script_name>")
@limiter.limit("100 per minute") # 공개 API DDoS 방어
def serve_script(script_name):
    safe_name = "".join(c for c in script_name if c.isalnum() or c in ('_', '-')).lower()
    
    # 경로 탐색(Path Traversal) 방지
    if not validate_script_name(safe_name) or safe_name != script_name.lower():
        return Response("-- Invalid script name", status=400, mimetype='text/plain')
    
    script = Script.query.filter_by(name=safe_name).first()
    
    if script:
        return Response(script.content, mimetype='text/plain')
    
    return Response("-- Script not found", status=404, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
