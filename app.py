import os
from urllib.parse import urlparse
from flask import Flask, render_template, jsonify, request, Response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- Supabase 데이터베이스 설정 ---
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    database_url = 'sqlite:///local_test.db'
    print("경고: DATABASE_URL이 설정되지 않아 로컬 SQLite를 사용합니다.")
else:
    # SQLAlchemy 2.0+ 호환을 위해 'postgres://'를 'postgresql://'로 변환
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # --- 안전한 디버깅 로그 ---
    # 비밀번호를 노출하지 않고 연결 정보만 파싱하여 출력합니다.
    try:
        parsed_url = urlparse(database_url)
        print("\n" + "="*50)
        print(" [DB 연결 정보 디버깅 (비밀번호 출력 안함) ]")
        print(f"  1. DATABASE_URL 설정 여부: True")
        print(f"  2. 스키마 (Scheme): {parsed_url.scheme}")
        print(f"  3. 사용자명: {parsed_url.username}")
        print(f"  4. 호스트 (Host): {parsed_url.hostname}")
        print(f"  5. 포트 (Port): {parsed_url.port}")
        print(f"  6. 데이터베이스 이름: {parsed_url.path.lstrip('/')}")
        print("="*50 + "\n")
    except Exception as e:
        print(f"URL 파싱 중 오류 발생: {e}")

# Flask-SQLAlchemy 설정
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300
}

db = SQLAlchemy(app)

# --- 데이터 모델 정의 ---
class Script(db.Model):
    __tablename__ = 'scripts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'name': self.name,
            'content': self.content,
            'url': f"https://script.ekohub.xyz/{self.name}"
        }

with app.app_context():
    db.create_all()

# --- 웹 UI 라우트 ---
@app.route("/")
def index():
    return render_template("index.html")

# --- API 라우트 ---
@app.route("/api/scripts", methods=['GET'])
def get_scripts():
    scripts = Script.query.order_by(Script.name).all()
    return jsonify([script.to_dict() for script in scripts])

@app.route("/api/scripts", methods=['POST'])
def save_script():
    data = request.json
    name = data.get('name', '').strip().lower()
    content = data.get('content', '')
    
    if not name or not all(c.isalnum() or c in ('_', '-') for c in name):
        return jsonify({'error': '이름은 영문, 숫자, _, - 만 사용할 수 있습니다.'}), 400
    
    existing_script = Script.query.filter_by(name=name).first()
    
    try:
        if existing_script:
            existing_script.content = content
        else:
            new_script = Script(name=name, content=content)
            db.session.add(new_script)
            
        db.session.commit()
        return jsonify({'success': True, 'message': f'{name} 스크립트가 저장되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'DB 저장 실패: {str(e)}'}), 500

@app.route("/api/scripts/<name>", methods=['DELETE'])
def delete_script(name):
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
    safe_name = "".join(c for c in script_name if c.isalnum() or c in ('_', '-')).lower()
    
    script = Script.query.filter_by(name=safe_name).first()
    
    if script:
        return Response(script.content, mimetype='text/plain')
    
    return Response("-- Script not found", status=404, mimetype='text/plain')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
