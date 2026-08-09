import os
from flask import Flask, render_template, jsonify, request, Response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- Supabase 데이터베이스 설정 ---
# 1. 환경변수에서 DATABASE_URL 가져오기
database_url = os.environ.get('DATABASE_URL')

# 로컬 테스트용: 환경변수가 없을 경우 임시 SQLite 사용 (Render 배포 시에는 무시됨)
if not database_url:
    database_url = 'sqlite:///local_test.db'
    print("경고: DATABASE_URL이 설정되지 않아 로컬 SQLite를 사용합니다.")
else:
    # 2. Supabase(또는 기타 호스팅)에서 'postgres://'로 시작하는 URI를 제공할 경우
    # SQLAlchemy 2.0+ 호환을 위해 'postgresql://'로 변환
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

# 3. Flask-SQLAlchemy 설정
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Supabase Pooler(트랜잭션/세션) 사용 시 커넥션 재활용 설정 (선택 사항이지만 권장)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300
}

db = SQLAlchemy(app)

# --- 데이터 모델 정의 ---
class Script(db.Model):
    __tablename__ = 'scripts' # Supabase에 생성될 테이블 이름
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'name': self.name,
            'content': self.content,
            'url': f"https://script.ekohub.xyz/{self.name}"
        }

# 앱 실행 시 테이블 생성 (최초 1회 자동 생성됨)
with app.app_context():
    db.create_all()

# --- 웹 UI 라우트 ---
@app.route("/")
def index():
    """스크립트 관리 대시보드 UI"""
    return render_template("index.html")

# --- API 라우트 ---
@app.route("/api/scripts", methods=['GET'])
def get_scripts():
    """DB에 저장된 모든 스크립트 목록 반환"""
    scripts = Script.query.order_by(Script.name).all()
    return jsonify([script.to_dict() for script in scripts])

@app.route("/api/scripts", methods=['POST'])
def save_script():
    """스크립트 저장 또는 수정 (Create / Update)"""
    data = request.json
    name = data.get('name', '').strip().lower()
    content = data.get('content', '')
    
    # 파일명(스크립트 이름) 유효성 검사
    if not name or not all(c.isalnum() or c in ('_', '-') for c in name):
        return jsonify({'error': '이름은 영문, 숫자, _, - 만 사용할 수 있습니다.'}), 400
    
    # DB에서 동일한 이름의 스크립트 찾기
    existing_script = Script.query.filter_by(name=name).first()
    
    try:
        if existing_script:
            # 이미 있으면 내용 수정 (Update)
            existing_script.content = content
        else:
            # 없으면 새로 생성 (Create)
            new_script = Script(name=name, content=content)
            db.session.add(new_script)
            
        db.session.commit()
        return jsonify({'success': True, 'message': f'{name} 스크립트가 저장되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'DB 저장 실패: {str(e)}'}), 500

@app.route("/api/scripts/<name>", methods=['DELETE'])
def delete_script(name):
    """스크립트 삭제 (Delete)"""
    safe_name = "".join(c for c in name if c.isalnum() or c in ('_', '-')).lower()
    
    script_to_delete = Script.query.filter_by(name=safe_name).first()
    if script_to_delete:
        try:
            db.session.delete(script_to_delete)
            db.session.commit()
            return jsonify({'success': True, 'message': f'{safe_name} 스크립트가 삭제되었습니다.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'삭제 실패: {str(e)}'}), 500
    
    return jsonify({'error': '스크립트를 찾을 수 없습니다.'}), 404

# --- 로블록스 스크립트 호스팅 라우트 ---
@app.route("/<script_name>")
def serve_script(script_name):
    """로블록스에서 loadstring으로 불러올 스크립트 반환 (Read)"""
    safe_name = "".join(c for c in script_name if c.isalnum() or c in ('_', '-')).lower()
    
    # DB에서 스크립트 찾기
    script = Script.query.filter_by(name=safe_name).first()
    
    if script:
        # ★ 핵심: HTML이 아닌 텍스트(text/plain)로 반환
        return Response(script.content, mimetype='text/plain')
    
    return Response("-- Script not found", status=404, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
