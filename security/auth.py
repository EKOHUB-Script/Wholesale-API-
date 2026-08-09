import os
import re
from functools import wraps
from flask import session, jsonify, request

# 환경변수에서 관리자 비밀번호 가져오기
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'default_fallback_password')

def is_admin():
    return session.get('admin') == True

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            return jsonify({"error": "Unauthorized"}), 401
        
        # CSRF 방어: 상태 변경 요청(POST, DELETE 등)은 반드시 커스텀 헤더를 요구
        # (외부 악성 웹사이트에서 폼/스크립트로 직접 요청하는 것을 차단)
        if request.method in ['POST', 'DELETE', 'PUT', 'PATCH']:
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "CSRF check failed"}), 403
                
        return f(*args, **kwargs)
    return decorated_function

def validate_script_name(name):
    """스크립트 이름 검증: 영문, 숫자, _, - 만 허용 (최대 50자)"""
    if not name or len(name) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))
