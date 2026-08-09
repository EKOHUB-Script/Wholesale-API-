import os
import datetime
from functools import wraps
from flask import session, jsonify, request
from app import db, User

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized. 로그인이 필요합니다."}), 401
        
        # CSRF 방어: 상태 변경 요청은 커스텀 헤더 필수
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "CSRF check failed"}), 403
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.role != 'admin':
            return jsonify({"error": "Forbidden. 관리자 권한이 필요합니다."}), 403
        
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "CSRF check failed"}), 403
        return f(*args, **kwargs)
    return decorated

def check_upload_limits():
    """일반 유저의 업로드 제한 검사 (3분 1회, 하루 10회)"""
    user = get_current_user()
    if not user or user.role == 'admin':
        return True, None # 관리자는 제한 없음

    now = datetime.datetime.now()
    today = now.date()

    # 날짜가 바뀌면 카운트 초기화
    if user.last_upload_date < today:
        user.daily_upload_count = 0
        user.last_upload_date = today

    # 하루 10개 제한
    if user.daily_upload_count >= 10:
        return False, "하루 최대 10개까지만 업로드할 수 있습니다."

    # 3분(180초)당 1개 제한
    if user.last_upload_time:
        diff = (now - user.last_upload_time).total_seconds()
        if diff < 180:
            return False, f"스크립트 업로드는 3분당 1개만 가능합니다. ({int(180-diff)}초 후 시도하세요)"

    return True, None
