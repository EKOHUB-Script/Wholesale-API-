import os
import re
from functools import wraps
from flask import session, jsonify, request

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'default_super_secret_password')

def is_admin():
    return session.get('admin') == True

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            log_audit("UNAUTHORIZED_ACCESS", request.path, False, "Not authenticated")
            return jsonify({"error": "Unauthorized"}), 401
        
        # CSRF 방어: POST/DELETE 요청 시 커스텀 헤더 강제 (외부 폼 공격 차단)
        if request.method in ['POST', 'DELETE', 'PUT', 'PATCH']:
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                log_audit("CSRF_BLOCKED", request.path, False, "Missing X-Requested-With header")
                return jsonify({"error": "CSRF check failed"}), 403
                
        return f(*args, **kwargs)
    return decorated_function

def validate_script_name(name):
    """스크립트 이름 검증: 영문, 숫자, _, - 만 허용 (최대 50자)"""
    if not name or len(name) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))

def log_audit(action, target, success, reason=""):
    """DB에 감사 로그 기록 (비밀번호 등 Secret은 절대 기록하지 않음)"""
    try:
        from app import db, AuditLog
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0]
        
        log_entry = AuditLog(
            ip_address=ip,
            action=action,
            target=target,
            success=success,
            reason=reason,
            user_agent=request.headers.get('User-Agent', 'Unknown')[:200]
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"[Audit Log Error] {e}")
